"""`python -m app.bootstrap` contra PostgreSQL real (CA3 a CA7, CA12, Q7)."""

import asyncio
import json
import socket
from pathlib import Path
from typing import Final

import psycopg
import pytest
from argon2 import PasswordHasher

from app.infrastructure.db.bootstrap.bloqueo import CLAVE_LOCK
from app.infrastructure.db.bootstrap.migraciones import revision_head
from tests.integracion.conftest import BasePrueba, RolesPrueba
from tests.integracion.pg_efimero import ServidorPg
from tests.integracion.soporte_bd import (
    TABLAS_PROPIAS,
    ResultadoProceso,
    bootstrap_en_subproceso,
    bootstrap_en_subproceso_async,
    conteos,
    tablas_de,
)
from tests.soporte import APP_MASTER_KEY_PRUEBA, JWT_SECRET_PRUEBA, ORIGEN_PERMITIDO

MAX_PRIMERA_S: Final = 30
MAX_SEGUNDA_S: Final = 5
PREFIJO_ARGON2ID: Final = "$argon2id$v=19$m=65536,t=3,p=4$"
LINEA_CONTRASENA: Final = "Contraseña inicial del administrador "
CONTRASENA_DEFINIDA: Final = "contrasena-definida-de-prueba"


def _variables(url: str, **extra: str) -> dict[str, str]:
    return {"DATABASE_URL": url, **extra}


def _contrasena_mostrada(resultado: ResultadoProceso) -> str:
    """Extrae la contraseña del bloque de stderr (falla si no está exactamente una vez)."""
    lineas = [linea for linea in resultado.stderr.splitlines() if LINEA_CONTRASENA in linea]
    assert len(lineas) == 1
    return lineas[0].rsplit(": ", 1)[1]


def _puerto_cerrado() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# ------------------------------------------------------------------ CA3, CA4


