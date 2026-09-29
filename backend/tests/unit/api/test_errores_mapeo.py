"""Pruebas de la tabla ExcepcionDominio → HTTP y de la construcción de problemas."""

import json

import pytest

from app.api.errores import (
    ERROR_INTERNO,
    NO_ENCONTRADO,
    DescripcionProblema,
    describir_excepcion_dominio,
    describir_http,
    respuesta_problema,
)
from app.api.schemas.problema import MEDIA_TYPE_PROBLEMA
from app.domain.errores import Conflicto, ExcepcionDominio, NoEncontrado

ID_PRUEBA = "3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10"


class CuentaNoEncontrada(NoEncontrado):
    """Subclase de dominio para probar la búsqueda por jerarquía."""


@pytest.mark.parametrize(
    ("excepcion", "esperado"),
    [
        (NoEncontrado(), (404, "no_encontrado")),
        (Conflicto(), (409, "conflicto")),
        (CuentaNoEncontrada(), (404, "no_encontrado")),
        (ExcepcionDominio(), (500, "error_interno")),
    ],
    ids=["no_encontrado", "conflicto", "subclase", "sin_mapeo"],
)
def test_describir_excepcion_dominio_mapea_status_y_tipo(
    excepcion: ExcepcionDominio, esperado: tuple[int, str]
) -> None:
    descripcion = describir_excepcion_dominio(excepcion)
    assert (descripcion.status, descripcion.type) == esperado


@pytest.mark.parametrize(
    ("status", "tipo"),
    [
        (404, "no_encontrado"),
        (405, "metodo_no_permitido"),
        (418, "error_http"),
        (499, "error_http"),
    ],
)
def test_describir_http_asigna_tipo(status: int, tipo: str) -> None:
    assert describir_http(status).type == tipo


def test_respuesta_problema_usa_media_type_problem_json() -> None:
    respuesta = respuesta_problema(ID_PRUEBA, NO_ENCONTRADO)
    assert respuesta.media_type == MEDIA_TYPE_PROBLEMA


def test_respuesta_problema_instance_es_urn_del_correlation_id() -> None:
    cuerpo = json.loads(bytes(respuesta_problema(ID_PRUEBA, ERROR_INTERNO).body))
    assert cuerpo["instance"] == f"urn:uuid:{ID_PRUEBA}"


def test_respuesta_problema_extensiones_no_pisan_campos_estandar() -> None:
    descripcion = DescripcionProblema(409, "conflicto", "Conflicto", "detalle")
    cuerpo = json.loads(bytes(respuesta_problema(ID_PRUEBA, descripcion, {"status": 200}).body))
    assert cuerpo["status"] == 409
