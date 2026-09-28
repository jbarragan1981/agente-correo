"""Configuración común de pruebas: marcado por directorio, Settings de prueba y cliente ASGI."""

import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, Final

import httpx
import pytest
from fastapi import FastAPI

from app.application.ports.salud import ResultadoSonda
from app.main import crear_app
from tests.soporte import SondaFalsa, cliente_para, settings_prueba, usar_sondas

DIRECTORIO_PRUEBAS: Final = Path(__file__).parent
MARCADORES_POR_DIRECTORIO: Final = {"unit": "unit", "api": "api", "integracion": "integracion"}
VARIABLES_CONFIG: Final = (
    "ENV",
    "DEBUG",
    "LOG_LEVEL",
    "DATABASE_URL",
    "APP_MASTER_KEY",
    "JWT_SECRET",
    "CORS_ORIGENES",
    "SALUD_BD_TIMEOUT_S",
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Asigna el marcador según el directorio y rechaza pruebas fuera de los permitidos."""
    for item in items:
        relativa = item.path.relative_to(DIRECTORIO_PRUEBAS)
        marcador = MARCADORES_POR_DIRECTORIO.get(relativa.parts[0]) if relativa.parts else None
        if marcador is None or len(relativa.parts) < 2:
            mensaje = f"Prueba fuera de tests/unit, tests/api o tests/integracion: {relativa}"
            raise pytest.UsageError(mensaje)
        item.add_marker(marcador)


@pytest.fixture(autouse=True)
def _aislar_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evita que variables del entorno del desarrollador alteren `Settings`."""
    for variable in VARIABLES_CONFIG:
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def app_prueba() -> FastAPI:
    """App de prueba con una sonda falsa OK."""
    app = crear_app(settings_prueba())
    usar_sondas(app, SondaFalsa(ResultadoSonda.OK))
    return app


@pytest.fixture
async def cliente_api(app_prueba: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente httpx contra la app ASGI de prueba."""
    async with cliente_para(app_prueba) as cliente:
        yield cliente


@pytest.fixture
def capturar_logs(
    capsys: pytest.CaptureFixture[str],
) -> Callable[[], list[dict[str, Any]]]:
    """Devuelve una función que lee stdout y parsea cada línea como JSON."""
    lineas: list[str] = []

    def leer() -> list[dict[str, Any]]:
        lineas.extend(linea for linea in capsys.readouterr().out.splitlines() if linea.strip())
        return [json.loads(linea) for linea in lineas]

    return leer
