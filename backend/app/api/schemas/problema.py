"""Esquema de error RFC 9457 (`application/problem+json`)."""

from pydantic import BaseModel, ConfigDict, Field

MEDIA_TYPE_PROBLEMA = "application/problem+json"


class ErrorCampo(BaseModel):
    """Error de validación de un campo; nunca incluye el valor recibido."""

    model_config = ConfigDict(extra="forbid")

    campo: str = Field(description="Ubicación del campo unida por puntos.", examples=["body.email"])
    mensaje: str = Field(description="Mensaje de validación.", examples=["Field required"])


class Problema(BaseModel):
    """Detalle de problema; admite extensiones como `errores` o `comprobaciones`."""

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "type": "no_encontrado",
                    "title": "Recurso no encontrado",
                    "status": 404,
                    "detail": "El recurso solicitado no existe.",
                    "instance": "urn:uuid:3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10",
                }
            ]
        },
    )

    type: str = Field(description="Código de error de docs/04-api.md §12.")
    title: str
    status: int
    detail: str | None = None
    instance: str = Field(description="`urn:uuid:<correlation_id>` de la petición.")
