"""Middleware ASGI de correlation id y log de acceso."""

import time
import uuid
from typing import Final

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import obtener_logger

CABECERA_ID: Final = "X-Request-ID"
CLAVE_ESTADO: Final = "correlation_id"
LONGITUD_UUID: Final = 36

_log = obtener_logger(__name__)


def correlation_id_valido(valor: str | None) -> str:
    """Devuelve el id recibido si es un UUID canónico; si no, genera uno nuevo."""
    if valor is not None and len(valor) == LONGITUD_UUID:
        try:
            return str(uuid.UUID(valor))
        except ValueError:
            pass
    return str(uuid.uuid4())


def obtener_correlation_id(scope: Scope) -> str:
    """Lee el correlation id de la petición; genera uno si el middleware no corrió."""
    estado = scope.setdefault("state", {})
    if CLAVE_ESTADO not in estado:
        estado[CLAVE_ESTADO] = str(uuid.uuid4())
    return str(estado[CLAVE_ESTADO])


class CorrelacionMiddleware:
    """Asigna `X-Request-ID`, lo liga a los logs y registra el acceso sin query string."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Procesa peticiones HTTP; el resto de tipos pasa sin cambios."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlation_id = correlation_id_valido(Headers(scope=scope).get(CABECERA_ID))
        scope.setdefault("state", {})[CLAVE_ESTADO] = correlation_id
        tokens = structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        inicio = time.perf_counter()
        estado_http = 500

        async def enviar(mensaje: Message) -> None:
            nonlocal estado_http
            if mensaje["type"] == "http.response.start":
                estado_http = int(mensaje["status"])
                MutableHeaders(scope=mensaje)[CABECERA_ID] = correlation_id
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        finally:
            _log.info(
                "http.peticion",
                metodo=scope["method"],
                ruta=scope["path"],
                estado=estado_http,
                duracion_ms=round((time.perf_counter() - inicio) * 1000, 2),
            )
            structlog.contextvars.reset_contextvars(**tokens)
