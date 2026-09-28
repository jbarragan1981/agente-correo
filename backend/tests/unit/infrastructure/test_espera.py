"""Espera de PostgreSQL con backoff acotado (reloj y conector falsos)."""

import asyncpg
import pytest
from sqlalchemy.engine import URL, make_url

from app.infrastructure.db.bootstrap.errores import AutenticacionRechazada, BdNoDisponible
from app.infrastructure.db.bootstrap.espera import (
    ESPERA_MAXIMA_S,
    Conectar,
    esperar_postgres,
    siguiente_espera,
)

URL_PRUEBA = make_url("postgresql+psycopg://u:postgres@127.0.0.1:5432/agente")


class RelojFalso:
    """Reloj que avanza solo cuando se duerme."""

    def __init__(self) -> None:
        self.ahora = 0.0
        self.esperas: list[float] = []

    def __call__(self) -> float:
        return self.ahora

    async def dormir(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.ahora += segundos


def _conector(fallos: list[BaseException]) -> Conectar:
    """Conector que lanza los fallos indicados en orden y luego conecta."""
    pendientes = list(fallos)

    async def conectar(url: URL, timeout_s: float) -> None:
        if pendientes:
            raise pendientes.pop(0)

    return conectar


async def test_espera_conecta_al_primer_intento() -> None:
    reloj = RelojFalso()
    intentos = await esperar_postgres(URL_PRUEBA, 10, _conector([]), reloj.dormir, reloj)
    assert (intentos, reloj.esperas) == (1, [])


async def test_espera_reintenta_con_backoff_exponencial() -> None:
    reloj = RelojFalso()
    fallos: list[BaseException] = [ConnectionRefusedError()] * 4
    intentos = await esperar_postgres(URL_PRUEBA, 60, _conector(fallos), reloj.dormir, reloj)
    assert (intentos, reloj.esperas) == (5, [0.5, 1.0, 2.0, 4.0])


def test_espera_backoff_no_supera_el_maximo() -> None:
    assert siguiente_espera(4.0) == siguiente_espera(ESPERA_MAXIMA_S) == ESPERA_MAXIMA_S


async def test_espera_base_inexistente_cuenta_como_servidor_disponible() -> None:
    reloj = RelojFalso()
    fallos: list[BaseException] = [asyncpg.InvalidCatalogNameError("no existe")]
    assert await esperar_postgres(URL_PRUEBA, 10, _conector(fallos), reloj.dormir, reloj) == 1


async def test_espera_credencial_rechazada_falla_sin_esperar() -> None:
    reloj = RelojFalso()
    fallos: list[BaseException] = [asyncpg.InvalidPasswordError("rechazada")]
    with pytest.raises(AutenticacionRechazada):
        await esperar_postgres(URL_PRUEBA, 10, _conector(fallos), reloj.dormir, reloj)
    assert reloj.esperas == []


async def test_espera_agota_el_tiempo_con_bd_no_disponible() -> None:
    reloj = RelojFalso()
    fallos: list[BaseException] = [OSError("rechazada")] * 100
    with pytest.raises(BdNoDisponible) as error:
        await esperar_postgres(URL_PRUEBA, 3, _conector(fallos), reloj.dormir, reloj)
    assert (sum(reloj.esperas), error.value.tipo_error, error.value.paso) == (
        3.0,
        "OSError",
        "espera",
    )


async def test_espera_arranque_en_curso_se_reintenta() -> None:
    reloj = RelojFalso()
    fallos: list[BaseException] = [asyncpg.CannotConnectNowError("arrancando"), TimeoutError()]
    assert await esperar_postgres(URL_PRUEBA, 10, _conector(fallos), reloj.dormir, reloj) == 3
