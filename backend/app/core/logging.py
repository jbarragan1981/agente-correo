"""Logging JSON a stdout con redacción de secretos y PII para app y librerías.

Toda línea pasa por la misma cadena de procesadores; `redactar` corre después de
`format_exc_info` para limpiar también las trazas de excepción.
"""

import logging
import re
import sys
from collections.abc import Mapping
from typing import Any, Final, TextIO

import structlog
from pydantic import SecretStr
from structlog.typing import EventDict, Processor, WrappedLogger

from app.core.config import NivelLog

REDACTADO: Final = "[REDACTADO]"
SECRETO_ENMASCARADO: Final = "**********"
PROFUNDIDAD_EXCEDIDA: Final = "[PROFUNDIDAD_MAXIMA]"
SUFIJO_TRUNCADO: Final = "…[truncado]"
LONGITUD_MAXIMA: Final = 2000
LONGITUD_MAXIMA_TRAZA: Final = 8000
PREFIJO_TRUNCADO: Final = "[truncado]…"
PROFUNDIDAD_MAXIMA: Final = 8

CLAVES_SENSIBLES: Final = (
    "password",
    "contrasena",
    "contraseña",
    "secreto",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "master_key",
    "jwt",
    "database_url",
    "dsn",
    "clave",
    "credencial",
    "passwd",
    "private_key",
)

PATRONES_VALOR: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"), REDACTADO),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), f"Bearer {REDACTADO}"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]+"), REDACTADO),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), REDACTADO),
    (re.compile(r"\bts_[A-Za-z0-9_-]{8,}"), REDACTADO),
    (re.compile(r"(://[^:/@\s]+:)[^\s/]+@"), r"\1***@"),
    (
        re.compile(
            r"(?i)([?&][a-z0-9_.-]*(?:token|key|password|secret|signature|sig)=)[^&\s#\"']+"
        ),
        rf"\1{REDACTADO}",
    ),
    (
        re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)"),
        r"\1***@\2",
    ),
)

LOGGERS_LIBRERIAS: Final = ("uvicorn", "uvicorn.error", "uvicorn.asgi", "sqlalchemy", "asyncio")
LOGGERS_SILENCIADOS: Final = ("uvicorn.access",)
LOGGERS_SOLO_AVISOS: Final = ("httpx", "httpcore", "sqlalchemy")
CAMPOS_DE_CONSOLA: Final = ("color_message",)


def _es_clave_sensible(clave: str) -> bool:
    """Indica si el nombre de la clave sugiere un secreto (subcadena, sin mayúsculas ni guiones)."""
    minuscula = clave.lower().replace("-", "_")
    return any(sensible in minuscula for sensible in CLAVES_SENSIBLES)


def _reemplazar_patrones(texto: str) -> str:
    """Reemplaza tokens, API keys, contraseñas en URL, query sensibles y emails."""
    for patron, reemplazo in PATRONES_VALOR:
        texto = patron.sub(reemplazo, texto)
    return texto


def redactar_texto(texto: str) -> str:
    """Redacta un texto y lo trunca por el final si excede la longitud máxima."""
    texto = _reemplazar_patrones(texto)
    if len(texto) > LONGITUD_MAXIMA:
        return texto[:LONGITUD_MAXIMA] + SUFIJO_TRUNCADO
    return texto


def redactar_traza(traza: str) -> str:
    """Redacta una traza y conserva su final, donde están el tipo y el mensaje."""
    traza = _reemplazar_patrones(traza)
    if len(traza) > LONGITUD_MAXIMA_TRAZA:
        return PREFIJO_TRUNCADO + traza[-LONGITUD_MAXIMA_TRAZA:]
    return traza


