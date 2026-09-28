"""Ajustes del esquema OpenAPI: errores como `application/problem+json`."""

from typing import Any, Final

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.schemas.problema import MEDIA_TYPE_PROBLEMA

MEDIA_TYPE_JSON: Final = "application/json"
ESQUEMAS_VALIDACION_FASTAPI: Final = ("HTTPValidationError", "ValidationError")
REF_VALIDACION_FASTAPI: Final = "#/components/schemas/HTTPValidationError"


def _es_error(codigo: str) -> bool:
    """Indica si el código de respuesta OpenAPI es 4xx/5xx."""
    return codigo.isdigit() and int(codigo) >= 400


def _es_validacion_fastapi(respuesta: dict[str, Any]) -> bool:
    """Detecta la respuesta 422 automática de FastAPI (este backend responde 400)."""
    esquema = respuesta.get("content", {}).get(MEDIA_TYPE_JSON, {}).get("schema", {})
    return esquema.get("$ref") == REF_VALIDACION_FASTAPI


def _ajustar_respuestas(respuestas: dict[str, Any]) -> None:
    """Quita el 422 automático y publica los errores bajo `application/problem+json`."""
    if _es_validacion_fastapi(respuestas.get("422", {})):
        del respuestas["422"]
    for codigo, respuesta in respuestas.items():
        contenido = respuesta.get("content", {})
        if _es_error(codigo) and MEDIA_TYPE_JSON in contenido:
            json = contenido.pop(MEDIA_TYPE_JSON)
            contenido[MEDIA_TYPE_PROBLEMA] = {**json, **contenido.get(MEDIA_TYPE_PROBLEMA, {})}


def ajustar_esquema(esquema: dict[str, Any]) -> dict[str, Any]:
    """Aplica los ajustes de errores a todas las operaciones del esquema."""
    for operaciones in esquema.get("paths", {}).values():
        for operacion in operaciones.values():
            _ajustar_respuestas(operacion.get("responses", {}))
    componentes = esquema.get("components", {}).get("schemas", {})
    for nombre in ESQUEMAS_VALIDACION_FASTAPI:
        componentes.pop(nombre, None)
    return esquema


class AplicacionApi(FastAPI):
    """FastAPI con el esquema OpenAPI ajustado a problem+json."""

    def openapi(self) -> dict[str, Any]:
        """Genera y cachea el esquema ajustado."""
        if self.openapi_schema is None:
            self.openapi_schema = ajustar_esquema(
                get_openapi(
                    title=self.title,
                    version=self.version,
                    description=self.description,
                    routes=self.routes,
                    tags=self.openapi_tags,
                )
            )
        return self.openapi_schema
