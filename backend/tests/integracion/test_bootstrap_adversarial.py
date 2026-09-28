"""Q4/Q7 adversarial del bootstrap: carreras, credenciales raras, permisos, fallos y fugas."""

import asyncio
import secrets
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine, pool

from app.application.use_cases.crear_admin_inicial import CrearAdminInicial
from app.infrastructure.db.bootstrap import orquestador
from app.infrastructure.db.bootstrap.errores import FalloEnPaso
from app.infrastructure.db.bootstrap.migraciones import configuracion_alembic
from tests.integracion.conftest import BasePrueba, RolesPrueba
from tests.integracion.pg_efimero import ServidorPg
from tests.integracion.soporte_bd import (
    AvisoCapturado,
    bootstrap_en_proceso,
    bootstrap_en_subproceso,
    bootstrap_en_subproceso_async,
    conteos,
)
from tests.soporte import APP_MASTER_KEY_PRUEBA, JWT_SECRET_PRUEBA, ORIGEN_PERMITIDO

LINEA_CONTRASENA: Final = "Contraseña inicial del administrador "
CLAVE_RARA: Final = "p@ss:w%rd/#?&=+ ñ;'\"x"
CLAVE_URL_RARA: Final = "secretpw-qa"
MENSAJE_FALLO: Final = "fallo simulado de auditoría"


def _variables(url: str, **extra: str) -> dict[str, str]:
    return {"DATABASE_URL": url, **extra}


# ------------------------------------------------------------------ carreras


async def test_cuatro_bootstraps_a_la_vez_sobre_una_base_que_no_existe(
    backend_aislado: Path, postgres_efimero: ServidorPg, nombre_base_libre: str
) -> None:
    url = postgres_efimero.url(nombre_base_libre, "postgresql+asyncpg")
    variables = _variables(url, DB_AUTO_CREATE="true")
    resultados = await asyncio.gather(
        *(bootstrap_en_subproceso_async(backend_aislado, variables) for _ in range(4))
    )
    with postgres_efimero.conectar(nombre_base_libre) as conexion:
        cuentas = conteos(conexion)
        migradas = conexion.execute(
            "SELECT count(*) FROM auditoria WHERE accion = 'bd.migrada'"
        ).fetchone()
        semillas = conexion.execute(
            "SELECT count(*) FROM auditoria WHERE accion = 'bd.semillas_aplicadas'"
        ).fetchone()
    mostradas = sum(r.stderr.count(LINEA_CONTRASENA) for r in resultados)
    assert [r.codigo for r in resultados] == [0, 0, 0, 0]
    assert (cuentas["usuarios"], cuentas["agentes"], cuentas["categorias"]) == (1, 5, 7)
    assert (migradas, semillas, mostradas) == ((1,), (1,), 1)


# ------------------------------------------------------------------ credenciales y permisos


def test_bootstrap_roles_separados_con_contrasenas_de_caracteres_especiales(
    backend_aislado: Path, base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    clave_migrador, clave_app = CLAVE_RARA + "-m", CLAVE_RARA + "-a"
    with base_limpia.conectar() as conexion:
        for rol, clave in (("agente_migrador", clave_migrador), ("agente_app", clave_app)):
            conexion.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(rol), sql.Literal(clave))
            )
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        {
            "DATABASE_URL": base_limpia.url(usuario="agente_app", contrasena=clave_app),
            "DATABASE_URL_MIGRADOR": base_limpia.url(
                usuario="agente_migrador", contrasena=clave_migrador
            ),
            "DB_ROLES_SEPARADOS": "true",
        },
    )
    visible = resultado.stdout + resultado.stderr
    assert resultado.codigo == 0
    assert [c for c in (clave_app, clave_migrador, "w%rd") if c in visible] == []


def test_bootstrap_contrasena_incorrecta_de_agente_app_falla_sin_filtrar(
    backend_aislado: Path, base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        {
            "DATABASE_URL": base_limpia.url(usuario="agente_app", contrasena=CLAVE_RARA),
            "DATABASE_URL_MIGRADOR": roles_separados.url_migrador,
            "DB_ROLES_SEPARADOS": "true",
        },
    )
    visible = resultado.stdout + resultado.stderr
    fallo = [log for log in resultado.logs() if log["evento"] == "bootstrap.fallido"]
    assert resultado.codigo == 2
    assert [f["paso"] for f in fallo] == ["privilegios"]
    assert [
        d
        for d in (
            CLAVE_RARA,
            "w%rd",
            roles_separados.contrasena_migrador,
            roles_separados.contrasena_app,
            "agente_app",
            "agente_migrador",
            base_limpia.nombre,
        )
        if d in visible
    ] == []


