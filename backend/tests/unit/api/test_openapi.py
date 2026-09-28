"""Pruebas de `ajustar_esquema` (errores como problem+json en OpenAPI)."""

from typing import Any

from app.api.openapi import ajustar_esquema


def _esquema(respuestas: dict[str, Any]) -> dict[str, Any]:
    """Esquema mínimo con una operación y los componentes de validación de FastAPI."""
    return {
        "paths": {"/x": {"post": {"responses": respuestas}}},
        "components": {"schemas": {"HTTPValidationError": {}, "ValidationError": {}}},
    }


def _ref(nombre: str) -> dict[str, Any]:
    """Contenido JSON con referencia a un componente."""
    return {"application/json": {"schema": {"$ref": f"#/components/schemas/{nombre}"}}}


def test_ajustar_esquema_quita_422_automatico_de_fastapi() -> None:
    esquema = ajustar_esquema(_esquema({"422": {"content": _ref("HTTPValidationError")}}))
    assert "422" not in esquema["paths"]["/x"]["post"]["responses"]


def test_ajustar_esquema_conserva_422_propio() -> None:
    esquema = ajustar_esquema(_esquema({"422": {"content": _ref("Problema")}}))
    assert (
        "application/problem+json" in esquema["paths"]["/x"]["post"]["responses"]["422"]["content"]
    )


def test_ajustar_esquema_mueve_errores_a_problem_json() -> None:
    esquema = ajustar_esquema(_esquema({"404": {"content": _ref("Problema")}}))
    assert list(esquema["paths"]["/x"]["post"]["responses"]["404"]["content"]) == [
        "application/problem+json"
    ]


def test_ajustar_esquema_no_toca_respuestas_2xx() -> None:
    esquema = ajustar_esquema(_esquema({"200": {"content": _ref("SaludOut")}}))
    assert "application/json" in esquema["paths"]["/x"]["post"]["responses"]["200"]["content"]


def test_ajustar_esquema_elimina_componentes_de_validacion_de_fastapi() -> None:
    esquema = ajustar_esquema(_esquema({}))
    assert esquema["components"]["schemas"] == {}
