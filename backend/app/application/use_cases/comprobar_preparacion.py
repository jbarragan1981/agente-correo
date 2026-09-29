"""Caso de uso: comprobar si las dependencias del servicio están listas."""

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.application.ports.salud import ResultadoSonda, SondaDependenciaPort

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class InformePreparacion:
    """Resultado agregado de las sondas."""

    listo: bool
    comprobaciones: Mapping[str, ResultadoSonda]


class ComprobarPreparacion:
    """Ejecuta todas las sondas en paralelo, cada una con su propio timeout."""

    def __init__(self, sondas: Sequence[SondaDependenciaPort], timeout_s: float) -> None:
        self._sondas = tuple(sondas)
        self._timeout_s = timeout_s

    async def ejecutar(self) -> InformePreparacion:
        """Devuelve el informe; una sonda lenta o con error cuenta como `FALLA`."""
        resultados = await asyncio.gather(*(self._comprobar(sonda) for sonda in self._sondas))
        comprobaciones = {
            sonda.nombre: resultado
            for sonda, resultado in zip(self._sondas, resultados, strict=True)
        }
        return InformePreparacion(
            listo=all(resultado is ResultadoSonda.OK for resultado in resultados),
            comprobaciones=MappingProxyType(comprobaciones),
        )

    async def _comprobar(self, sonda: SondaDependenciaPort) -> ResultadoSonda:
        """Ejecuta una sonda protegida por timeout; registra solo el tipo de error."""
        try:
            async with asyncio.timeout(self._timeout_s):
                return await sonda.comprobar()
        except Exception as exc:  # noqa: BLE001 - una sonda defectuosa no debe tumbar la salud
            _log.warning(
                "preparacion.sonda_fallida",
                extra={"sonda": sonda.nombre, "tipo_error": type(exc).__name__},
            )
            return ResultadoSonda.FALLA
