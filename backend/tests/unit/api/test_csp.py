"""Pruebas de `csp_para` y `aplicar_cabeceras`."""

import pytest
from starlette.datastructures import MutableHeaders

from app.api.middleware.cabeceras import (
    CSP_API,
    CSP_DOCUMENTACION,
    aplicar_cabeceras,
    csp_para,
)


@pytest.mark.parametrize(
    "ruta",
    ["/api/v1/salud", "/api/v1/openapi.json", "/api/v1/docs/oauth2-redirect", "/docs", "/"],
)
def test_csp_para_ruta_de_api_es_estricta(ruta: str) -> None:
    assert csp_para(ruta) == CSP_API


@pytest.mark.parametrize("ruta", ["/api/v1/docs", "/api/v1/redoc"])
def test_csp_para_documentacion_permite_swagger(ruta: str) -> None:
    assert csp_para(ruta) == CSP_DOCUMENTACION


def test_csp_documentacion_no_permite_scripts_en_linea_arbitrarios() -> None:
    directiva_script = next(
        parte for parte in CSP_DOCUMENTACION.split(";") if "script-src" in parte
    )
    assert "'unsafe-inline'" not in directiva_script


def test_aplicar_cabeceras_elimina_server() -> None:
    cabeceras = MutableHeaders(headers={"server": "uvicorn"})
    aplicar_cabeceras(cabeceras, "/api/v1/salud")
    assert "server" not in cabeceras


def test_aplicar_cabeceras_respeta_cache_control_propio() -> None:
    cabeceras = MutableHeaders(headers={"cache-control": "max-age=60"})
    aplicar_cabeceras(cabeceras, "/api/v1/salud")
    assert cabeceras["cache-control"] == "max-age=60"
