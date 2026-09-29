"""Piezas puras del orquestador: URLs por modo, envoltura de pasos y auditoría condicional."""

from collections.abc import Callable
from typing import Any

import pytest

from app.core.logging import configurar_logging
from app.domain.auditoria import EntradaAuditoria
from app.infrastructure.db.bootstrap.errores import (
    FalloEnPaso,
    FaltaUrlMigrador,
    LockTimeout,
)
from app.infrastructure.db.bootstrap.orquestador import (
    paso,
    registrar_auditoria_bootstrap,
    urls_bootstrap,
)
from tests.soporte import settings_prueba

URL_APP = "postgresql+asyncpg://agente_app:postgres@bd:5432/agente"
URL_MIGRADOR = "postgresql+asyncpg://agente_migrador:postgres@bd:5432/agente"
LeerLogs = Callable[[], list[dict[str, Any]]]
MENSAJE_CON_CREDENCIAL = "permiso denegado para usuario:clave@bd"


class AuditoriaFalsa:
    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoria] = []

    async def registrar(self, entrada: EntradaAuditoria) -> None:
        self.entradas.append(entrada)


def test_orquestador_roles_separados_sin_url_migrador_falla() -> None:
    with pytest.raises(FaltaUrlMigrador):
        urls_bootstrap(settings_prueba(database_url=URL_APP, db_roles_separados=True))


def test_orquestador_roles_separados_usa_dos_urls_psycopg() -> None:
    migrador, app = urls_bootstrap(
        settings_prueba(
            database_url=URL_APP, database_url_migrador=URL_MIGRADOR, db_roles_separados=True
        )
    )
    assert (migrador.drivername, migrador.username, app.drivername, app.username) == (
        "postgresql+psycopg",
        "agente_migrador",
        "postgresql+psycopg",
        "agente_app",
    )


def test_orquestador_rol_unico_usa_la_url_de_la_app_para_todo() -> None:
    migrador, app = urls_bootstrap(settings_prueba(database_url=URL_APP))
    assert migrador == app


async def test_orquestador_paso_envuelve_excepciones_inesperadas(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")

    class ErrorConSqlstate(Exception):
        sqlstate = "42501"

    with pytest.raises(FalloEnPaso) as error:
        async with paso("migraciones"):
            raise ErrorConSqlstate(MENSAJE_CON_CREDENCIAL)
    logs = capturar_logs()
    assert (error.value.paso, error.value.tipo_error, error.value.sqlstate) == (
        "migraciones",
        "ErrorConSqlstate",
        "42501",
    )
    assert [(log["paso"], log["resultado"]) for log in logs] == [("migraciones", "error")]


async def test_orquestador_paso_propaga_errores_de_bootstrap_sin_envolver() -> None:
    with pytest.raises(LockTimeout):
        async with paso("bloqueo"):
            raise LockTimeout


async def test_orquestador_paso_ok_registra_duracion(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    async with paso("espera"):
        pass
    (log,) = capturar_logs()
    assert (log["evento"], log["paso"], log["resultado"], isinstance(log["duracion_ms"], int)) == (
        "bootstrap.paso",
        "espera",
        "ok",
        True,
    )


async def test_orquestador_auditoria_sin_cambios_no_registra_nada() -> None:
    auditoria = AuditoriaFalsa()
    await registrar_auditoria_bootstrap(auditoria, "r4", "r4", {"roles": 0})  # type: ignore[arg-type]
    assert auditoria.entradas == []


async def test_orquestador_auditoria_migracion_y_semillas() -> None:
    auditoria = AuditoriaFalsa()
    await registrar_auditoria_bootstrap(
        auditoria,  # type: ignore[arg-type]
        None,
        "r4",
        {"roles": 3, "agentes": 0, "configuracion": 3},
    )
    assert [(e.accion, dict(e.detalle)) for e in auditoria.entradas] == [
        ("bd.migrada", {"desde": None, "hasta": "r4"}),
        ("bd.semillas_aplicadas", {"insertadas": {"roles": 3, "configuracion": 3}}),
    ]
