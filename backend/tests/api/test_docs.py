"""Pruebas API de documentación condicionada al entorno (CA11)."""

import httpx
import pytest

from app.main import crear_app
from tests.soporte import cliente_para, settings_prueba, valores_produccion

RUTAS_DOCUMENTACION = [
    "/api/v1/docs",
    "/api/v1/redoc",
    "/api/v1/openapi.json",
    "/api/v1/docs/oauth2-redirect",
    "/docs",
    "/redoc",
    "/openapi.json",
]


@pytest.mark.parametrize("ruta", RUTAS_DOCUMENTACION)
async def test_docs_en_produccion_responden_404(ruta: str) -> None:
    app = crear_app(settings_prueba(**valores_produccion()))
    async with cliente_para(app) as cliente:
        assert (await cliente.get(ruta)).status_code == 404


async def test_docs_en_desarrollo_openapi_responde_200(cliente_api: httpx.AsyncClient) -> None:
    assert (await cliente_api.get("/api/v1/openapi.json")).status_code == 200


async def test_docs_openapi_declara_el_esquema_problema(cliente_api: httpx.AsyncClient) -> None:
    esquema = (await cliente_api.get("/api/v1/openapi.json")).json()
    assert "Problema" in esquema["components"]["schemas"]


async def test_docs_openapi_503_de_listo_es_problem_json(cliente_api: httpx.AsyncClient) -> None:
    esquema = (await cliente_api.get("/api/v1/openapi.json")).json()
    contenido = esquema["paths"]["/api/v1/salud/listo"]["get"]["responses"]["503"]["content"]
    assert list(contenido) == ["application/problem+json"]


@pytest.mark.parametrize("ruta", ["/docs", "/redoc", "/openapi.json"])
async def test_docs_en_desarrollo_no_existen_fuera_del_prefijo(
    cliente_api: httpx.AsyncClient, ruta: str
) -> None:
    assert (await cliente_api.get(ruta)).status_code == 404
