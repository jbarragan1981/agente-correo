"""Espera a que PostgreSQL acepte conexiones con backoff exponencial acotado.

Se usa asyncpg porque expone el SQLSTATE de los fallos de conexión: una base inexistente
significa que el servidor ya responde; una credencial rechazada no se arregla esperando.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Final

import asyncpg
from sqlalchemy.engine import URL

from app.core.logging import obtener_logger
from app.infrastructure.db.bootstrap.errores import AutenticacionRechazada, BdNoDisponible

ESPERA_INICIAL_S: Final = 0.5
ESPERA_MAXIMA_S: Final = 5.0
TIMEOUT_CONEXION_S: Final = 5.0
ERRORES_DE_CREDENCIAL: Final = (
    asyncpg.InvalidPasswordError,
    asyncpg.InvalidAuthorizationSpecificationError,
)

Conectar = Callable[[URL, float], Awaitable[None]]
Dormir = Callable[[float], Awaitable[None]]
Reloj = Callable[[], float]

_log = obtener_logger(__name__)


async def conectar_asyncpg(url: URL, timeout_s: float) -> None:
    """Abre y cierra una conexión; propaga la excepción de asyncpg."""
    conexion = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database=url.database,
        timeout=timeout_s,
    )
    await conexion.close()


def siguiente_espera(actual: float) -> float:
    """Duplica la espera sin superar el máximo."""
    return min(actual * 2, ESPERA_MAXIMA_S)


async def esperar_postgres(
    url: URL,
    max_s: float,
    conectar: Conectar = conectar_asyncpg,
    dormir: Dormir = asyncio.sleep,
    reloj: Reloj = time.monotonic,
) -> int:
    """Reintenta hasta que el servidor responda; devuelve el número de intentos."""
    limite = reloj() + max_s
    espera = ESPERA_INICIAL_S
    intentos = 0
    while True:
        intentos += 1
        try:
            await conectar(url, min(TIMEOUT_CONEXION_S, max_s))
        except asyncpg.InvalidCatalogNameError:
            return intentos
        except ERRORES_DE_CREDENCIAL as exc:
            raise AutenticacionRechazada(sqlstate=exc.sqlstate) from None
        except (OSError, TimeoutError, asyncpg.PostgresError) as exc:
            restante = limite - reloj()
            if restante <= 0:
                raise BdNoDisponible(tipo_error=type(exc).__name__) from None
            _log.info("bootstrap.esperando_bd", intento=intentos, tipo_error=type(exc).__name__)
            await dormir(min(espera, restante))
            espera = siguiente_espera(espera)
        else:
            return intentos
