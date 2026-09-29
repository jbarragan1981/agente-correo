"""Revisión de seguridad E0.2: S-M1 (pertenencias y atributos peligrosos) y S-B1 (checkpointer).

Cada caso inseguro reproduce la concesión, ejecuta `python -m app.bootstrap` en un subproceso
y comprueba que falla cerrado (código 2, `bootstrap.privilegios_inseguros`) sin filtrar
contraseñas. Los roles son globales del clúster: cada prueba deshace su concesión.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Final, LiteralString

import psycopg
import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import errors, sql

from app.infrastructure.db.bootstrap.errores import PrivilegiosInseguros
from app.infrastructure.db.bootstrap.privilegios import ROLES_DE_SERVIDOR
from app.infrastructure.db.bootstrap.urls import conninfo
from tests.integracion.conftest import BasePrueba, RolesPrueba
from tests.integracion.soporte_bd import (
    ResultadoProceso,
    bootstrap_en_proceso,
    bootstrap_en_subproceso,
)

ATRIBUTOS_MIGRADOR: Final[dict[LiteralString, str]] = {
    "CREATEROLE": "migrador.crea_roles",
    "CREATEDB": "migrador.crea_bases",
    "BYPASSRLS": "migrador.salta_rls",
}


def _bootstrap(backend: Path, roles: RolesPrueba) -> ResultadoProceso:
    return bootstrap_en_subproceso(
        backend,
        {
            "DATABASE_URL": roles.url_app,
            "DATABASE_URL_MIGRADOR": roles.url_migrador,
            "DB_ROLES_SEPARADOS": "true",
        },
    )


def _comprobaciones(resultado: ResultadoProceso) -> list[str]:
    eventos = [
        log for log in resultado.logs() if log["evento"] == "bootstrap.privilegios_inseguros"
    ]
    assert len(eventos) == 1
    return list(eventos[0]["comprobaciones"])


def _sin_fugas(resultado: ResultadoProceso, base: BasePrueba, roles: RolesPrueba) -> list[str]:
    visible = resultado.stdout + resultado.stderr
    secretos = (roles.contrasena_app, roles.contrasena_migrador, base.servidor.contrasena)
    return [secreto for secreto in secretos if secreto in visible]


@pytest.fixture
def superusuario(base_limpia: BasePrueba) -> Iterator[psycopg.Connection]:  # type: ignore[type-arg]
    with base_limpia.conectar() as conexion:
        yield conexion


# ------------------------------------------------------------------ S-M1: agente_app


def test_app_miembro_del_migrador_sin_herencia_falla_cerrado(
    backend_aislado: Path,
    base_limpia: BasePrueba,
    roles_separados: RolesPrueba,
    superusuario: psycopg.Connection,  # type: ignore[type-arg]
) -> None:
    superusuario.execute("GRANT agente_migrador TO agente_app WITH INHERIT FALSE")
    try:
        with psycopg.connect(
            base_limpia.url("postgresql", "agente_app", roles_separados.contrasena_app),
            autocommit=True,
        ) as app:
            app.execute("SET ROLE agente_migrador")
            reproducido = app.execute("SELECT current_user").fetchone()
        resultado = _bootstrap(backend_aislado, roles_separados)
    finally:
        superusuario.execute("REVOKE agente_migrador FROM agente_app")
    assert reproducido == ("agente_migrador",)
    assert (resultado.codigo, "app.miembro_del_migrador" in _comprobaciones(resultado)) == (
        2,
        True,
    )
    assert _sin_fugas(resultado, base_limpia, roles_separados) == []


@pytest.mark.parametrize("rol", ROLES_DE_SERVIDOR)
def test_app_con_rol_de_servidor_falla_cerrado(
    backend_aislado: Path,
    base_limpia: BasePrueba,
    roles_separados: RolesPrueba,
    superusuario: psycopg.Connection,  # type: ignore[type-arg]
    rol: str,
) -> None:
    concesion = sql.SQL("GRANT {} TO agente_app").format(sql.Identifier(rol))
    superusuario.execute(concesion)
    try:
        resultado = _bootstrap(backend_aislado, roles_separados)
    finally:
        superusuario.execute(sql.SQL("REVOKE {} FROM agente_app").format(sql.Identifier(rol)))
    assert (resultado.codigo, _comprobaciones(resultado)) == (2, ["app.rol_de_servidor"])
    assert _sin_fugas(resultado, base_limpia, roles_separados) == []


# ------------------------------------------------------------------ S-M1: agente_migrador


@pytest.mark.parametrize(("atributo", "comprobacion"), sorted(ATRIBUTOS_MIGRADOR.items()))
def test_migrador_con_atributo_peligroso_falla_cerrado(
    backend_aislado: Path,
    base_limpia: BasePrueba,
    roles_separados: RolesPrueba,
    superusuario: psycopg.Connection,  # type: ignore[type-arg]
    atributo: LiteralString,
    comprobacion: str,
) -> None:
    superusuario.execute(sql.SQL("ALTER ROLE agente_migrador {}").format(sql.SQL(atributo)))
    try:
        resultado = _bootstrap(backend_aislado, roles_separados)
    finally:
        superusuario.execute(
            sql.SQL("ALTER ROLE agente_migrador {}").format(sql.SQL(f"NO{atributo}"))
        )
    assert (resultado.codigo, _comprobaciones(resultado)) == (2, [comprobacion])
    assert _sin_fugas(resultado, base_limpia, roles_separados) == []


@pytest.mark.parametrize("rol", ROLES_DE_SERVIDOR)
def test_migrador_con_rol_de_servidor_falla_cerrado(
    backend_aislado: Path,
    base_limpia: BasePrueba,
    roles_separados: RolesPrueba,
    superusuario: psycopg.Connection,  # type: ignore[type-arg]
    rol: str,
) -> None:
    superusuario.execute(sql.SQL("GRANT {} TO agente_migrador").format(sql.Identifier(rol)))
    try:
        resultado = _bootstrap(backend_aislado, roles_separados)
    finally:
        superusuario.execute(sql.SQL("REVOKE {} FROM agente_migrador").format(sql.Identifier(rol)))
    assert (resultado.codigo, _comprobaciones(resultado)) == (2, ["migrador.rol_de_servidor"])
    assert _sin_fugas(resultado, base_limpia, roles_separados) == []


# ------------------------------------------------------------------ S-B1: checkpointer


async def _bootstrap_separado(roles: RolesPrueba) -> None:
    await bootstrap_en_proceso(
        roles.url_app, database_url_migrador=roles.url_migrador, db_roles_separados=True
    )


def _app(base: BasePrueba, roles: RolesPrueba) -> psycopg.Connection:  # type: ignore[type-arg]
    return psycopg.connect(
        base.url("postgresql", "agente_app", roles.contrasena_app), autocommit=True
    )


@pytest.mark.parametrize(
    "sentencia",
    [
        "INSERT INTO langgraph.checkpoint_migrations (v) VALUES (9999)",
        "UPDATE langgraph.checkpoint_migrations SET v = v",
        "DELETE FROM langgraph.checkpoint_migrations",
        "TRUNCATE langgraph.checkpoint_migrations",
    ],
)
async def test_app_no_escribe_en_checkpoint_migrations(
    base_limpia: BasePrueba, roles_separados: RolesPrueba, sentencia: str
) -> None:
    await _bootstrap_separado(roles_separados)
    with _app(base_limpia, roles_separados) as app, pytest.raises(errors.InsufficientPrivilege):
        app.execute(sentencia)  # type: ignore[arg-type]


async def test_app_usa_el_checkpointer_sin_setup(
    base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    await _bootstrap_separado(roles_separados)
    dsn = conninfo(roles_separados.url_app, options="-csearch_path=langgraph")
    config = {"configurable": {"thread_id": "hilo-prueba", "checkpoint_ns": ""}}
    checkpoint = empty_checkpoint()
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        guardado = await saver.aput(config, checkpoint, {"source": "input", "step": -1}, {})  # type: ignore[arg-type]
        await saver.aput_writes(guardado, [("canal", "valor")], "tarea-1")
        leido = await saver.aget_tuple(guardado)
    assert leido is not None
    assert (leido.checkpoint["id"], [w[1:] for w in leido.pending_writes or []]) == (
        checkpoint["id"],
        [("canal", "valor")],
    )


async def test_app_con_dml_heredado_en_checkpoint_migrations_falla_cerrado(
    base_limpia: BasePrueba,
    roles_separados: RolesPrueba,
    superusuario: psycopg.Connection,  # type: ignore[type-arg]
) -> None:
    await _bootstrap_separado(roles_separados)
    intruso = sql.Identifier(f"intruso_lg_{base_limpia.nombre}")
    superusuario.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(intruso))
    try:
        superusuario.execute(
            sql.SQL("GRANT INSERT ON langgraph.checkpoint_migrations TO {}").format(intruso)
        )
        superusuario.execute(sql.SQL("GRANT {} TO agente_app").format(intruso))
        with pytest.raises(PrivilegiosInseguros) as error:
            await _bootstrap_separado(roles_separados)
    finally:
        superusuario.execute(
            sql.SQL("REVOKE ALL ON langgraph.checkpoint_migrations FROM {}").format(intruso)
        )
        superusuario.execute(sql.SQL("DROP ROLE {}").format(intruso))
    assert error.value.comprobaciones == ("app.modifica_checkpoint_migrations",)


async def test_app_con_dml_directo_en_checkpoint_migrations_lo_revoca_el_bootstrap(
    base_limpia: BasePrueba,
    roles_separados: RolesPrueba,
    superusuario: psycopg.Connection,  # type: ignore[type-arg]
) -> None:
    await _bootstrap_separado(roles_separados)
    superusuario.execute(
        "GRANT INSERT, UPDATE, DELETE ON langgraph.checkpoint_migrations TO agente_app"
    )
    await _bootstrap_separado(roles_separados)
    with _app(base_limpia, roles_separados) as app:
        fila = app.execute(
            "SELECT has_table_privilege('langgraph.checkpoint_migrations', "
            "'INSERT, UPDATE, DELETE, TRUNCATE')"
        ).fetchone()
    assert fila == (False,)
