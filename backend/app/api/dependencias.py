"""Proveedores de dependencias FastAPI; las pruebas los sustituyen con `dependency_overrides`."""

from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.ports.salud import SondaDependenciaPort
from app.application.use_cases.comprobar_preparacion import ComprobarPreparacion
from app.core.config import Settings
from app.infrastructure.db.sonda_postgres import SondaPostgres


def dep_settings(request: Request) -> Settings:
    """Configuración con la que se creó la aplicación."""
    return cast(Settings, request.app.state.settings)


def dep_sondas(request: Request) -> list[SondaDependenciaPort]:
    """Sondas de preparación activas en esta épica."""
    motor = cast(AsyncEngine, request.app.state.motor)
    return [SondaPostgres(motor)]


def dep_comprobar_preparacion(
    settings: Annotated[Settings, Depends(dep_settings)],
    sondas: Annotated[list[SondaDependenciaPort], Depends(dep_sondas)],
) -> ComprobarPreparacion:
    """Caso de uso de preparación con el timeout configurado."""
    return ComprobarPreparacion(sondas, settings.salud_bd_timeout_s)