def test_bootstrap_base_vacia_deja_todo_listo(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    resultado = bootstrap_en_subproceso(backend_aislado, _variables(base_limpia.url()))
    with base_limpia.conectar() as conexion:
        propias = tablas_de(conexion, "public")
        cola = tablas_de(conexion, "procrastinate")
        checkpoints = tablas_de(conexion, "langgraph")
        revision = conexion.execute("SELECT version_num FROM alembic_version").fetchall()
        extensiones = {f[0] for f in conexion.execute("SELECT extname FROM pg_extension")}
    assert (resultado.codigo, resultado.duracion_s <= MAX_PRIMERA_S) == (0, True)
    assert (
        propias,
        len(cola),
        checkpoints,
        revision,
        {"citext", "pgcrypto", "pg_trgm"} <= extensiones,
    ) == (
        {*TABLAS_PROPIAS, "alembic_version"},
        4,
        {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"},
        [(revision_head(),)],
        True,
    )


def test_bootstrap_segunda_ejecucion_no_inserta_nada_ni_muestra_contrasena(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    variables = _variables(base_limpia.url())
    primera = bootstrap_en_subproceso(backend_aislado, variables)
    with base_limpia.conectar() as conexion:
        antes = conteos(conexion)
    segunda = bootstrap_en_subproceso(backend_aislado, variables)
    with base_limpia.conectar() as conexion:
        despues = conteos(conexion)
    assert (primera.codigo, segunda.codigo, segunda.duracion_s <= MAX_SEGUNDA_S) == (0, 0, True)
    assert (despues, LINEA_CONTRASENA in segunda.stderr, segunda.stderr) == (antes, False, "")


def test_bootstrap_eventos_estructurados(backend_aislado: Path, base_limpia: BasePrueba) -> None:
    resultado = bootstrap_en_subproceso(backend_aislado, _variables(base_limpia.url()))
    logs = resultado.logs()
    pasos = [log["paso"] for log in logs if log["evento"] == "bootstrap.paso"]
    (completado,) = [log for log in logs if log["evento"] == "bootstrap.completado"]
    (admin,) = [log for log in logs if log["evento"] == "bootstrap.admin_inicial_creado"]
    assert (resultado.eventos()[0], "bd.rol_unico" in resultado.eventos()) == (
        "bootstrap.inicio",
        True,
    )
    assert pasos == ["configuracion", "espera", "creacion", "migraciones", "langgraph", "semillas"]
    assert (completado["revision"], completado["insertadas"]["roles"]) == (revision_head(), 3)
    assert (admin["generada_aleatoriamente"], admin["email"]) == (True, "a***@agente-correo.local")


# ------------------------------------------------------------------ CA5


async def test_bootstrap_dos_procesos_concurrentes(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    variables = _variables(base_limpia.url())
    resultados = await asyncio.gather(
        bootstrap_en_subproceso_async(backend_aislado, variables),
        bootstrap_en_subproceso_async(backend_aislado, variables),
    )
    with base_limpia.conectar() as conexion:
        cuentas = conteos(conexion)
        migradas = conexion.execute(
            "SELECT count(*) FROM auditoria WHERE accion = 'bd.migrada'"
        ).fetchone()
    mostradas = sum(r.stderr.count(LINEA_CONTRASENA) for r in resultados)
    assert [r.codigo for r in resultados] == [0, 0]
    assert (cuentas["usuarios"], cuentas["roles"], cuentas["agentes"], migradas, mostradas) == (
        1,
        3,
        5,
        (1,),
        1,
    )


# ------------------------------------------------------------------ CA6


def test_bootstrap_lock_ocupado_termina_con_codigo_2(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    with psycopg.connect(base_limpia.url("postgresql"), autocommit=True) as retenedor:
        retenedor.execute("SELECT pg_advisory_lock(%s)", (CLAVE_LOCK,))
        resultado = bootstrap_en_subproceso(
            backend_aislado,
            _variables(base_limpia.url(), DB_BOOTSTRAP_LOCK_TIMEOUT_S="1"),
        )
    assert (resultado.codigo, "bootstrap.lock_timeout" in resultado.eventos()) == (2, True)


def test_bootstrap_bd_caida_termina_con_codigo_2_sin_credenciales(backend_aislado: Path) -> None:
    clave = "clave%40secreta-de-prueba"
    url = f"postgresql+asyncpg://usuario_qa:{clave}@127.0.0.1:{_puerto_cerrado()}/bd_qa"
    resultado = bootstrap_en_subproceso(backend_aislado, _variables(url, DB_ESPERA_MAX_S="1"))
    visible = resultado.stdout + resultado.stderr
    assert (resultado.codigo, "bootstrap.bd_no_disponible" in resultado.eventos()) == (2, True)
    assert [d for d in ("usuario_qa", "clave", "secreta", "bd_qa") if d in visible] == []


def test_bootstrap_credencial_rechazada_no_filtra_la_contrasena(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    clave = "p@ss:w%rd-de-prueba"
    url = base_limpia.url(usuario="postgres", contrasena=clave)
    resultado = bootstrap_en_subproceso(backend_aislado, _variables(url, DB_ESPERA_MAX_S="2"))
    visible = resultado.stdout + resultado.stderr
    assert (resultado.codigo, "bootstrap.autenticacion_rechazada" in resultado.eventos()) == (
        2,
        True,
    )
    assert [d for d in (clave, "w%rd", "p%40ss", base_limpia.nombre) if d in visible] == []


# ------------------------------------------------------------------ CA7


def test_bootstrap_auto_create_crea_la_base(
    backend_aislado: Path, postgres_efimero: ServidorPg, nombre_base_libre: str
) -> None:
    url = postgres_efimero.url(nombre_base_libre, "postgresql+asyncpg")
    resultado = bootstrap_en_subproceso(backend_aislado, _variables(url, DB_AUTO_CREATE="true"))
    with postgres_efimero.conectar() as conexion:
        existe = conexion.execute(
            "SELECT count(*) FROM pg_database WHERE datname = %s", (nombre_base_libre,)
        ).fetchone()
    assert (resultado.codigo, existe) == (0, (1,))


def test_bootstrap_sin_auto_create_y_base_inexistente_falla(
    backend_aislado: Path, postgres_efimero: ServidorPg, nombre_base_libre: str
) -> None:
    url = postgres_efimero.url(nombre_base_libre, "postgresql+asyncpg")
    resultado = bootstrap_en_subproceso(backend_aislado, _variables(url, DB_AUTO_CREATE="false"))
    with postgres_efimero.conectar() as conexion:
        existe = conexion.execute(
            "SELECT count(*) FROM pg_database WHERE datname = %s", (nombre_base_libre,)
        ).fetchone()
    assert (resultado.codigo, "bootstrap.base_inexistente" in resultado.eventos(), existe) == (
        2,
        True,
        (0,),
    )


@pytest.mark.parametrize(
    "nombre", ["con-guion", "con%22comillas", "con%3Bpunto_y_coma", "con%20espacio", "a" * 64]
)
def test_bootstrap_nombre_de_base_invalido_falla_sin_ejecutar_sql(
    backend_aislado: Path, postgres_efimero: ServidorPg, nombre: str
) -> None:
    url = postgres_efimero.url(nombre, "postgresql+asyncpg")
    resultado = bootstrap_en_subproceso(backend_aislado, _variables(url, DB_AUTO_CREATE="true"))
    pasos = [log["paso"] for log in resultado.logs() if log["evento"] == "bootstrap.paso"]
    assert (resultado.codigo, "bootstrap.nombre_base_invalido" in resultado.eventos(), pasos) == (
        2,
        True,
        ["configuracion"],
    )


# ------------------------------------------------------------------ CA12


def test_bootstrap_admin_con_contrasena_generada_se_muestra_una_sola_vez(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    resultado = bootstrap_en_subproceso(backend_aislado, _variables(base_limpia.url()))
    contrasena = _contrasena_mostrada(resultado)
    with base_limpia.conectar() as conexion:
        usuario = conexion.execute(
            "SELECT hash_password, requiere_cambio_password FROM usuarios"
        ).fetchone()
        detalles = json.dumps(
            [f[0] for f in conexion.execute("SELECT detalle FROM auditoria").fetchall()]
        )
    assert usuario is not None
    assert (
        len(contrasena),
        resultado.stderr.count(contrasena),
        contrasena in resultado.stdout,
        contrasena in detalles,
    ) == (24, 1, False, False)
    assert (
        usuario[0].startswith(PREFIJO_ARGON2ID),
        PasswordHasher().verify(usuario[0], contrasena),
        usuario[1],
    ) == (True, True, True)


def test_bootstrap_admin_con_contrasena_definida_no_imprime_nada(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        _variables(
            base_limpia.url(),
            ADMIN_INITIAL_EMAIL="Admin@Ejemplo.com",
            ADMIN_INITIAL_PASSWORD=CONTRASENA_DEFINIDA,
        ),
    )
    with base_limpia.conectar() as conexion:
        usuario = conexion.execute(
            "SELECT email::text, hash_password, requiere_cambio_password FROM usuarios"
        ).fetchone()
        roles = conexion.execute(
            "SELECT r.nombre FROM usuarios_roles ur JOIN roles r ON r.id = ur.rol_id"
        ).fetchall()
    assert usuario is not None
    assert (resultado.codigo, resultado.stderr, CONTRASENA_DEFINIDA in resultado.stdout) == (
        0,
        "",
        False,
    )
    assert (
        usuario[0],
        PasswordHasher().verify(usuario[1], CONTRASENA_DEFINIDA),
        usuario[2],
        roles,
    ) == ("admin@ejemplo.com", True, True, [("admin",)])


def test_bootstrap_con_usuarios_existentes_no_crea_admin(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    bootstrap_en_subproceso(backend_aislado, _variables(base_limpia.url()))
    with base_limpia.conectar() as conexion:
        conexion.execute("UPDATE usuarios SET email = 'otro@ejemplo.com'")
    segunda = bootstrap_en_subproceso(
        backend_aislado, _variables(base_limpia.url(), ADMIN_INITIAL_EMAIL="nuevo@ejemplo.com")
    )
    with base_limpia.conectar() as conexion:
        emails = conexion.execute("SELECT email::text FROM usuarios").fetchall()
    assert (segunda.codigo, emails, segunda.stderr) == (0, [("otro@ejemplo.com",)], "")


def _variables_produccion(roles: RolesPrueba, **extra: str) -> dict[str, str]:
    return {
        "ENV": "production",
        "DATABASE_URL": roles.url_app,
        "DATABASE_URL_MIGRADOR": roles.url_migrador,
        "DB_ROLES_SEPARADOS": "true",
        "APP_MASTER_KEY": APP_MASTER_KEY_PRUEBA,
        "JWT_SECRET": JWT_SECRET_PRUEBA,
        "CORS_ORIGENES": ORIGEN_PERMITIDO,
        **extra,
    }


def test_bootstrap_produccion_sin_usuarios_ni_email_falla(
    backend_aislado: Path, base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    resultado = bootstrap_en_subproceso(backend_aislado, _variables_produccion(roles_separados))
    with base_limpia.conectar() as conexion:
        usuarios = conexion.execute("SELECT count(*) FROM usuarios").fetchone()
    assert (resultado.codigo, "bootstrap.admin_sin_email" in resultado.eventos(), usuarios) == (
        2,
        True,
        (0,),
    )


def test_bootstrap_produccion_con_email_termina_bien(
    backend_aislado: Path, roles_separados: RolesPrueba
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        _variables_produccion(roles_separados, ADMIN_INITIAL_EMAIL="admin@ejemplo.com"),
    )
    assert (resultado.codigo, resultado.stderr.count(LINEA_CONTRASENA)) == (0, 1)


def test_bootstrap_produccion_con_auto_create_es_configuracion_invalida(
    backend_aislado: Path, roles_separados: RolesPrueba
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado, _variables_produccion(roles_separados, DB_AUTO_CREATE="true")
    )
    assert (resultado.codigo, resultado.eventos()) == (1, ["config.invalida"])


def test_bootstrap_email_con_salto_de_linea_es_configuracion_invalida(
    backend_aislado: Path, base_limpia: BasePrueba
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        _variables(base_limpia.url(), ADMIN_INITIAL_EMAIL="admin@ejemplo.com\nBcc: x@y.com"),
    )
    assert (resultado.codigo, "x@y.com" in resultado.stdout) == (1, False)
