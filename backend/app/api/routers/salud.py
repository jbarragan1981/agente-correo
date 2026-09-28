"""Sondas públicas de liveness y readiness (`docs/04-api.md` §9)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.api.dependencias import dep_comprobar_preparacion
from app.api.errores import NO_LISTO, respuesta_problema
from app.api.middleware.correlacion import obtener_correlation_id
from app.api.schemas.problema import MEDIA_TYPE_PROBLEMA, Problema
from app.api.schemas.salud import PreparacionOut, SaludOut
from app.application.use_cases.comprobar_preparacion import ComprobarPreparacion

router = APIRouter(prefix="/salud", tags=["salud"])

RESPUESTA_NO_LISTO: dict[int | str, dict[str, Any]] = {
    503: {
        "model": Problema,
        "description": "Alguna dependencia no está disponible (`no_listo`).",
        "content": {
            MEDIA_TYPE_PROBLEMA: {
                "example": {
                    "type": "no_listo",
                    "title": "Servicio no listo",
                    "status": 503,
                    "detail": "Una o más dependencias no están disponibles.",
                    "instance": "urn:uuid:3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10",
                    "comprobaciones": {"base_datos": "falla"},
                }
            }
        },
    }
}


@router.get("", response_model=SaludOut, summary="Liveness")
async def vivo() -> SaludOut:
    """Indica que el proceso responde; no consulta dependencias."""
    return SaludOut(estado="vivo")


@router.get(
    "/listo", response_model=PreparacionOut, responses=RESPUESTA_NO_LISTO, summary="Readiness"
)
async def listo(
    request: Request,
    caso_de_uso: Annotated[ComprobarPreparacion, Depends(dep_comprobar_preparacion)],
) -> Response | PreparacionOut:
    """Comprueba las dependencias; 503 `no_listo` si alguna falla."""
    informe = await caso_de_uso.ejecutar()
    comprobaciones = {
        nombre: str(resultado) for nombre, resultado in informe.comprobaciones.items()
    }
    if informe.listo:
        return PreparacionOut.model_validate({"estado": "listo", "comprobaciones": comprobaciones})
    return respuesta_problema(
        obtener_correlation_id(request.scope), NO_LISTO, {"comprobaciones": comprobaciones}
    )
