"""Pruebas de validación del correlation id (R6)."""

import uuid

import pytest

from app.api.middleware.correlacion import correlation_id_valido, obtener_correlation_id

UUID_VALIDO = "3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10"


def test_correlation_id_uuid_valido_se_propaga() -> None:
    assert correlation_id_valido(UUID_VALIDO) == UUID_VALIDO


def test_correlation_id_uuid_en_mayusculas_se_normaliza() -> None:
    assert correlation_id_valido(UUID_VALIDO.upper()) == UUID_VALIDO


@pytest.mark.parametrize(
    "valor",
    [
        None,
        "",
        "no-es-un-uuid",
        "a" * 200,
        f"{UUID_VALIDO[:-2]}\r\n",
        "{" + UUID_VALIDO[:-2] + "}",
        UUID_VALIDO.replace("-", ""),
    ],
    ids=["ausente", "vacio", "texto", "largo", "crlf", "llaves", "sin_guiones"],
)
def test_correlation_id_invalido_se_reemplaza_por_uuid_nuevo(valor: str | None) -> None:
    resultado = correlation_id_valido(valor)
    assert (resultado != valor, str(uuid.UUID(resultado)) == resultado) == (True, True)


def test_obtener_correlation_id_sin_middleware_genera_y_guarda() -> None:
    scope: dict[str, object] = {"type": "http"}
    generado = obtener_correlation_id(scope)
    assert obtener_correlation_id(scope) == generado