def _redactar_valor(valor: object, profundidad: int) -> object:
    """Redacta recursivamente dicts, listas y tuplas hasta la profundidad máxima."""
    if profundidad > PROFUNDIDAD_MAXIMA:
        return PROFUNDIDAD_EXCEDIDA
    if valor is None or isinstance(valor, bool | int | float):
        return valor
    if isinstance(valor, SecretStr):
        return SECRETO_ENMASCARADO
    if isinstance(valor, str):
        return redactar_texto(valor)
    if isinstance(valor, Mapping):
        return _redactar_mapa(valor, profundidad + 1)
    if isinstance(valor, list | tuple | set | frozenset):
        return [_redactar_valor(elemento, profundidad + 1) for elemento in valor]
    return redactar_texto(str(valor))


def _redactar_mapa(mapa: Mapping[Any, Any], profundidad: int) -> dict[Any, object]:
    """Redacta un mapa: por clave sensible y, en el resto, por valor."""
    return {
        clave: REDACTADO
        if isinstance(clave, str) and _es_clave_sensible(clave)
        else _redactar_valor(valor, profundidad)
        for clave, valor in mapa.items()
    }


def redactar(logger: WrappedLogger, metodo: str, evento: EventDict) -> EventDict:
    """Procesador structlog que elimina secretos y PII del evento completo."""
    traza = evento.pop("exception", None)
    limpio = _redactar_mapa(evento, 0)
    if traza is not None:
        limpio["exception"] = redactar_traza(str(traza))
    return limpio


def _renombrar_nivel(logger: WrappedLogger, metodo: str, evento: EventDict) -> EventDict:
    """Mueve `level` a `nivel` para el esquema de logs del proyecto."""
    if "level" in evento:
        evento["nivel"] = evento.pop("level")
    return evento


def _quitar_campos_de_consola(logger: WrappedLogger, metodo: str, evento: EventDict) -> EventDict:
    """Elimina campos pensados para terminal (p. ej. `color_message` de Uvicorn)."""
    for campo in CAMPOS_DE_CONSOLA:
        evento.pop(campo, None)
    return evento


class _ManejadorStdout(logging.StreamHandler[TextIO]):
    """Handler que escribe en el `sys.stdout` vigente en cada emisión."""

    def emit(self, record: logging.LogRecord) -> None:
        """Resuelve stdout al emitir para respetar redirecciones posteriores."""
        self.stream = sys.stdout
        super().emit(record)


def _procesadores_previos() -> list[Processor]:
    """Procesadores comunes a logs de structlog y de la librería estándar."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
    ]


def _crear_formateador() -> structlog.stdlib.ProcessorFormatter:
    """Formateador JSON único con redacción posterior al formateo de excepciones."""
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[*_procesadores_previos(), structlog.stdlib.ExtraAdder()],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            _renombrar_nivel,
            _quitar_campos_de_consola,
            redactar,
            structlog.processors.EventRenamer("evento"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )


def _enrutar_librerias() -> None:
    """Hace que las librerías propaguen al root y silencia el access log de Uvicorn."""
    for nombre in LOGGERS_LIBRERIAS:
        logger = logging.getLogger(nombre)
        logger.handlers.clear()
        logger.propagate = True
    for nombre in LOGGERS_SILENCIADOS:
        logger = logging.getLogger(nombre)
        logger.handlers.clear()
        logger.propagate = False
        logger.disabled = True
    for nombre in LOGGERS_SOLO_AVISOS:
        logging.getLogger(nombre).setLevel(logging.WARNING)


def configurar_logging(nivel: NivelLog) -> None:
    """Configura structlog y la librería estándar para emitir JSON redactado a stdout."""
    structlog.configure(
        processors=[
            *_procesadores_previos(),
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    raiz = logging.getLogger()
    for manejador in [m for m in raiz.handlers if isinstance(m, _ManejadorStdout)]:
        raiz.removeHandler(manejador)
    manejador = _ManejadorStdout(sys.stdout)
    manejador.setFormatter(_crear_formateador())
    raiz.addHandler(manejador)
    raiz.setLevel(nivel)
    _enrutar_librerias()


def obtener_logger(nombre: str) -> structlog.stdlib.BoundLogger:
    """Devuelve un logger structlog con nombre."""
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(nombre)
    return logger
