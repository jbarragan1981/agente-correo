"""Roles separados y verificación de privilegios del bootstrap (CA14, ADR-0008)."""

import os
import shutil
import subprocess  # nosec B404 - sh y psql locales con lista de argumentos
from pathlib import Path
from typing import Final

import psycopg
import pytest
from psycopg import errors, sql

from app.infrastructure.db.bootstrap.errores import PrivilegiosInseguros
from tests.integracion.conftest import RAIZ_BACKEND, BasePrueba, RolesPrueba
from tests.integracion.soporte_bd import (
    bootstrap_en_proceso,
    bootstrap_en_subproceso,
    tablas_de,
)

SCRIPT_ROLES: Final = RAIZ_BACKEND.parent / "infra" / "sql" / "00-roles.sh"
ROLES_SQL: Final = RAIZ_BACKEND.parent / "infra" / "sql" / "roles.sql"
ENCOLAR: Final = (
    "SELECT procrastinate.procrastinate_defer_jobs_v1(ARRAY[ROW('cola', 'tarea', 0, NULL, NULL, "
    "'{}'::jsonb, NULL)::procrastinate.procrastinate_job_to_defer_v1])"
)


async def _bootstrap_separado(roles: RolesPrueba, url_app: str | None = None) -> None:
    await bootstrap_en_proceso(
        url_app or roles.url_app,
        database_url_migrador=roles.url_migrador,
        db_roles_separados=True,
    )


async def _comprobaciones_fallidas(roles: RolesPrueba, url_app: str) -> tuple[str, ...]:
    with pytest.raises(PrivilegiosInseguros) as error:
        await _bootstrap_separado(roles, url_app)
    return error.value.comprobaciones


def _app(base: BasePrueba, roles: RolesPrueba) -> psycopg.Connection:  # type: ignore[type-arg]
    return psycopg.connect(
        base.url("postgresql", "agente_app", roles.contrasena_app), autocommit=True
    )


# ------------------------------------------------------------------ modo separado correcto


def test_roles_bootstrap_como_migrador_termina_con_codigo_0(
    backend_aislado: Path, base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        {
            "DATABASE_URL": roles_separados.url_app,
            "DATABASE_URL_MIGRADOR": roles_separados.url_migrador,
            "DB_ROLES_SEPARADOS": "true",
        },
    )
    with base_limpia.conectar() as conexion:
        propietarios = conexion.execute(
            "SELECT DISTINCT tableowner FROM pg_tables "
            "WHERE schemaname IN ('public', 'procrastinate', 'langgraph')"
        ).fetchall()
    visible = resultado.stdout + resultado.stderr
    assert (resultado.codigo, "bd.rol_unico" in resultado.eventos(), propietarios) == (
        0,
        False,
        [("agente_migrador",)],
    )
    assert [
        c
        for c in (roles_separados.contrasena_app, roles_separados.contrasena_migrador)
        if c in visible
    ] == []


