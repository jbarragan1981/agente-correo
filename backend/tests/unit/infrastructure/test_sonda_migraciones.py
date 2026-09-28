"""`SondaMigraciones`: OK, desfasada, tabla ausente o excepción → FALLA sin lanzar."""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.exc import ProgrammingError

from app.application.ports.salud import ResultadoSonda
from app.infrastructure.db.sonda_migraciones import SondaMigraciones

HEAD = "0005_revocar_alembic_version"


class _Resultado:
    def __init__(self, filas: list[str]) -> None:
        self._filas = filas

    def scalars(self) -> list[str]:
        return self._filas


class _Conexion:
    def __init__(self, comportamiento: Callable[[], list[str]]) -> None:
        self._comportamiento = comportamiento

    async def __aenter__(self) -> "_Conexion":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def execute(self, consulta: Any) -> _Resultado:
        return _Resultado(self._comportamiento())


class _MotorFalso:
    def __init__(self, comportamiento: Callable[[], list[str]]) -> None:
        self._comportamiento = comportamiento

    def connect(self) -> _Conexion:
        return _Conexion(self._comportamiento)


def _sonda(comportamiento: Callable[[], list[str]]) -> SondaMigraciones:
    return SondaMigraciones(_MotorFalso(comportamiento), HEAD)  # type: ignore[arg-type]


def _lanza(exc: BaseException) -> Callable[[], list[str]]:
    def comportamiento() -> list[str]:
        raise exc

    return comportamiento


def test_sonda_migraciones_nombre() -> None:
    assert _sonda(lambda: [HEAD]).nombre == "migraciones"


async def test_sonda_migraciones_en_head_ok() -> None:
    assert await _sonda(lambda: [HEAD]).comprobar() is ResultadoSonda.OK


@pytest.mark.parametrize(
    "filas", [[], ["0003_config_agentes_taxonomia"], [HEAD, HEAD], ["desconocida"]]
)
async def test_sonda_migraciones_desfasada_falla(filas: list[str]) -> None:
    assert await _sonda(lambda: filas).comprobar() is ResultadoSonda.FALLA


async def test_sonda_migraciones_tabla_ausente_falla() -> None:
    error = ProgrammingError("SELECT", {}, Exception("relation alembic_version does not exist"))
    assert await _sonda(_lanza(error)).comprobar() is ResultadoSonda.FALLA


async def test_sonda_migraciones_excepcion_falla_y_registra_solo_el_tipo(
    capturar_logs: Callable[[], list[dict[str, Any]]],
) -> None:
    from app.core.logging import configurar_logging

    configurar_logging("INFO")
    resultado = await _sonda(_lanza(ConnectionError("usuario:clave@bd"))).comprobar()
    logs = capturar_logs()
    assert (resultado, [(log["evento"], log["tipo_error"]) for log in logs]) == (
        ResultadoSonda.FALLA,
        [("salud.migraciones_falla", "ConnectionError")],
    )
    assert "clave@bd" not in str(logs)
