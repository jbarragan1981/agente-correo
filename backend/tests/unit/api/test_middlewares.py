"""Pruebas de los middlewares ASGI con apps mínimas (sin FastAPI)."""

from typing import Any

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.api.middleware.cabeceras import CabecerasSeguridadMiddleware
from app.api.middleware.correlacion import CorrelacionMiddleware
from app.api.middleware.errores_inesperados import ErroresInesperadosMiddleware

MIDDLEWARES = [CorrelacionMiddleware, CabecerasSeguridadMiddleware, ErroresInesperadosMiddleware]


class AppRegistradora:
    """App ASGI que registra los scopes recibidos."""

    def __init__(self) -> None:
        self.scopes: list[Scope] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Guarda el scope y no responde."""
        self.scopes.append(scope)


async def _recibir() -> Message:
    """Receive vacío."""
    return {"type": "http.request", "body": b"", "more_body": False}


def _scope_http() -> dict[str, Any]:
    """Scope HTTP mínimo."""
    return {"type": "http", "method": "GET", "path": "/x", "headers": [], "query_string": b""}


@pytest.mark.parametrize("middleware", MIDDLEWARES, ids=lambda m: m.__name__)
async def test_middleware_scope_no_http_pasa_sin_cambios(middleware: Any) -> None:
    interna = AppRegistradora()
    scope = {"type": "lifespan"}
    enviados: list[Message] = []

    async def enviar(mensaje: Message) -> None:
        enviados.append(mensaje)

    await middleware(interna)(scope, _recibir, enviar)
    assert interna.scopes == [{"type": "lifespan"}]


async def test_errores_inesperados_con_respuesta_iniciada_relanza() -> None:
    async def app_que_falla_tarde(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        mensaje = "fallo tras iniciar"
        raise RuntimeError(mensaje)

    async def enviar(mensaje: Message) -> None:
        return None

    with pytest.raises(RuntimeError):
        await ErroresInesperadosMiddleware(app_que_falla_tarde)(_scope_http(), _recibir, enviar)
