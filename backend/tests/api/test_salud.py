"""Pruebas API de `/api/v1/salud` y `/api/v1/salud/listo` (CA6, CA7)."""

import time

import httpx
from fastapi import FastAPI

from app.application.ports.salud import ResultadoSonda
from app.main import crear_app
from tests.soporte import (
    TIMEOUT_PRUEBA_S,
    SondaColgada,
    SondaEspia,
    SondaFalsa,
    SondaQueLanza,
    cliente_para,
    settings_prueba,
    usar_sondas,
)

MARGEN_S = 0.5


def _app_con(*sondas: SondaFalsa) -> FastAPI:
    """App de prueba con las sondas indicadas."""
    app = crear_app(settings_prueba())
    usar_sondas(app, *sondas)
    return app


async def test_salud_vivo_responde_200(cliente_api: httpx.AsyncClient) -> None:
    respuesta = await cliente_api.get("/api/v1/salud")
    assert (respuesta.status_code, respuesta.json()) == (200, {"estado": "vivo"})


async def test_salud_vivo_no_consulta_sondas() -> None:
    espia = SondaEspia()
    async with cliente_para(_app_con(espia)) as cliente:
        await cliente.get("/api/v1/salud")
    assert espia.llamadas == 0


async def test_salud_listo_con_bd_ok_responde_200(cliente_api: httpx.AsyncClient) -> None:
    respuesta = await cliente_api.get("/api/v1/salud/listo")
    assert (respuesta.status_code, respuesta.json()) == (
        200,
        {"estado": "listo", "comprobaciones": {"base_datos": "ok"}},
    )


async def test_salud_listo_con_bd_caida_responde_503_problem() -> None:
    async with cliente_para(_app_con(SondaFalsa(ResultadoSonda.FALLA))) as cliente:
        respuesta = await cliente.get("/api/v1/salud/listo")
    cuerpo = respuesta.json()
    assert (
        respuesta.status_code,
        respuesta.headers["content-type"],
        cuerpo["type"],
        cuerpo["comprobaciones"],
    ) == (503, "application/problem+json", "no_listo", {"base_datos": "falla"})


async def test_salud_listo_con_sonda_colgada_responde_dentro_del_timeout() -> None:
    async with cliente_para(_app_con(SondaColgada())) as cliente:
        inicio = time.perf_counter()
        respuesta = await cliente.get("/api/v1/salud/listo")
        duracion = time.perf_counter() - inicio
    assert (respuesta.status_code, duracion <= TIMEOUT_PRUEBA_S + MARGEN_S) == (503, True)


async def test_salud_listo_503_no_filtra_detalles_de_la_dependencia() -> None:
    mensaje = "postgres://usuario@db:5432 rechazó la conexión"
    async with cliente_para(_app_con(SondaQueLanza(mensaje))) as cliente:
        texto = (await cliente.get("/api/v1/salud/listo")).text
    assert not any(fuga in texto for fuga in ("postgres", "@", "5432", "ConnectionError"))


async def test_salud_post_responde_405_metodo_no_permitido(
    cliente_api: httpx.AsyncClient,
) -> None:
    respuesta = await cliente_api.post("/api/v1/salud")
    assert (respuesta.status_code, respuesta.json()["type"]) == (405, "metodo_no_permitido")


async def test_salud_405_conserva_cabecera_allow(cliente_api: httpx.AsyncClient) -> None:
    respuesta = await cliente_api.post("/api/v1/salud")
    assert respuesta.headers["allow"] == "GET"
