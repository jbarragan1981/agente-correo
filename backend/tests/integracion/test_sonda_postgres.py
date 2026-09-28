"""Integración de `SondaPostgres` y de la readiness con PostgreSQL 17 real (requiere Docker)."""

import socket
import time
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from fastapi import FastAPI
from testcontainers.community.postgres import PostgresContainer

from app.application.ports.salud import ResultadoSonda
from app.core.config import Settings
from app.infrastructure.db.motor import crear_motor
from app.infrastructure.db.sonda_postgres import SondaPostgres
from app.main import crear_app
from tests.soporte import cliente_para, settings_prueba

IMAGEN_POSTGRES = "postgres:17-alpine"
TIMEOUT_BD_S = 1.0
MARGEN_S = 0.5


@pytest.fixture(scope="module")
def url_postgres() -> Iterator[str]:
    """Levanta PostgreSQL 17 en un contenedor efímero y devuelve su URL asyncpg."""
    with PostgresContainer(IMAGEN_POSTGRES, driver="asyncpg") as contenedor:
        yield contenedor.get_connection_url()


def _puerto_cerrado() -> int:
    """Obtiene un puerto local libre y lo cierra para que rechace conexiones."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _settings_bd(url: str) -> Settings:
    """Settings de prueba apuntando a la URL indicada."""
    return settings_prueba(database_url=url, salud_bd_timeout_s=TIMEOUT_BD_S)


def _url_caida() -> str:
    """URL hacia un puerto cerrado de 127.0.0.1 (contraseña de ejemplo)."""
    return f"postgresql+asyncpg://usuario:postgres@127.0.0.1:{_puerto_cerrado()}/agente_correo"


@pytest.fixture
async def app_con_bd(url_postgres: str) -> AsyncIterator[FastAPI]:
    """App real (sin sondas falsas) con su ciclo de vida activo contra el contenedor."""
    app = crear_app(_settings_bd(url_postgres))
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def app_bd_caida() -> AsyncIterator[FastAPI]:
    """App real con la BD inaccesible."""
    app = crear_app(_settings_bd(_url_caida()))
    async with app.router.lifespan_context(app):
        yield app


async def test_sonda_postgres_con_bd_real_devuelve_ok(url_postgres: str) -> None:
    motor = crear_motor(_settings_bd(url_postgres))
    try:
        resultado = await SondaPostgres(motor).comprobar()
    finally:
        await motor.dispose()
    assert resultado is ResultadoSonda.OK


async def test_sonda_postgres_puerto_cerrado_falla_dentro_del_timeout() -> None:
    motor = crear_motor(_settings_bd(_url_caida()))
    inicio = time.perf_counter()
    try:
        resultado = await SondaPostgres(motor).comprobar()
    finally:
        await motor.dispose()
    assert (resultado, time.perf_counter() - inicio <= TIMEOUT_BD_S + MARGEN_S) == (
        ResultadoSonda.FALLA,
        True,
    )


async def test_readiness_con_bd_real_responde_200(app_con_bd: FastAPI) -> None:
    async with cliente_para(app_con_bd) as cliente:
        respuesta = await cliente.get("/api/v1/salud/listo")
    assert (respuesta.status_code, respuesta.json()["comprobaciones"]) == (
        200,
        {"base_datos": "ok"},
    )


async def test_app_con_bd_caida_arranca_y_liveness_responde_200(app_bd_caida: FastAPI) -> None:
    async with cliente_para(app_bd_caida) as cliente:
        respuesta = await cliente.get("/api/v1/salud")
    assert respuesta.status_code == 200


async def test_readiness_con_bd_caida_responde_503_sin_detalles(app_bd_caida: FastAPI) -> None:
    async with cliente_para(app_bd_caida) as cliente:
        inicio = time.perf_counter()
        respuesta: httpx.Response = await cliente.get("/api/v1/salud/listo")
        duracion = time.perf_counter() - inicio
    assert (
        respuesta.status_code,
        respuesta.json()["type"],
        "127.0.0.1" in respuesta.text,
        duracion <= TIMEOUT_BD_S + MARGEN_S,
    ) == (503, "no_listo", False, True)
