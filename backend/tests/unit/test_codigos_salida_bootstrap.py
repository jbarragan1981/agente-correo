"""`python -m app.bootstrap`: mapeo excepción → código de salida y logs sin valores."""

import json
from collections.abc import Callable
from typing import Any

import pytest

from app import bootstrap
from app.core.config import Settings
from app.core.logging import configurar_logging
from app.infrastructure.db.bootstrap.errores import (
    BdNoDisponible,
    ErrorBootstrap,
    LockTimeout,
    PrivilegiosInseguros,
)

LeerLogs = Callable[[], list[dict[str, Any]]]
MARCADOR = "marcador-secreto-de-prueba"


@pytest.fixture(autouse=True)
def _sin_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)


def _fallar_con(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    async def falso(*args: object) -> None:
        raise error

    monkeypatch.setattr(bootstrap, "ejecutar_bootstrap", falso)


def test_codigos_config_invalida_devuelve_1_sin_valores(
    monkeypatch: pytest.MonkeyPatch, capturar_logs: LeerLogs
) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DB_AUTO_CREATE", "true")
    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", "corta")
    codigo = bootstrap.main()
    logs = capturar_logs()
    assert (codigo, logs[-1]["evento"], "corta" in json.dumps(logs)) == (
        1,
        "config.invalida",
        False,
    )


def test_codigos_exito_devuelve_0(monkeypatch: pytest.MonkeyPatch) -> None:
    async def falso(*args: object) -> None:
        return None

    monkeypatch.setattr(bootstrap, "ejecutar_bootstrap", falso)
    assert bootstrap.main() == 0


@pytest.mark.parametrize(
    ("error", "evento"),
    [
        (LockTimeout(), "bootstrap.lock_timeout"),
        (BdNoDisponible(tipo_error="OSError"), "bootstrap.bd_no_disponible"),
    ],
)
def test_codigos_error_de_bootstrap_devuelve_2_con_evento_especifico(
    monkeypatch: pytest.MonkeyPatch, capturar_logs: LeerLogs, error: ErrorBootstrap, evento: str
) -> None:
    _fallar_con(monkeypatch, error)
    codigo = bootstrap.main()
    eventos = [log["evento"] for log in capturar_logs() if log["nivel"] == "error"]
    assert (codigo, eventos) == (2, [evento, "bootstrap.fallido"])


def test_codigos_privilegios_inseguros_lista_comprobaciones(
    monkeypatch: pytest.MonkeyPatch, capturar_logs: LeerLogs
) -> None:
    _fallar_con(monkeypatch, PrivilegiosInseguros(("app.superusuario", "app.create_en_public")))
    codigo = bootstrap.main()
    (log,) = [log for log in capturar_logs() if log["evento"] == "bootstrap.privilegios_inseguros"]
    assert (codigo, log["comprobaciones"], log["paso"]) == (
        2,
        ["app.superusuario", "app.create_en_public"],
        "privilegios",
    )


def test_codigos_excepcion_inesperada_devuelve_2_sin_mensaje(
    monkeypatch: pytest.MonkeyPatch, capturar_logs: LeerLogs
) -> None:
    _fallar_con(monkeypatch, ConnectionError(f"postgresql://u:{MARCADOR}@bd/x"))
    codigo = bootstrap.main()
    logs = capturar_logs()
    assert (codigo, logs[-1]["evento"], logs[-1]["tipo_error"], MARCADOR in json.dumps(logs)) == (
        2,
        "bootstrap.fallido",
        "ConnectionError",
        False,
    )


def test_codigos_codigo_de_salida_de_error_generico(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    assert bootstrap.codigo_de_salida(RuntimeError(MARCADOR)) == 2
    assert MARCADOR not in json.dumps(capturar_logs())
