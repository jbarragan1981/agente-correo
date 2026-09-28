"""Fábrica de la aplicación: `uvicorn --factory app.main:crear_app`.

Importar este módulo no lee el entorno ni abre conexiones (ADR-0007).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Final

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.errores import RESPUESTAS_ERROR, registrar_manejadores
from app.api.middleware.cabeceras import (
    RUTA_DOCS,
    RUTA_OAUTH2_REDIRECT,
    RUTA_OPENAPI,
    RUTA_REDOC,
    CabecerasSeguridadMiddleware,
)
from app.api.middleware.correlacion import CABECERA_ID, CorrelacionMiddleware
from app.api.middleware.errores_inesperados import ErroresInesperadosMiddleware
from app.api.openapi import AplicacionApi
from app.api.routers import salud
from app.core.config import ConfiguracionInvalida, NivelLog, Settings, cargar_settings
from app.core.logging import configurar_logging, obtener_logger
from app.infrastructure.db.motor import crear_motor

PREFIJO_API: Final = "/api/v1"
METODOS_CORS: Final = ["GET", "POST", "PUT", "PATCH", "DELETE"]
CABECERAS_CORS: Final = ["Authorization", "Content-Type", CABECERA_ID, "Idempotency-Key"]
CABECERAS_EXPUESTAS: Final = [CABECERA_ID, "Retry-After"]
MAX_AGE_CORS_S: Final = 600
CODIGO_SALIDA_CONFIG_INVALIDA: Final = 1

_log = obtener_logger(__name__)


@asynccontextmanager
async def _ciclo_de_vida(app: FastAPI) -> AsyncGenerator[None]:
    """Crea el motor sin conectar (la API arranca con la BD caída) y lo libera al apagar."""
    motor = crear_motor(app.state.settings)
    app.state.motor = motor
    try:
        yield
    finally:
        await motor.dispose()


def _nivel_log(settings: Settings) -> NivelLog:
    """`DEBUG=true` solo sube el nivel de log."""
    return "DEBUG" if settings.debug else settings.log_level


def _cargar_o_fallar() -> Settings:
    """Carga la configuración; si es inválida registra los campos (sin valores) y termina."""
    try:
        return cargar_settings()
    except ConfiguracionInvalida as error:
        configurar_logging("INFO")
        _log.critical(
            "config.invalida",
            errores=[{"campo": campo, "mensaje": mensaje} for campo, mensaje in error.errores],
        )
        raise SystemExit(CODIGO_SALIDA_CONFIG_INVALIDA) from None


def _router_v1() -> APIRouter:
    """Router con prefijo `/api/v1` y respuestas de error compartidas."""
    router = APIRouter(prefix=PREFIJO_API, responses=RESPUESTAS_ERROR)
    router.include_router(salud.router)
    return router


def _registrar_middlewares(app: FastAPI, settings: Settings) -> None:
    """Orden efectivo (de fuera a dentro): Correlación → Cabeceras → CORS → Errores → router."""
    app.add_middleware(ErroresInesperadosMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origenes),
        allow_credentials=True,
        allow_methods=METODOS_CORS,
        allow_headers=CABECERAS_CORS,
        expose_headers=CABECERAS_EXPUESTAS,
        max_age=MAX_AGE_CORS_S,
    )
    app.add_middleware(CabecerasSeguridadMiddleware)
    app.add_middleware(CorrelacionMiddleware)


def crear_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación; sin `settings` los carga del entorno y falla cerrado."""
    config = settings if settings is not None else _cargar_o_fallar()
    configurar_logging(_nivel_log(config))
    documentacion = not config.es_produccion
    app = AplicacionApi(
        title="Agente Correo API",
        version="0.1.0",
        debug=False,
        lifespan=_ciclo_de_vida,
        docs_url=RUTA_DOCS if documentacion else None,
        redoc_url=RUTA_REDOC if documentacion else None,
        openapi_url=RUTA_OPENAPI if documentacion else None,
        swagger_ui_oauth2_redirect_url=RUTA_OAUTH2_REDIRECT,
    )
    app.state.settings = config
    registrar_manejadores(app)
    app.include_router(_router_v1())
    _registrar_middlewares(app, config)
    return app
