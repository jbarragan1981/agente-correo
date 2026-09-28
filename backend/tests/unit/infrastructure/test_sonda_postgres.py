"""Pruebas unitarias de `SondaPostgres` con un motor falso (la integración real usa Docker)."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.ports.salud import ResultadoSonda
from app.infrastructure.db.sonda_postgres import CONSULTA_SONDA, SondaPostgres


class ConexionFalsa:
    """Conexión que registra las consultas ejecutadas."""

    def __init__(self) -> None:
        self.consultas: list[Any] = []

    async def execute(self, consulta: Any) -> None:
        """Registra la consulta."""
        self.consultas.append(consulta)


class MotorFalso:
    """Motor cuyo `connect` entrega una conexión falsa o lanza el error indicado."""

    def __init__(self, error: Exception | None = None) -> None:
        self.conexion = ConexionFalsa()
        self._error = error

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[ConexionFalsa]:
        """Simula la apertura de conexión."""
        if self._error is not None:
            raise self._error
        yield self.conexion


def _sonda(motor: MotorFalso) -> SondaPostgres:
    """Sonda con el motor falso tipado como AsyncEngine."""
    return SondaPostgres(cast(AsyncEngine, motor))


async def test_sonda_postgres_conexion_ok_devuelve_ok() -> None:
    assert await _sonda(MotorFalso()).comprobar() is ResultadoSonda.OK


async def test_sonda_postgres_ejecuta_select_1() -> None:
    motor = MotorFalso()
    await _sonda(motor).comprobar()
    assert motor.conexion.consultas == [CONSULTA_SONDA]


async def test_sonda_postgres_error_de_conexion_devuelve_falla() -> None:
    motor = MotorFalso(ConnectionRefusedError("127.0.0.1:5432 rechazada"))
    assert await _sonda(motor).comprobar() is ResultadoSonda.FALLA


def test_sonda_postgres_se_nombra_base_datos() -> None:
    assert _sonda(MotorFalso()).nombre == "base_datos"
