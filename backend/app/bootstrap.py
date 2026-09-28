"""Composition root del bootstrap de BD: `python -m app.bootstrap` (ADR-0008).

Códigos de salida: 0 correcto, 1 configuración inválida, 2 fallo del bootstrap.
"""

import asyncio
import sys
from typing import Final

from app.core.config import ConfiguracionInvalida, Settings, cargar_settings
from app.core.logging import configurar_logging, obtener_logger
from app.infrastructure.avisos.stderr import AvisoStderr
from app.infrastructure.db.bootstrap.errores import (
    ErrorBootstrap,
    FalloEnPaso,
    PrivilegiosInseguros,
)
from app.infrastructure.db.bootstrap.orquestador import ejecutar_bootstrap

CODIGO_OK: Final = 0
CODIGO_CONFIG_INVALIDA: Final = 1
CODIGO_FALLO_BOOTSTRAP: Final = 2

_log = obtener_logger("app.bootstrap")


def _cargar() -> Settings | None:
    """Configuración o `None` tras registrar los campos inválidos (sin valores)."""
    try:
        return cargar_settings()
    except ConfiguracionInvalida as error:
        configurar_logging("INFO")
        _log.critical(
            "config.invalida",
            errores=[{"campo": campo, "mensaje": mensaje} for campo, mensaje in error.errores],
        )
        return None


def registrar_fallo(error: ErrorBootstrap) -> None:
    """Emite el evento específico y `bootstrap.fallido` con paso, tipo y SQLSTATE."""
    campos: dict[str, object] = {
        "paso": error.paso,
        "tipo_error": error.tipo_error,
        "sqlstate": error.sqlstate,
    }
    if isinstance(error, PrivilegiosInseguros):
        campos["comprobaciones"] = list(error.comprobaciones)
    if error.evento != ErrorBootstrap.evento:
        _log.error(error.evento, **campos)
    _log.error(ErrorBootstrap.evento, **campos)


def codigo_de_salida(error: BaseException) -> int:
    """Traduce una excepción del bootstrap al código de salida, registrándola sin detalles."""
    if not isinstance(error, ErrorBootstrap):
        error = FalloEnPaso("desconocido", type(error).__name__)
    registrar_fallo(error)
    return CODIGO_FALLO_BOOTSTRAP


def main() -> int:
    """Carga configuración, configura logs y ejecuta el bootstrap."""
    settings = _cargar()
    if settings is None:
        return CODIGO_CONFIG_INVALIDA
    configurar_logging("DEBUG" if settings.debug else settings.log_level)
    try:
        asyncio.run(ejecutar_bootstrap(settings, AvisoStderr()))
    except Exception as error:  # noqa: BLE001 - todo fallo termina en código 2 sin detalles
        return codigo_de_salida(error)
    return CODIGO_OK


if __name__ == "__main__":
    sys.exit(main())
