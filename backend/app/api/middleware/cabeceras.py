"""Middleware ASGI que añade cabeceras de seguridad a toda respuesta HTTP."""

import base64
import hashlib
import re
from typing import Final

from fastapi.openapi.docs import get_swagger_ui_html
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

RUTA_DOCS: Final = "/api/v1/docs"
RUTA_REDOC: Final = "/api/v1/redoc"
RUTA_OPENAPI: Final = "/api/v1/openapi.json"
RUTA_OAUTH2_REDIRECT: Final = f"{RUTA_DOCS}/oauth2-redirect"
RUTAS_DOCUMENTACION: Final = frozenset({RUTA_DOCS, RUTA_REDOC})

CSP_API: Final = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

CABECERAS_FIJAS: Final[dict[str, str]] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
CACHE_CONTROL: Final = "no-store"


def _hashes_scripts_swagger() -> str:
    """Calcula los hashes CSP de los scripts en línea de la página Swagger UI de FastAPI."""
    cuerpo = get_swagger_ui_html(
        openapi_url=RUTA_OPENAPI, title="", oauth2_redirect_url=RUTA_OAUTH2_REDIRECT
    ).body
    scripts = re.findall(r"<script>(.*?)</script>", bytes(cuerpo).decode(), flags=re.DOTALL)
    return " ".join(
        f"'sha256-{base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()}'"
        for s in scripts
    )


CSP_DOCUMENTACION: Final = (
    "default-src 'none'; "
    f"script-src 'self' https://cdn.jsdelivr.net {_hashes_scripts_swagger()}; "
    "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com 'unsafe-inline'; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "connect-src 'self'; worker-src blob:; "
    "frame-ancestors 'none'; base-uri 'none'"
)


def csp_para(ruta: str) -> str:
    """Devuelve la CSP estricta de la API o la de documentación para Swagger/ReDoc."""
    return CSP_DOCUMENTACION if ruta in RUTAS_DOCUMENTACION else CSP_API


def aplicar_cabeceras(cabeceras: MutableHeaders, ruta: str) -> None:
    """Escribe las cabeceras de seguridad y elimina `Server`."""
    for nombre, valor in CABECERAS_FIJAS.items():
        cabeceras[nombre] = valor
    cabeceras["Content-Security-Policy"] = csp_para(ruta)
    cabeceras.setdefault("Cache-Control", CACHE_CONTROL)
    if "server" in cabeceras:
        del cabeceras["server"]


class CabecerasSeguridadMiddleware:
    """Aplica HSTS, CSP, anti-framing y demás cabeceras a toda respuesta HTTP."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Intercepta el inicio de la respuesta para añadir las cabeceras."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ruta = str(scope["path"])

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                aplicar_cabeceras(MutableHeaders(scope=mensaje), ruta)
            await send(mensaje)

        await self.app(scope, receive, enviar)
