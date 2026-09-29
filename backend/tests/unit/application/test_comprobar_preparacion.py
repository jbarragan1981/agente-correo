"""Pruebas del caso de uso `ComprobarPreparacion` con sondas falsas."""

import time

from app.application.ports.salud import ResultadoSonda
from app.application.use_cases.comprobar_preparacion import ComprobarPreparacion
from tests.soporte import SondaColgada, SondaFalsa, SondaQueLanza

TIMEOUT_S = 0.05
MARGEN_S = 0.5


async def test_preparacion_todas_ok_esta_lista() -> None:
    caso = ComprobarPreparacion(
        [SondaFalsa(nombre="base_datos"), SondaFalsa(nombre="migraciones")], TIMEOUT_S
    )
    assert (await caso.ejecutar()).listo


async def test_preparacion_una_falla_no_esta_lista_y_la_nombra() -> None:
    caso = ComprobarPreparacion(
        [
            SondaFalsa(ResultadoSonda.OK, nombre="base_datos"),
            SondaFalsa(ResultadoSonda.FALLA, nombre="migraciones"),
        ],
        TIMEOUT_S,
    )
    informe = await caso.ejecutar()
    assert (informe.listo, dict(informe.comprobaciones)) == (
        False,
        {"base_datos": ResultadoSonda.OK, "migraciones": ResultadoSonda.FALLA},
    )


async def test_preparacion_sonda_que_excede_timeout_es_falla() -> None:
    informe = await ComprobarPreparacion([SondaColgada()], TIMEOUT_S).ejecutar()
    assert informe.comprobaciones["base_datos"] is ResultadoSonda.FALLA


async def test_preparacion_sonda_colgada_responde_dentro_del_margen() -> None:
    inicio = time.perf_counter()
    await ComprobarPreparacion([SondaColgada()], TIMEOUT_S).ejecutar()
    assert time.perf_counter() - inicio <= TIMEOUT_S + MARGEN_S


async def test_preparacion_sonda_que_lanza_es_falla() -> None:
    informe = await ComprobarPreparacion([SondaQueLanza("marcador-interno")], TIMEOUT_S).ejecutar()
    assert informe.comprobaciones["base_datos"] is ResultadoSonda.FALLA


async def test_preparacion_sonda_que_lanza_no_filtra_el_mensaje() -> None:
    informe = await ComprobarPreparacion([SondaQueLanza("marcador-interno")], TIMEOUT_S).ejecutar()
    assert "marcador-interno" not in repr(informe)


async def test_preparacion_sin_sondas_esta_lista() -> None:
    assert (await ComprobarPreparacion([], TIMEOUT_S).ejecutar()).listo
