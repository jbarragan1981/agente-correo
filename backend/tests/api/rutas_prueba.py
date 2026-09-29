"""Router solo de prueba que provoca 400, 409 y 500 (no se monta en la app real)."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.domain.errores import Conflicto


class EntradaPrueba(BaseModel):
    """Body de prueba con un campo sensible."""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(max_length=5)
    edad: int


router_prueba = APIRouter(prefix="/api/v1/prueba")


@router_prueba.post("/validar")
async def validar(entrada: EntradaPrueba) -> dict[str, str]:
    """Acepta el body si es válido."""
    return {"ok": entrada.password}


@router_prueba.get("/fallar")
async def fallar() -> None:
    """Lanza una excepción no manejada."""
    raise RuntimeError("marcador-interno")


@router_prueba.get("/conflicto")
async def conflicto() -> None:
    """Lanza una excepción de dominio."""
    raise Conflicto
