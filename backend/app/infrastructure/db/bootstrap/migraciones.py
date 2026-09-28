"""Alembic programático: revisión `head` del código, revisión actual y `upgrade head`."""

from pathlib import Path
from typing import Final

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

DIRECTORIO_ALEMBIC: Final = Path(__file__).resolve().parents[4] / "alembic"


class HeadsMultiples(RuntimeError):
    """Hay más de una revisión `head`: error de desarrollo que detecta una prueba unitaria."""

    def __init__(self, cantidad: int) -> None:
        super().__init__(f"Se esperaba una sola head de Alembic y hay {cantidad}")


class SinRevisionAplicada(RuntimeError):
    """Alembic terminó sin dejar revisión en `alembic_version`."""

    def __init__(self) -> None:
        super().__init__("Alembic no dejó revisión aplicada")


def configuracion_alembic(conexion: Connection | None = None) -> Config:
    """`Config` sin archivo; la conexión viaja en `attributes` (env.py no lee el entorno)."""
    config = Config()
    config.set_main_option("script_location", str(DIRECTORIO_ALEMBIC))
    config.set_main_option("path_separator", "os")
    if conexion is not None:
        config.attributes["connection"] = conexion
    return config


def revision_head() -> str:
    """Única revisión `head` del código; varias heads es un error de desarrollo."""
    heads = ScriptDirectory.from_config(configuracion_alembic()).get_heads()
    if len(heads) != 1:
        raise HeadsMultiples(len(heads))
    return heads[0]


def _revision_actual_sync(conexion: Connection) -> str | None:
    """Lee `alembic_version` (None si no existe)."""
    return MigrationContext.configure(conexion).get_current_revision()


def _upgrade_sync(conexion: Connection) -> None:
    """Ejecuta `upgrade head` sobre la conexión dada."""
    command.upgrade(configuracion_alembic(conexion), "head")


async def revision_actual(motor: AsyncEngine) -> str | None:
    """Revisión aplicada en la base."""
    async with motor.connect() as conexion:
        return await conexion.run_sync(_revision_actual_sync)


async def aplicar_migraciones(motor: AsyncEngine) -> str:
    """Aplica todas las migraciones pendientes y devuelve la revisión final."""
    async with motor.connect() as conexion:
        await conexion.run_sync(_upgrade_sync)
        await conexion.commit()
    final = await revision_actual(motor)
    if final is None:
        raise SinRevisionAplicada
    return final
