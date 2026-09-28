"""Creación del motor SQLAlchemy async (perezoso: no conecta al crearse)."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings

TAMANO_POOL = 5
DESBORDE_POOL = 5


def crear_motor(settings: Settings) -> AsyncEngine:
    """Crea el motor con pool acotado y timeout de conexión."""
    return create_async_engine(
        settings.url_base_datos(),
        pool_pre_ping=True,
        pool_size=TAMANO_POOL,
        max_overflow=DESBORDE_POOL,
        connect_args={"timeout": settings.salud_bd_timeout_s},
    )