@pytest.fixture
def rol_sin_permisos(base_limpia: BasePrueba) -> Iterator[tuple[str, str]]:
    """Rol con LOGIN y CONNECT, sin CREATE en la base ni en `public`."""
    nombre, clave = f"qa_sin_ddl_{secrets.token_hex(4)}", secrets.token_urlsafe(12)
    rol = sql.Identifier(nombre)
    with base_limpia.conectar() as conexion:
        conexion.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(rol, sql.Literal(clave))
        )
        conexion.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(base_limpia.nombre), rol
            )
        )
    try:
        yield nombre, clave
    finally:
        with base_limpia.conectar() as conexion:
            conexion.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(
                    sql.Identifier(base_limpia.nombre), rol
                )
            )
            conexion.execute(sql.SQL("DROP ROLE {}").format(rol))


def test_bootstrap_con_rol_sin_permiso_de_creacion_falla_con_codigo_2_sin_filtrar(
    backend_aislado: Path, base_limpia: BasePrueba, rol_sin_permisos: tuple[str, str]
) -> None:
    usuario, clave = rol_sin_permisos
    resultado = bootstrap_en_subproceso(
        backend_aislado, _variables(base_limpia.url(usuario=usuario, contrasena=clave))
    )
    visible = resultado.stdout + resultado.stderr
    fallo = [log for log in resultado.logs() if log["evento"] == "bootstrap.fallido"]
    with base_limpia.conectar() as conexion:
        tablas = conexion.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
        ).fetchone()
    assert resultado.codigo == 2
    assert [(f["paso"], f["sqlstate"]) for f in fallo] == [("migraciones", "42501")]
    assert tablas == (0,)
    assert [d for d in (clave, usuario, base_limpia.nombre) if d in visible] == []


@pytest.mark.parametrize(
    "url",
    [
        "no-es-una-url",
        f"postgresql+asyncpg://u:{CLAVE_URL_RARA}@127.0.0.1:abc/bd",
        f"postgresql+asyncpg://u:{CLAVE_URL_RARA}@127.0.0.1:99999/bd",
        f"postgresql+asyncpg://u:{CLAVE_URL_RARA}@127.0.0.1:5432/",
        f"mysql://u:{CLAVE_URL_RARA}@127.0.0.1/bd",
        f"postgresql+asyncpg://u:{CLAVE_URL_RARA}@[::1/bd",
    ],
)
def test_bootstrap_url_malformada_termina_con_codigo_1_o_2_sin_eco(
    backend_aislado: Path, url: str
) -> None:
    resultado = bootstrap_en_subproceso(backend_aislado, _variables(url, DB_ESPERA_MAX_S="1"))
    visible = resultado.stdout + resultado.stderr
    assert resultado.codigo in (1, 2)
    assert [d for d in (CLAVE_URL_RARA, "Traceback") if d in visible] == []


def test_bootstrap_url_del_migrador_malformada_no_se_repite_en_los_logs(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        _variables(
            base_limpia.url(),
            DATABASE_URL_MIGRADOR=f"postgresql+asyncpg://m:{CLAVE_URL_RARA}@127.0.0.1:abc/bd",
            DB_ROLES_SEPARADOS="true",
        ),
    )
    visible = resultado.stdout + resultado.stderr
    assert resultado.codigo in (1, 2)
    assert CLAVE_URL_RARA not in visible


def test_bootstrap_produccion_sin_roles_separados_es_configuracion_invalida_sin_valores(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        {
            "ENV": "production",
            "DATABASE_URL": base_limpia.url(),
            "APP_MASTER_KEY": APP_MASTER_KEY_PRUEBA,
            "JWT_SECRET": JWT_SECRET_PRUEBA,
            "CORS_ORIGENES": ORIGEN_PERMITIDO,
        },
    )
    (config,) = [log for log in resultado.logs() if log["evento"] == "config.invalida"]
    campos = [e["campo"] for e in config["errores"]]
    visible = resultado.stdout + resultado.stderr
    assert (resultado.codigo, "DB_ROLES_SEPARADOS" in campos) == (1, True)
    assert [
        d
        for d in (base_limpia.servidor.contrasena, APP_MASTER_KEY_PRUEBA, JWT_SECRET_PRUEBA)
        if d in visible
    ] == []


# ------------------------------------------------------------------ reversibilidad con datos


async def test_downgrade_base_con_datos_y_nuevo_bootstrap_reconstruye_todo(
    base_limpia: BasePrueba,
) -> None:
    await bootstrap_en_proceso(base_limpia.url())
    with base_limpia.conectar() as conexion:
        antes = conteos(conexion)
    motor = create_engine(base_limpia.url("postgresql+psycopg"), poolclass=pool.NullPool)
    try:
        for _ in range(2):
            with motor.connect() as conexion:
                command.downgrade(configuracion_alembic(conexion), "base")
                conexion.commit()
            with motor.connect() as conexion:
                command.upgrade(configuracion_alembic(conexion), "head")
                conexion.commit()
    finally:
        motor.dispose()
    aviso = AvisoCapturado()
    await bootstrap_en_proceso(base_limpia.url(), aviso)
    with base_limpia.conectar() as conexion:
        despues = conteos(conexion)
    assert despues == {**antes, "auditoria": despues["auditoria"]}
    assert len(aviso.mostrados) == 1


# ------------------------------------------------------------------ admin inicial


