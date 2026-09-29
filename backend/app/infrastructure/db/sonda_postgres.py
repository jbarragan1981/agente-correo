"""Sonda de preparación de PostgreSQL (implementa `SondaDependenciaPort`)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.ports.salud import ResultadoSonda
from app.core.logging import obtener_logger

_log = obtener_logger(__name__)
CONSULTA_SONDA = text("SELECT 1")


class SondaPostgres:
    """Ejecuta `SELECT 1`; cualquier error se traduce en `FALLA` sin exponer detalles."""

    def __init__(self, motor: AsyncEngine) -> None:
        self._motor = motor

    @property
    def nombre(self) -> str:
        """Nombre de la comprobación en el informe."""
        return "base_datos"

    async def comprobar(self) -> ResultadoSonda:
        """Abre una conexión del pool y ejecuta la consulta mínima."""
        try:
            async with self._motor.connect() as conexion:
                await conexion.execute(CONSULTA_SONDA)
        except Exception as exc:  # noqa: BLE001 - la sonda nunca lanza; el tipo basta para diagnosticar
            _log.warning("salud.base_datos_falla", tipo_error=type(exc).__name__)
            return ResultadoSonda.FALLA
        return ResultadoSonda.OK
