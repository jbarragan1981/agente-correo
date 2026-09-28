"""Pruebas API del contrato problem+json (CA9) con un router solo de prueba."""

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from tests.api.rutas_prueba import router_prueba
from tests.soporte import cliente_para

LeerLogs = Callable[[], list[dict[str, Any]]]
VALOR_MARCADOR = "valor-marcador-enviado"


@pytest.fixture
def app_con_rutas(app_prueba: FastAPI) -> FastAPI:
    """App de prueba con el router solo de prueba."""
    app_prueba.include_router(router_prueba)
    return app_prueba


@pytest.fixture
async def cliente(app_con_rutas: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente contra la app con rutas de prueba."""
    async with cliente_para(app_con_rutas) as cliente:
        yield cliente


async def _body_invalido(cliente: httpx.AsyncClient) -> httpx.Response:
    """Envía un body con `password` demasiado largo y `edad` no numérica."""
    return await cliente.post(
        "/api/v1/prueba/validar", json={"password": VALOR_MARCADOR, "edad": "no-numero"}
    )


async def test_errores_body_invalido_responde_400_validacion(cliente: httpx.AsyncClient) -> None:
    respuesta = await _body_invalido(cliente)
    assert (respuesta.status_code, respuesta.json()["type"]) == (400, "validacion")


async def test_errores_body_invalido_detalla_campos(cliente: httpx.AsyncClient) -> None:
    errores = (await _body_invalido(cliente)).json()["errores"]
    assert {error["campo"] for error in errores} == {"body.password", "body.edad"}


async def test_errores_body_invalido_no_devuelve_valores(cliente: httpx.AsyncClient) -> None:
    texto = (await _body_invalido(cliente)).text
    assert (VALOR_MARCADOR in texto, "no-numero" in texto) == (False, False)


async def test_errores_json_malformado_responde_400(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.post(
        "/api/v1/prueba/validar",
        content=b"{no-json",
        headers={"content-type": "application/json"},
    )
    assert (respuesta.status_code, respuesta.json()["type"]) == (400, "validacion")


async def test_errores_excepcion_responde_500_error_interno(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/api/v1/prueba/fallar")
    assert (respuesta.status_code, respuesta.json()["type"]) == (500, "error_interno")


async def test_errores_500_no_expone_mensaje_ni_traza(cliente: httpx.AsyncClient) -> None:
    texto = (await cliente.get("/api/v1/prueba/fallar")).text
    assert ("marcador-interno" in texto, "Traceback" in texto) == (False, False)


async def test_errores_500_lleva_request_id_y_cabeceras(cliente: httpx.AsyncClient) -> None:
    cabeceras = (await cliente.get("/api/v1/prueba/fallar")).headers
    assert {"x-request-id", "content-security-policy", "strict-transport-security"} <= set(
        cabeceras.keys()
    )


async def test_errores_500_registra_la_excepcion(
    cliente: httpx.AsyncClient, capturar_logs: LeerLogs
) -> None:
    await cliente.get("/api/v1/prueba/fallar")
    eventos = [log for log in capturar_logs() if log.get("evento") == "http.error_inesperado"]
    assert "RuntimeError: marcador-interno" in eventos[0]["exception"]


async def test_errores_ruta_inexistente_responde_404(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/api/v1/no-existe")
    assert (respuesta.status_code, respuesta.json()["type"]) == (404, "no_encontrado")


async def test_errores_dominio_conflicto_responde_409(cliente: httpx.AsyncClient) -> None:
    respuesta = await cliente.get("/api/v1/prueba/conflicto")
    assert (respuesta.status_code, respuesta.json()["type"]) == (409, "conflicto")


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [("GET", "/api/v1/no-existe"), ("GET", "/api/v1/prueba/fallar"), ("POST", "/api/v1/salud")],
)
async def test_errores_instance_es_urn_del_request_id(
    cliente: httpx.AsyncClient, metodo: str, ruta: str
) -> None:
    respuesta = await cliente.request(metodo, ruta)
    assert respuesta.json()["instance"] == f"urn:uuid:{respuesta.headers['x-request-id']}"


async def test_errores_cuerpo_tiene_campos_rfc9457(cliente: httpx.AsyncClient) -> None:
    cuerpo = json.loads((await cliente.get("/api/v1/no-existe")).text)
    assert {"type", "title", "status", "detail", "instance"} <= cuerpo.keys()
