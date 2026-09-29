"""Middleware ASGI que convierte excepciones no manejadas en 500 problem+json.

Corre dentro de correlación, cabeceras y CORS para que el 500 también lleve
`X-Request-ID`, cabeceras de seguridad y CORS (el manejador de Starlette corre fuera).
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errores import ERROR_INTERNO, respuesta_problema
from app.api.middleware.correlacion import obtener_correlation_id
from app.core.logging import obtener_logger

_log = obtener_logger(__name__)


class ErroresInesperadosMiddleware:
    """Registra la excepción con traza redactada y responde sin detalles internos."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Delegado protegido: si la respuesta ya empezó, relanza la excepción."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        respuesta_iniciada = False

        async def enviar(mensaje: Message) -> None:
            nonlocal respuesta_iniciada
            if mensaje["type"] == "http.response.start":
                respuesta_iniciada = True
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            _log.exception("http.error_inesperado", ruta=scope["path"])
            if respuesta_iniciada:
                raise
            respuesta = respuesta_problema(obtener_correlation_id(scope), ERROR_INTERNO)
            await respuesta(scope, receive, send)
