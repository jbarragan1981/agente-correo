"""Sonda de preparación: la base está en la revisión `head` del código (ADR-0008)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.ports.salud import ResultadoSonda
from app.core.logging import obtener_logger

_log = obtener_logger(__name__)
CONSULTA_REVISION = text("SELECT version_num FROM alembic_version")


class SondaMigraciones:
    """OK solo si `alembic_version` tiene exactamente una fila igual a la revisión esperada."""

    def __init__(self, motor: AsyncEngine, revision_esperada: str) -> None:
        self._motor = motor
        self._esperada = revision_esperada

    @property
    def nombre(self) -> str:
        """Nombre de la comprobación en el informe."""
        return "migraciones"

    async def comprobar(self) -> ResultadoSonda:
        """Compara la revisión aplicada con la esperada; nunca lanza."""
        try:
            async with self._motor.connect() as conexion:
                revisiones = list((await conexion.execute(CONSULTA_REVISION)).scalars())
        except Exception as exc:  # noqa: BLE001 - la sonda nunca lanza; el tipo basta para diagnosticar
            _log.warning("salud.migraciones_falla", tipo_error=type(exc).__name__)
            return ResultadoSonda.FALLA
        if revisiones != [self._esperada]:
            _log.warning("salud.migraciones_desfasadas", actual=revisiones, esperada=self._esperada)
            return ResultadoSonda.FALLA
        return ResultadoSonda.OK
