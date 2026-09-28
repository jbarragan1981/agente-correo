"""Migraciones reversibles y coherentes con los modelos (CA8, CA9)."""

from collections.abc import Iterator
from typing import Final

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, create_engine, pool

from app.infrastructure.db.bootstrap.migraciones import configuracion_alembic, revision_head
from app.infrastructure.db.modelos import Base
from tests.integracion.conftest import BasePrueba, RolesPrueba
from tests.integracion.soporte_bd import TABLAS_PROPIAS, tablas_de

REVISIONES: Final = [
    rev.revision
    for rev in reversed(list(ScriptDirectory.from_config(configuracion_alembic()).walk_revisions()))
]
TABLAS_PROCRASTINATE: Final = {
    "procrastinate_jobs",
    "procrastinate_events",
    "procrastinate_periodic_defers",
    "procrastinate_workers",
}
EXTENSIONES: Final = {"citext", "pgcrypto", "pg_trgm"}
FUNCIONES_PROPIAS: Final = {
    "agente_conceder_privilegios",
    "auditoria_calcular_hash",
    "auditoria_encadenar",
    "auditoria_inmutable",
    "versiones_prompt_inmutable",
}


@pytest.fixture
def motor(base_limpia: BasePrueba) -> Iterator[Engine]:
    """Motor síncrono psycopg contra la base limpia (como superusuario, modo rol único)."""
    motor = create_engine(base_limpia.url("postgresql+psycopg"), poolclass=pool.NullPool)
    try:
        yield motor
    finally:
        motor.dispose()


def _alembic(motor: Engine, operacion: str, destino: str) -> None:
    """Ejecuta `upgrade`/`downgrade` con la conexión en `config.attributes`."""
    with motor.connect() as conexion:
        getattr(command, operacion)(configuracion_alembic(conexion), destino)
        conexion.commit()


def _revision(motor: Engine) -> str | None:
    with motor.connect() as conexion:
        return MigrationContext.configure(conexion).get_current_revision()


def _extensiones(base: BasePrueba) -> set[str]:
    with base.conectar() as conexion:
        return {str(fila[0]) for fila in conexion.execute("SELECT extname FROM pg_extension")}


def _funciones_publicas(base: BasePrueba) -> set[str]:
    with base.conectar() as conexion:
        filas = conexion.execute(
            "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND p.proname = ANY(%s)",
            (sorted(FUNCIONES_PROPIAS),),
        )
        return {str(fila[0]) for fila in filas}


def _esquemas(base: BasePrueba) -> set[str]:
    with base.conectar() as conexion:
        filas = conexion.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname IN ('procrastinate', 'langgraph')"
        )
        return {str(fila[0]) for fila in filas}


def test_migraciones_upgrade_head_crea_todo(motor: Engine, base_limpia: BasePrueba) -> None:
    _alembic(motor, "upgrade", "head")
    with base_limpia.conectar() as conexion:
        propias, cola = tablas_de(conexion, "public"), tablas_de(conexion, "procrastinate")
    assert (
        _revision(motor),
        propias,
        cola,
        _extensiones(base_limpia) >= EXTENSIONES,
        _funciones_publicas(base_limpia),
    ) == (
        revision_head(),
        {*TABLAS_PROPIAS, "alembic_version"},
        TABLAS_PROCRASTINATE,
        True,
        FUNCIONES_PROPIAS,
    )


@pytest.mark.parametrize("indice", range(len(REVISIONES)), ids=REVISIONES)
def test_migraciones_escalera_upgrade_downgrade_upgrade(motor: Engine, indice: int) -> None:
    revision = REVISIONES[indice]
    anterior = REVISIONES[indice - 1] if indice else None
    _alembic(motor, "upgrade", revision)
    _alembic(motor, "downgrade", "-1")
    tras_bajar = _revision(motor)
    _alembic(motor, "upgrade", revision)
    assert (tras_bajar, _revision(motor)) == (anterior, revision)


def test_migraciones_downgrade_base_deja_la_base_limpia(
    motor: Engine, base_limpia: BasePrueba
) -> None:
    _alembic(motor, "upgrade", "head")
    _alembic(motor, "downgrade", "base")
    with base_limpia.conectar() as conexion:
        propias = tablas_de(conexion, "public")
    assert (
        propias,
        _esquemas(base_limpia),
        _extensiones(base_limpia) & EXTENSIONES,
        _funciones_publicas(base_limpia),
        _revision(motor),
    ) == ({"alembic_version"}, set(), set(), set(), None)


def test_migraciones_upgrade_head_tras_downgrade_base_funciona(
    motor: Engine, base_limpia: BasePrueba
) -> None:
    _alembic(motor, "upgrade", "head")
    _alembic(motor, "downgrade", "base")
    _alembic(motor, "upgrade", "head")
    with base_limpia.conectar() as conexion:
        cola = tablas_de(conexion, "procrastinate")
    assert (_revision(motor), cola) == (revision_head(), TABLAS_PROCRASTINATE)


def test_migraciones_downgrade_de_procrastinate_vacia_su_esquema(
    motor: Engine, base_limpia: BasePrueba
) -> None:
    _alembic(motor, "upgrade", "head")
    _alembic(motor, "downgrade", "0003_config_agentes_taxonomia")
    with base_limpia.conectar() as conexion:
        cola = tablas_de(conexion, "procrastinate")
        funciones = conexion.execute(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'procrastinate'"
        ).fetchone()
    assert (cola, funciones, "procrastinate" in _esquemas(base_limpia)) == (set(), (0,), True)


def _diferencias(conexion: Connection) -> list[object]:
    contexto = MigrationContext.configure(
        conexion,
        opts={
            "include_name": lambda nombre, tipo, padres: (
                not (tipo == "table" and nombre == "alembic_version")
            ),
            "compare_type": True,
        },
    )
    return list(compare_metadata(contexto, Base.metadata))


def test_migraciones_modelos_y_migraciones_coinciden(motor: Engine) -> None:
    _alembic(motor, "upgrade", "head")
    with motor.connect() as conexion:
        assert _diferencias(conexion) == []


def test_migraciones_0005_revoca_y_su_downgrade_restituye_dml_en_alembic_version(
    motor: Engine, base_limpia: BasePrueba, roles_separados: RolesPrueba
) -> None:
    consulta = "SELECT has_table_privilege('agente_app', 'alembic_version', 'UPDATE')"
    _alembic(motor, "upgrade", "0004_procrastinate_3_10_0")
    with base_limpia.conectar() as conexion:
        antes = conexion.execute(consulta).fetchone()
    _alembic(motor, "upgrade", "0005_revocar_alembic_version")
    with base_limpia.conectar() as conexion:
        tras_subir = conexion.execute(consulta).fetchone()
    _alembic(motor, "downgrade", "-1")
    with base_limpia.conectar() as conexion:
        tras_bajar = conexion.execute(consulta).fetchone()
    assert (antes, tras_subir, tras_bajar) == ((True,), (False,), (True,))


def test_migraciones_upgrade_head_es_idempotente(motor: Engine) -> None:
    _alembic(motor, "upgrade", "head")
    _alembic(motor, "upgrade", "head")
    assert _revision(motor) == revision_head()