async def test_contrasena_generada_no_se_muestra_si_la_transaccion_de_semillas_falla(
    base_limpia: BasePrueba, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    generadas: list[str] = []
    original = CrearAdminInicial.ejecutar

    async def espiar(self: CrearAdminInicial, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        resultado = await original(self, *args, **kwargs)  # type: ignore[arg-type]
        if resultado.contrasena_generada:
            generadas.append(resultado.contrasena_generada)
        return resultado

    async def fallar(*args: object, **kwargs: object) -> None:
        raise RuntimeError(MENSAJE_FALLO)

    monkeypatch.setattr(CrearAdminInicial, "ejecutar", espiar)
    monkeypatch.setattr(orquestador, "registrar_auditoria_bootstrap", fallar)
    aviso = AvisoCapturado()
    with pytest.raises(FalloEnPaso) as error:
        await bootstrap_en_proceso(base_limpia.url(), aviso)
    salida = capfd.readouterr()
    with base_limpia.conectar() as conexion:
        usuarios = conexion.execute("SELECT count(*) FROM usuarios").fetchone()
    assert (aviso.mostrados, usuarios, len(generadas)) == ([], (0,), 1)
    assert error.value.paso == "semillas"
    assert [
        d
        for d in (generadas[0], base_limpia.servidor.contrasena)
        if d in salida.out + salida.err + str(error.value)
    ] == []


async def test_contrasena_definida_no_aparece_en_logs_ni_en_la_base_salvo_su_hash(
    base_limpia: BasePrueba, capfd: pytest.CaptureFixture[str]
) -> None:
    clave = "clave-definida-qa-" + secrets.token_hex(4)
    aviso = AvisoCapturado()
    await bootstrap_en_proceso(
        base_limpia.url(), aviso, admin_initial_password=clave, admin_initial_email="a@ejemplo.com"
    )
    salida = capfd.readouterr()
    with base_limpia.conectar() as conexion:
        volcado = conexion.execute(
            "SELECT (SELECT string_agg(detalle::text, '') FROM auditoria) || "
            "(SELECT string_agg(u::text, '') FROM usuarios u)"
        ).fetchone()
    assert aviso.mostrados == []
    assert volcado is not None
    assert clave not in salida.out + salida.err + volcado[0]


# ------------------------------------------------------------------ estados intermedios de la BD


async def test_bootstrap_sobre_base_a_medio_migrar_completa_y_audita_el_salto(
    base_limpia: BasePrueba,
) -> None:
    motor = create_engine(base_limpia.url("postgresql+psycopg"), poolclass=pool.NullPool)
    try:
        with motor.connect() as conexion:
            command.upgrade(configuracion_alembic(conexion), "0002_identidad_auditoria")
            conexion.commit()
    finally:
        motor.dispose()
    resultado = await bootstrap_en_proceso(base_limpia.url())
    with base_limpia.conectar() as conexion:
        migrada = conexion.execute(
            "SELECT detalle FROM auditoria WHERE accion = 'bd.migrada'"
        ).fetchall()
    assert resultado.revision_inicial == "0002_identidad_auditoria"
    assert migrada == [({"desde": "0002_identidad_auditoria", "hasta": resultado.revision_final},)]


def test_bootstrap_con_revision_desconocida_falla_con_codigo_2_sin_traza(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    variables = _variables(base_limpia.url())
    assert bootstrap_en_subproceso(backend_aislado, variables).codigo == 0
    with base_limpia.conectar() as conexion:
        conexion.execute("UPDATE alembic_version SET version_num = 'revision_del_futuro'")
    resultado = bootstrap_en_subproceso(backend_aislado, variables)
    fallo = [log for log in resultado.logs() if log["evento"] == "bootstrap.fallido"]
    visible = resultado.stdout + resultado.stderr
    assert resultado.codigo == 2
    assert [f["paso"] for f in fallo] == ["migraciones"]
    assert "Traceback" not in visible


@pytest.fixture
def base_postgres_restringida(postgres_efimero: ServidorPg) -> Iterator[None]:
    """Simula un servidor gestionado donde los roles de aplicación no entran a `postgres`."""
    with postgres_efimero.conectar() as conexion:
        conexion.execute("REVOKE CONNECT ON DATABASE postgres FROM PUBLIC")
    try:
        yield
    finally:
        with postgres_efimero.conectar() as conexion:
            conexion.execute("GRANT CONNECT ON DATABASE postgres TO PUBLIC")


def test_bootstrap_con_base_existente_no_necesita_acceso_a_la_base_postgres(
    backend_aislado: Path,
    base_limpia: BasePrueba,
    roles_separados: RolesPrueba,
    base_postgres_restringida: None,
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        {
            "DATABASE_URL": roles_separados.url_app,
            "DATABASE_URL_MIGRADOR": roles_separados.url_migrador,
            "DB_ROLES_SEPARADOS": "true",
        },
    )
    fallos = [
        (log["paso"], log["tipo_error"])
        for log in resultado.logs()
        if log["evento"] == "bootstrap.fallido"
    ]
    assert (resultado.codigo, fallos) == (0, [])
