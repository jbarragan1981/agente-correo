"""Readiness real con la sonda `migraciones` (CA16)."""

import httpx
import pytest
from fastapi import FastAPI

from app.infrastructure.db.bootstrap.migraciones import revision_head
from app.main import crear_app
from tests.integracion.conftest import BasePrueba, RolesPrueba
from tests.integracion.soporte_bd import bootstrap_en_proceso
from tests.soporte import cliente_para, settings_prueba

TIMEOUT_BD_S = 2.0


@pytest.fixture
async def migrada(base_limpia: BasePrueba) -> BasePrueba:
    await bootstrap_en_proceso(base_limpia.url())
    return base_limpia


async def _listo(base: BasePrueba) -> httpx.Response:
    app: FastAPI = crear_app(
        settings_prueba(database_url=base.url(), salud_bd_timeout_s=TIMEOUT_BD_S)
    )
    async with app.router.lifespan_context(app), cliente_para(app) as cliente:
        return await cliente.get("/api/v1/salud/listo")


async def test_readiness_real_en_head_responde_200(migrada: BasePrueba) -> None:
    respuesta = await _listo(migrada)
    assert (respuesta.status_code, respuesta.json()) == (
        200,
        {"estado": "listo", "comprobaciones": {"base_datos": "ok", "migraciones": "ok"}},
    )


async def test_readiness_real_con_revision_anterior_responde_503_sin_revisiones(
    migrada: BasePrueba,
) -> None:
    with migrada.conectar() as conexion:
        conexion.execute("UPDATE alembic_version SET version_num = '0003_config_agentes_taxonomia'")
    respuesta = await _listo(migrada)
    assert (respuesta.status_code, respuesta.json()["comprobaciones"]) == (
        503,
        {"base_datos": "ok", "migraciones": "falla"},
    )
    assert [r for r in ("0003", revision_head(), "alembic") if r in respuesta.text] == []


async def test_readiness_real_sin_alembic_version_responde_503(migrada: BasePrueba) -> None:
    with migrada.conectar() as conexion:
        conexion.execute("DROP TABLE alembic_version")
    respuesta = await _listo(migrada)
    assert respuesta.json()["comprobaciones"] == {"base_datos": "ok", "migraciones": "falla"}


async def test_readiness_real_con_rol_app_en_head(roles_separados: RolesPrueba) -> None:
    await bootstrap_en_proceso(
        roles_separados.url_app,
        database_url_migrador=roles_separados.url_migrador,
        db_roles_separados=True,
    )
    app = crear_app(settings_prueba(database_url=roles_separados.url_app))
    async with app.router.lifespan_context(app), cliente_para(app) as cliente:
        respuesta = await cliente.get("/api/v1/salud/listo")
    assert respuesta.status_code == 200
