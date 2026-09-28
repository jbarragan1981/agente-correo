"""Traducción de errores a respuestas `application/problem+json` (RFC 9457)."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Final, NamedTuple

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.middleware.correlacion import obtener_correlation_id
from app.api.schemas.problema import MEDIA_TYPE_PROBLEMA, ErrorCampo, Problema
from app.core.logging import obtener_logger
from app.domain.errores import Conflicto, ExcepcionDominio, NoEncontrado

_log = obtener_logger(__name__)

DETALLE_ERROR_INTERNO: Final = "Error interno. Cite el identificador al reportarlo."


class DescripcionProblema(NamedTuple):
    """Datos HTTP fijos de un tipo de problema."""

    status: int
    type: str
    title: str
    detail: str


NO_ENCONTRADO: Final = DescripcionProblema(
    404, "no_encontrado", "Recurso no encontrado", "El recurso solicitado no existe."
)
METODO_NO_PERMITIDO: Final = DescripcionProblema(
    405, "metodo_no_permitido", "Método no permitido", "El recurso no admite este método HTTP."
)
CONFLICTO: Final = DescripcionProblema(
    409, "conflicto", "Conflicto", "La operación choca con el estado actual del recurso."
)
VALIDACION: Final = DescripcionProblema(
    400, "validacion", "Petición inválida", "La petición contiene campos inválidos."
)
ERROR_INTERNO: Final = DescripcionProblema(
    500, "error_interno", "Error interno", DETALLE_ERROR_INTERNO
)
NO_LISTO: Final = DescripcionProblema(
    503, "no_listo", "Servicio no listo", "Una o más dependencias no están disponibles."
)

MAPEO_DOMINIO: Final[Mapping[type[ExcepcionDominio], DescripcionProblema]] = {
    NoEncontrado: NO_ENCONTRADO,
    Conflicto: CONFLICTO,
}

RESPUESTAS_ERROR: Final[dict[int | str, dict[str, Any]]] = {
    400: {"model": Problema, "description": "Petición inválida (`validacion`)."},
    404: {"model": Problema, "description": "Recurso no encontrado (`no_encontrado`)."},
    500: {"model": Problema, "description": "Error interno (`error_interno`)."},
}


class RespuestaProblema(JSONResponse):
    """Respuesta JSON con media type `application/problem+json`."""

    media_type = MEDIA_TYPE_PROBLEMA


def respuesta_problema(
    correlation_id: str,
    descripcion: DescripcionProblema,
    extensiones: Mapping[str, object] | None = None,
    cabeceras: Mapping[str, str] | None = None,
) -> RespuestaProblema:
    """Construye la respuesta de error con `instance` ligado al correlation id."""
    cuerpo = Problema.model_validate(
        {
            **(extensiones or {}),
            "type": descripcion.type,
            "title": descripcion.title,
            "status": descripcion.status,
            "detail": descripcion.detail,
            "instance": f"urn:uuid:{correlation_id}",
        }
    )
    return RespuestaProblema(
        content=cuerpo.model_dump(mode="json"),
        status_code=descripcion.status,
        headers=dict(cabeceras) if cabeceras else None,
    )


def describir_excepcion_dominio(exc: ExcepcionDominio) -> DescripcionProblema:
    """Busca en la jerarquía de la excepción su descripción HTTP; si no hay, es error interno."""
    for clase in type(exc).__mro__:
        descripcion = MAPEO_DOMINIO.get(clase)
        if descripcion is not None:
            return descripcion
    _log.error("http.excepcion_dominio_sin_mapeo", tipo_error=type(exc).__name__)
    return ERROR_INTERNO


def describir_http(status: int) -> DescripcionProblema:
    """Traduce un código HTTP de Starlette a su descripción de problema."""
    if status == NO_ENCONTRADO.status:
        return NO_ENCONTRADO
    if status == METODO_NO_PERMITIDO.status:
        return METODO_NO_PERMITIDO
    try:
        frase = HTTPStatus(status).phrase
    except ValueError:
        frase = "Error HTTP"
    return DescripcionProblema(status, "error_http", frase, frase)


def errores_de_validacion(exc: RequestValidationError) -> list[ErrorCampo]:
    """Convierte los errores de validación a campo y mensaje, sin `input` ni `ctx`."""
    return [
        ErrorCampo(
            campo=".".join(str(parte) for parte in error.get("loc", ())),
            mensaje=str(error.get("msg", "")),
        )
        for error in exc.errors()
    ]


async def manejar_validacion(request: Request, exc: Exception) -> RespuestaProblema:
    """Responde 400 `validacion` con el detalle por campo."""
    errores = errores_de_validacion(exc) if isinstance(exc, RequestValidationError) else []
    return respuesta_problema(
        obtener_correlation_id(request.scope),
        VALIDACION,
        {"errores": [error.model_dump() for error in errores]},
    )


async def manejar_http(request: Request, exc: Exception) -> RespuestaProblema:
    """Responde los `HTTPException` de Starlette/FastAPI como problem+json."""
    status = exc.status_code if isinstance(exc, StarletteHTTPException) else 500
    cabeceras = exc.headers if isinstance(exc, StarletteHTTPException) else None
    return respuesta_problema(
        obtener_correlation_id(request.scope), describir_http(status), cabeceras=cabeceras
    )


async def manejar_dominio(request: Request, exc: Exception) -> RespuestaProblema:
    """Responde las excepciones de dominio según `MAPEO_DOMINIO`."""
    descripcion = (
        describir_excepcion_dominio(exc) if isinstance(exc, ExcepcionDominio) else ERROR_INTERNO
    )
    return respuesta_problema(obtener_correlation_id(request.scope), descripcion)


def registrar_manejadores(app: FastAPI) -> None:
    """Registra los manejadores problem+json en la aplicación."""
    app.add_exception_handler(RequestValidationError, manejar_validacion)
    app.add_exception_handler(StarletteHTTPException, manejar_http)
    app.add_exception_handler(ExcepcionDominio, manejar_dominio)
