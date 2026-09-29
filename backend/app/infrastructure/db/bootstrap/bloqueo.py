"""Advisory lock de sesión que serializa bootstraps concurrentes (ADR-0008)."""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core.logging import obtener_logger
from app.infrastructure.db.bootstrap.errores import LockTimeout

CLAVE_LOCK: Final = 0xA6E17E
ESPERA_INICIAL_S: Final = 0.2
ESPERA_MAXIMA_S: Final = 2.0
TOMAR = text("SELECT pg_try_advisory_lock(:clave)")
LIBERAR = text("SELECT pg_advisory_unlock(:clave)")

_log = obtener_logger(__name__)


async def _intentar(conexion: AsyncConnection) -> bool:
    """Un intento no bloqueante de tomar el lock."""
    return bool((await conexion.execute(TOMAR, {"clave": CLAVE_LOCK})).scalar_one())


async def _tomar(conexion: AsyncConnection, timeout_s: float) -> None:
    """Reintenta con backoff hasta el timeout."""
    limite = time.monotonic() + timeout_s
    espera = ESPERA_INICIAL_S
    while not await _intentar(conexion):
        restante = limite - time.monotonic()
        if restante <= 0:
            raise LockTimeout
        _log.info("bootstrap.esperando_lock")
        await asyncio.sleep(min(espera, restante))
        espera = min(espera * 2, ESPERA_MAXIMA_S)


@asynccontextmanager
async def bloqueo_bootstrap(motor: AsyncEngine, timeout_s: float) -> AsyncIterator[None]:
    """Mantiene el lock en una conexión dedicada durante todo el bloque."""
    async with motor.connect() as conexion:
        autocommit = await conexion.execution_options(isolation_level="AUTOCOMMIT")
        await _tomar(autocommit, timeout_s)
        try:
            yield
        finally:
            await autocommit.execute(LIBERAR, {"clave": CLAVE_LOCK})
