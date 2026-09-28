"""Pruebas API del arranque: fallo cerrado, ciclo de vida y dependencias reales."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from app.api.dependencias import dep_comprobar_preparacion, dep_settings, dep_sondas
from app.core.config import Settings
from app.infrastructure.db.sonda_postgres import SondaPostgres
from app.main import crear_app
from tests.soporte import JWT_SECRET_PRUEBA, settings_prueba

LeerLogs = Callable[[], list[dict[str, Any]]]


@pytest.fixture
def entorno_produccion_incompleto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Entorno de producción sin claves y sin `.env`."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET_PRUEBA[:10])


@pytest.mark.usefixtures("entorno_produccion_incompleto")
def test_arranque_produccion_sin_claves_termina_con_codigo_1() -> None:
    with pytest.raises(SystemExit) as salida:
        crear_app()
    assert salida.value.code == 1


@pytest.mark.usefixtures("entorno_produccion_incompleto")
def test_arranque_fallido_registra_campos_sin_valores(capturar_logs: LeerLogs) -> None:
    with pytest.raises(SystemExit):
        crear_app()
    salida = json.dumps(capturar_logs())
    assert ("JWT_SECRET" in salida, JWT_SECRET_PRUEBA[:10] in salida) == (True, False)


def test_arranque_sin_argumentos_lee_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    app = crear_app()
    assert app.state.settings.log_level == "WARNING"


class MotorEspia:
    """Sustituto del motor que registra su liberación."""

    def __init__(self) -> None:
        self.liberado = False

    async def dispose(self) -> None:
        """Marca el motor como liberado."""
        self.liberado = True


async def test_arranque_ciclo_de_vida_libera_el_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    espia = MotorEspia()
    monkeypatch.setattr("app.main.crear_motor", lambda _settings: espia)
    app = crear_app(settings_prueba())
    async with app.router.lifespan_context(app):
        pass
    assert (app.state.motor, espia.liberado) == (espia, True)


def _peticion(app: FastAPI) -> Request:
    """Petición ASGI mínima ligada a la app."""
    return Request({"type": "http", "app": app, "headers": []})


async def test_arranque_dependencias_reales_usan_sonda_postgres() -> None:
    app = crear_app(settings_prueba())
    async with app.router.lifespan_context(app):
        sondas = dep_sondas(_peticion(app))
    assert [type(sonda) for sonda in sondas] == [SondaPostgres]


async def test_arranque_caso_de_uso_recibe_timeout_de_settings() -> None:
    app = crear_app(settings_prueba(salud_bd_timeout_s=1.5))
    caso = dep_comprobar_preparacion(dep_settings(_peticion(app)), [])
    assert caso._timeout_s == 1.5
