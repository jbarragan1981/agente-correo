"""Auxiliares compartidos por las pruebas: Settings de ejemplo, sondas falsas y cliente ASGI."""

import asyncio
import base64
from typing import Any, Final

import httpx
from fastapi import FastAPI

from app.api.dependencias import dep_sondas
from app.application.ports.salud import ResultadoSonda, SondaDependenciaPort
from app.core.config import Settings

ORIGEN_PERMITIDO: Final = "https://panel.ejemplo.com"
APP_MASTER_KEY_PRUEBA: Final = base64.b64encode(b"k" * 32).decode()
JWT_SECRET_PRUEBA: Final = "j" * 40
DATABASE_URL_PRUEBA: Final = "postgresql+asyncpg://usuario:clave-de-prueba@bd.ejemplo:5432/agente"
TIMEOUT_PRUEBA_S: Final = 0.2


def settings_prueba(**cambios: Any) -> Settings:
    """Settings de entorno `test` con valores de ejemplo, sin leer `.env`."""
    valores: dict[str, Any] = {
        "env": "test",
        "cors_origenes": [ORIGEN_PERMITIDO],
        "salud_bd_timeout_s": TIMEOUT_PRUEBA_S,
    }
    return Settings(_env_file=None, **(valores | cambios))


def valores_produccion(**cambios: Any) -> dict[str, Any]:
    """Valores válidos para `ENV=production`, modificables por prueba."""
    valores: dict[str, Any] = {
        "env": "production",
        "app_master_key": APP_MASTER_KEY_PRUEBA,
        "jwt_secret": JWT_SECRET_PRUEBA,
        "database_url": DATABASE_URL_PRUEBA,
        "cors_origenes": ORIGEN_PERMITIDO,
        "db_roles_separados": True,
    }
    return valores | cambios


class SondaFalsa:
    """Sonda con resultado y retardo configurables."""

    def __init__(
        self,
        resultado: ResultadoSonda = ResultadoSonda.OK,
        retardo_s: float = 0.0,
        nombre: str = "base_datos",
    ) -> None:
        self._resultado = resultado
        self._retardo_s = retardo_s
        self._nombre = nombre

    @property
    def nombre(self) -> str:
        """Nombre simulado de la dependencia."""
        return self._nombre

    async def comprobar(self) -> ResultadoSonda:
        """Devuelve el resultado configurado tras el retardo."""
        if self._retardo_s:
            await asyncio.sleep(self._retardo_s)
        return self._resultado


class SondaEspia(SondaFalsa):
    """Sonda que cuenta sus llamadas."""

    def __init__(self) -> None:
        super().__init__(ResultadoSonda.OK)
        self.llamadas = 0

    async def comprobar(self) -> ResultadoSonda:
        """Registra la llamada y devuelve OK."""
        self.llamadas += 1
        return await super().comprobar()


def usar_sondas(app: FastAPI, *sondas: SondaDependenciaPort) -> None:
    """Sustituye las sondas reales de la app por las indicadas."""
    app.dependency_overrides[dep_sondas] = lambda: list(sondas)


def cliente_para(app: FastAPI) -> httpx.AsyncClient:
    """Crea un cliente httpx para cualquier app ASGI."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba")


class SondaColgada(SondaFalsa):
    """Sonda que nunca responde; solo termina por cancelación (timeout)."""

    async def comprobar(self) -> ResultadoSonda:
        """Espera un evento que nadie activa."""
        await asyncio.Event().wait()
        return ResultadoSonda.OK


class SondaQueLanza(SondaFalsa):
    """Sonda defectuosa que lanza una excepción con un mensaje marcador."""

    def __init__(self, mensaje: str) -> None:
        super().__init__()
        self._mensaje = mensaje

    async def comprobar(self) -> ResultadoSonda:
        """Lanza siempre."""
        raise ConnectionError(self._mensaje)
