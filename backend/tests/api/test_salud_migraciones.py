"""`/api/v1/salud/listo` con la sonda `migraciones` (CA16, sondas falsas)."""

import httpx
import pytest
from fastapi import FastAPI

from app.application.ports.salud import ResultadoSonda
from app.main import crear_app
from tests.soporte import SondaFalsa, cliente_para, settings_prueba, usar_sondas

HEAD = "0005_revocar_alembic_version"


def _app(base_datos: ResultadoSonda, migraciones: ResultadoSonda) -> FastAPI:
    app = crear_app(settings_prueba())
    usar_sondas(
        app,
        SondaFalsa(base_datos, nombre="base_datos"),
        SondaFalsa(migraciones, nombre="migraciones"),
    )
    return app


async def _listo(app: FastAPI) -> httpx.Response:
    async with cliente_para(app) as cliente:
        return await cliente.get("/api/v1/salud/listo")


async def test_salud_migraciones_en_head_responde_200() -> None:
    respuesta = await _listo(_app(ResultadoSonda.OK, ResultadoSonda.OK))
    assert (respuesta.status_code, respuesta.json()) == (
        200,
        {"estado": "listo", "comprobaciones": {"base_datos": "ok", "migraciones": "ok"}},
    )


@pytest.mark.parametrize(
    ("base_datos", "migraciones"),
    [
        (ResultadoSonda.OK, ResultadoSonda.FALLA),
        (ResultadoSonda.FALLA, ResultadoSonda.FALLA),
    ],
)
async def test_salud_migraciones_desfasadas_responde_503(
    base_datos: ResultadoSonda, migraciones: ResultadoSonda
) -> None:
    respuesta = await _listo(_app(base_datos, migraciones))
    cuerpo = respuesta.json()
    assert (respuesta.status_code, cuerpo["type"], cuerpo["comprobaciones"]) == (
        503,
        "no_listo",
        {"base_datos": str(base_datos), "migraciones": "falla"},
    )


async def test_salud_migraciones_503_sin_revisiones_en_el_cuerpo() -> None:
    texto = (await _listo(_app(ResultadoSonda.OK, ResultadoSonda.FALLA))).text
    assert [fuga for fuga in (HEAD, "0003", "alembic", "version_num") if fuga in texto] == []


async def test_salud_migraciones_ejemplo_openapi_incluye_migraciones() -> None:
    async with cliente_para(crear_app(settings_prueba())) as cliente:
        esquema = (await cliente.get("/api/v1/openapi.json")).json()
    ejemplo = esquema["components"]["schemas"]["PreparacionOut"]["examples"][0]
    assert ejemplo["comprobaciones"] == {"base_datos": "ok", "migraciones": "ok"}
