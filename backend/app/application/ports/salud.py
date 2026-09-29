"""Puerto de sondas de dependencias para la comprobación de preparación."""

from enum import StrEnum
from typing import Protocol


class ResultadoSonda(StrEnum):
    """Resultado de comprobar una dependencia."""

    OK = "ok"
    FALLA = "falla"


class SondaDependenciaPort(Protocol):
    """Comprueba una dependencia externa; nunca lanza, devuelve `FALLA`."""

    @property
    def nombre(self) -> str:
        """Nombre estable de la comprobación (p. ej. `base_datos`)."""
        ...

    async def comprobar(self) -> ResultadoSonda:
        """Ejecuta la comprobación."""
        ...
