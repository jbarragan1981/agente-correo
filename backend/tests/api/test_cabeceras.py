"""Pruebas API de cabeceras de seguridad y `X-Request-ID` en todo código de estado (CA8)."""

import base64
import hashlib
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.api.middleware.cabeceras import CABECERAS_FIJAS, CSP_API
from app.application.ports.salud import ResultadoSonda
from app.main import crear_app
from tests.api.rutas_prueba import router_prueba
from tests.soporte import SondaFalsa, cliente_para, settings_prueba, usar_sondas

UUID_CLIENTE = "3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10"
PETICIONES: list[tuple[int, str, str, dict[str, Any]]] = [
    (200, "GET", "/api/v1/salud", {}),
    (404, "GET", "/api/v1/no-existe", {}),
    (405, "POST", "/api/v1/salud", {}),
    (400, "POST", "/api/v1/prueba/validar", {"json": {"edad": "x"}}),
    (500, "GET", "/api/v1/prueba/fallar", {}),
    (503, "GET", "/api/v1/salud/listo", {}),
]


@pytest.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    """App con BD caída simulada y rutas de prueba para provocar cada código."""
    app = crear_app(settings_prueba())
    usar_sondas(app, SondaFalsa(ResultadoSonda.FALLA))
    app.include_router(router_prueba)
    async with cliente_para(app) as cliente:
        yield cliente


async def _pedir(cliente: httpx.AsyncClient, peticion: tuple[Any, ...]) -> httpx.Response:
    """Ejecuta la petición parametrizada y comprueba su código."""
    status, metodo, ruta, extra = peticion
    respuesta = await cliente.request(metodo, ruta, **extra)
    assert respuesta.status_code == status
    return respuesta


@pytest.mark.parametrize("peticion", PETICIONES, ids=lambda p: str(p[0]))
async def test_cabeceras_seguridad_en_toda_respuesta(
    cliente: httpx.AsyncClient, peticion: tuple[Any, ...]
) -> None:
    cabeceras = (await _pedir(cliente, peticion)).headers
    esperadas = {**CABECERAS_FIJAS, "Content-Security-Policy": CSP_API, "Cache-Control": "no-store"}
    assert {nombre: cabeceras.get(nombre) for nombre in esperadas} == esperadas


@pytest.mark.parametrize("peticion", PETICIONES, ids=lambda p: str(p[0]))
async def test_cabeceras_request_id_en_toda_respuesta(
    cliente: httpx.AsyncClient, peticion: tuple[Any, ...]
) -> None:
    cabeceras = (await _pedir(cliente, peticion)).headers
    assert re.fullmatch(r"[0-9a-f-]{36}", cabeceras["x-request-id"])


@pytest.mark.parametrize("peticion", PETICIONES, ids=lambda p: str(p[0]))
async def test_cabeceras_sin_server(cliente: httpx.AsyncClient, peticion: tuple[Any, ...]) -> None:
    assert "server" not in (await _pedir(cliente, peticion)).headers


async def test_cabeceras_request_id_valido_del_cliente_se_devuelve(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/api/v1/salud", headers={"X-Request-ID": UUID_CLIENTE})
    assert respuesta.headers["x-request-id"] == UUID_CLIENTE


async def test_cabeceras_request_id_invalido_se_reemplaza(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/api/v1/salud", headers={"X-Request-ID": "inyectado\tvalor"})
    assert respuesta.headers["x-request-id"] != "inyectado\tvalor"


async def test_cabeceras_swagger_csp_autoriza_su_script_en_linea() -> None:
    app: FastAPI = crear_app(settings_prueba(env="development"))
    async with cliente_para(app) as cliente:
        respuesta = await cliente.get("/api/v1/docs")
    scripts = re.findall(r"<script>(.*?)</script>", respuesta.text, flags=re.DOTALL)
    hashes = {
        f"'sha256-{base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()}'"
        for s in scripts
    }
    directivas = set(respuesta.headers["content-security-policy"].replace(";", " ").split())
    assert (len(hashes) > 0, hashes <= directivas) == (True, True)