async def test_roles_app_hace_dml_en_los_tres_esquemas(
    base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    await _bootstrap_separado(roles_separados)
    with _app(base_limpia, roles_separados) as conexion:
        conexion.execute("UPDATE configuracion SET descripcion = descripcion")
        conexion.execute("INSERT INTO langgraph.checkpoint_migrations (v) VALUES (9999)")
        conexion.execute("DELETE FROM langgraph.checkpoint_migrations WHERE v = 9999")
        conexion.execute("SET search_path = procrastinate")
        ids = conexion.execute(ENCOLAR).fetchone()
        conexion.execute("DELETE FROM procrastinate_jobs")
    assert ids is not None
    assert len(ids[0]) == 1


@pytest.mark.parametrize("esquema", ["public", "procrastinate", "langgraph"])
async def test_roles_app_no_puede_crear_tablas(
    base_limpia: BasePrueba, roles_separados: RolesPrueba, esquema: str
) -> None:
    await _bootstrap_separado(roles_separados)
    with (
        _app(base_limpia, roles_separados) as conexion,
        pytest.raises(errors.InsufficientPrivilege),
    ):
        conexion.execute(
            sql.SQL("CREATE TABLE {}.intrusa (id int)").format(sql.Identifier(esquema))
        )


async def test_roles_app_no_puede_crear_esquemas(
    base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    await _bootstrap_separado(roles_separados)
    with (
        _app(base_limpia, roles_separados) as conexion,
        pytest.raises(errors.InsufficientPrivilege),
    ):
        conexion.execute("CREATE SCHEMA intruso")


# ------------------------------------------------------------------ casos inseguros


def test_roles_app_superusuario_termina_con_codigo_2_sin_credenciales(
    backend_aislado: Path, base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    resultado = bootstrap_en_subproceso(
        backend_aislado,
        {
            "DATABASE_URL": base_limpia.url(),
            "DATABASE_URL_MIGRADOR": roles_separados.url_migrador,
            "DB_ROLES_SEPARADOS": "true",
        },
    )
    (evento,) = [
        log for log in resultado.logs() if log["evento"] == "bootstrap.privilegios_inseguros"
    ]
    visible = resultado.stdout + resultado.stderr
    assert (resultado.codigo, "app.superusuario" in evento["comprobaciones"]) == (2, True)
    assert [
        c
        for c in (
            base_limpia.servidor.contrasena,
            roles_separados.contrasena_migrador,
            "agente_migrador",
            base_limpia.nombre,
        )
        if c in visible
    ] == []


async def test_roles_app_con_create_en_public(
    base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    with base_limpia.conectar() as conexion:
        conexion.execute("GRANT CREATE ON SCHEMA public TO agente_app")
    fallidas = await _comprobaciones_fallidas(roles_separados, roles_separados.url_app)
    assert fallidas == ("app.create_en_public",)


async def test_roles_app_con_create_en_la_base(
    base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    with base_limpia.conectar() as conexion:
        conexion.execute(
            sql.SQL("GRANT CREATE ON DATABASE {} TO agente_app").format(
                sql.Identifier(base_limpia.nombre)
            )
        )
    fallidas = await _comprobaciones_fallidas(roles_separados, roles_separados.url_app)
    assert fallidas == ("app.create_en_base",)


async def test_roles_app_igual_al_migrador(roles_separados: RolesPrueba) -> None:
    fallidas = await _comprobaciones_fallidas(roles_separados, roles_separados.url_migrador)
    assert {"app.mismo_rol_que_migrador", "app.propietario_de_tablas"} <= set(fallidas)


async def test_roles_update_directo_sobre_auditoria_lo_revoca_el_bootstrap(
    base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    await _bootstrap_separado(roles_separados)
    with base_limpia.conectar() as conexion:
        conexion.execute("GRANT UPDATE, TRUNCATE ON auditoria TO agente_app")
    await _bootstrap_separado(roles_separados)
    with _app(base_limpia, roles_separados) as conexion:
        privilegios = conexion.execute(
            "SELECT has_table_privilege('auditoria', 'UPDATE'), "
            "has_table_privilege('auditoria', 'TRUNCATE')"
        ).fetchone()
    assert privilegios == (False, False)


async def test_roles_update_heredado_sobre_auditoria_falla_cerrado(
    base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    await _bootstrap_separado(roles_separados)
    intruso = sql.Identifier(f"intruso_{base_limpia.nombre}")
    with base_limpia.conectar() as conexion:
        conexion.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(intruso))
        try:
            conexion.execute(sql.SQL("GRANT UPDATE ON auditoria TO {}").format(intruso))
            conexion.execute(sql.SQL("GRANT {} TO agente_app").format(intruso))
            fallidas = await _comprobaciones_fallidas(roles_separados, roles_separados.url_app)
        finally:
            conexion.execute(sql.SQL("REVOKE ALL ON auditoria FROM {}").format(intruso))
            conexion.execute(sql.SQL("DROP ROLE {}").format(intruso))
    assert fallidas == ("app.update_en_auditoria",)


async def test_roles_migrador_superusuario(
    base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    with pytest.raises(PrivilegiosInseguros) as error:
        await bootstrap_en_proceso(
            roles_separados.url_app,
            database_url_migrador=base_limpia.url(),
            db_roles_separados=True,
        )
    assert error.value.comprobaciones[0] == "migrador.superusuario"


# ------------------------------------------------------------------ scripts de infra/sql


def test_roles_sql_es_idempotente(base_limpia: BasePrueba) -> None:
    with base_limpia.conectar() as conexion:
        for _ in range(2):
            conexion.execute(ROLES_SQL.read_text(encoding="utf-8"))  # type: ignore[arg-type]
        atributos = conexion.execute(
            "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin FROM pg_roles "
            "WHERE rolname LIKE 'agente\\_%' ORDER BY rolname"
        ).fetchall()
    assert atributos == [
        (rol, False, False, False, True)
        for rol in ("agente_app", "agente_lectura", "agente_migrador")
    ]


def test_roles_script_asigna_contrasenas_sin_imprimirlas(
    base_limpia: BasePrueba, tmp_path: Path
) -> None:
    psql = shutil.which("psql") or str(
        next(Path("/usr/lib/postgresql").glob("*/bin/psql"), Path("psql"))
    )
    enlaces = tmp_path / "bin"
    enlaces.mkdir()
    (enlaces / "psql").symlink_to(psql)
    migrador, app = "migrador-script-de-prueba", "app-script-de-prueba"
    servidor = base_limpia.servidor
    resultado = subprocess.run(  # noqa: S603 - argumentos fijos, sin shell
        ["/bin/sh", str(SCRIPT_ROLES)],
        env={
            "PATH": f"{enlaces}:{os.environ['PATH']}",
            "PGHOST": servidor.host,
            "PGPORT": str(servidor.puerto),
            "PGPASSWORD": servidor.contrasena,
            "POSTGRES_USER": servidor.usuario,
            "POSTGRES_DB": base_limpia.nombre,
            "ROLES_SQL": str(ROLES_SQL),
            "AGENTE_MIGRADOR_PASSWORD": migrador,
            "AGENTE_APP_PASSWORD": app,
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    with psycopg.connect(
        base_limpia.url("postgresql", "agente_app", app), autocommit=True
    ) as conexion:
        conectado = conexion.execute("SELECT current_user").fetchone()
    with base_limpia.conectar() as conexion:
        tablas = tablas_de(conexion, "public")
    visible = resultado.stdout + resultado.stderr
    assert (resultado.returncode, conectado, migrador in visible, app in visible) == (
        0,
        ("agente_app",),
        False,
        False,
    )
    assert tablas == set()


def test_roles_script_falla_sin_contrasenas() -> None:
    resultado = subprocess.run(  # noqa: S603 - argumentos fijos, sin shell
        ["/bin/sh", str(SCRIPT_ROLES)],
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert (resultado.returncode != 0, "AGENTE_MIGRADOR_PASSWORD" in resultado.stderr) == (
        True,
        True,
    )
