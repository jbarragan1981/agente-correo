"""Pruebas API de CORS por allowlist (CA10)."""

import httpx

from app.main import crear_app
from tests.soporte import ORIGEN_PERMITIDO, cliente_para, settings_prueba

ORIGEN_AJENO = "https://atacante.ejemplo.net"


def _preflight(origen: str) -> dict[str, str]:
    """Cabeceras de una petición preflight para GET con `Authorization`."""
    return {
        "Origin": origen,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization",
    }


async def test_cors_preflight_origen_permitido_recibe_acao(cliente_api: httpx.AsyncClient) -> None:
    respuesta = await cliente_api.options("/api/v1/salud", headers=_preflight(ORIGEN_PERMITIDO))
    assert (
        respuesta.headers.get("access-control-allow-origin"),
        respuesta.headers.get("access-control-allow-credentials"),
    ) == (ORIGEN_PERMITIDO, "true")


async def test_cors_preflight_origen_ajeno_sin_acao(cliente_api: httpx.AsyncClient) -> None:
    respuesta = await cliente_api.options("/api/v1/salud", headers=_preflight(ORIGEN_AJENO))
    assert "access-control-allow-origin" not in respuesta.headers


async def test_cors_peticion_simple_origen_ajeno_sin_acao(cliente_api: httpx.AsyncClient) -> None:
    respuesta = await cliente_api.get("/api/v1/salud", headers={"Origin": ORIGEN_AJENO})
    assert "access-control-allow-origin" not in respuesta.headers


async def test_cors_expone_request_id(cliente_api: httpx.AsyncClient) -> None:
    respuesta = await cliente_api.get("/api/v1/salud", headers={"Origin": ORIGEN_PERMITIDO})
    assert "X-Request-ID" in respuesta.headers["access-control-expose-headers"]


async def test_cors_allowlist_vacia_no_permite_ningun_origen() -> None:
    async with cliente_para(crear_app(settings_prueba(cors_origenes=[]))) as cliente:
        respuesta = await cliente.options("/api/v1/salud", headers=_preflight(ORIGEN_PERMITIDO))
    assert "access-control-allow-origin" not in respuesta.headers
