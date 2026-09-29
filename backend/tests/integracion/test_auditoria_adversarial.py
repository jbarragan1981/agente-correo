"""Q3 adversarial de la auditoría: evasiones por SQL y detección de manipulaciones (ADR-0009)."""

import json
from collections.abc import AsyncIterator
from typing import LiteralString

import psycopg
import pytest
from psycopg import errors
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.db.repositorios.auditoria import RepositorioAuditoriaSql
from tests.integracion.conftest import BasePrueba
from tests.integracion.soporte_bd import bootstrap_en_proceso

INSERTAR: LiteralString = (
    "INSERT INTO auditoria (id, actor_tipo, accion, detalle) "
    "VALUES (gen_random_uuid(), 'sistema', 'prueba.insertada', %s)"
)
EVASIONES: tuple[LiteralString, ...] = (
    "INSERT INTO auditoria (id, actor_tipo, accion, hash) SELECT id, actor_tipo, accion, hash "
    "FROM auditoria LIMIT 1 ON CONFLICT (id) DO UPDATE SET accion = 'prueba.cambiada'",
    "UPDATE auditoria SET hash = hash",
    "DELETE FROM auditoria WHERE true",
    "TRUNCATE auditoria, usuarios CASCADE",
    "TRUNCATE auditoria RESTART IDENTITY",
    "WITH borradas AS (DELETE FROM auditoria RETURNING 1) SELECT count(*) FROM borradas",
)


@pytest.fixture
async def base_migrada(base_limpia: BasePrueba) -> BasePrueba:
    """Base con bootstrap completo y cinco entradas adicionales."""
    await bootstrap_en_proceso(base_limpia.url())
    with base_limpia.conectar() as conexion:
        for numero in range(5):
            conexion.execute(INSERTAR, (json.dumps({"n": numero}),))
    return base_limpia


@pytest.fixture
async def motor(base_migrada: BasePrueba) -> AsyncIterator[AsyncEngine]:
    motor = create_async_engine(base_migrada.url("postgresql+psycopg"), poolclass=NullPool)
    try:
        yield motor
    finally:
        await motor.dispose()


async def _verificar(motor: AsyncEngine) -> tuple[bool, int | None, int]:
    async with motor.connect() as conexion:
        resultado = await RepositorioAuditoriaSql(conexion).verificar_cadena()
    return resultado.ok, resultado.primera_secuencia_rota, resultado.filas


@pytest.mark.parametrize("sentencia", EVASIONES)
async def test_auditoria_evasiones_por_sql_fallan_incluso_para_el_superusuario(
    base_migrada: BasePrueba, motor: AsyncEngine, sentencia: LiteralString
) -> None:
    antes = await _verificar(motor)
    with base_migrada.conectar() as conexion, pytest.raises(errors.InsufficientPrivilege):
        conexion.execute(sentencia)
    assert await _verificar(motor) == antes


async def test_auditoria_transaccion_revertida_no_deja_huecos_en_la_cadena(
    base_migrada: BasePrueba, motor: AsyncEngine
) -> None:
    antes = await _verificar(motor)
    with psycopg.connect(base_migrada.url("postgresql")) as conexion:
        conexion.execute(INSERTAR, ("{}",))
        conexion.rollback()
    with base_migrada.conectar() as conexion:
        conexion.execute(INSERTAR, ("{}",))
    ok, rota, filas = await _verificar(motor)
    assert (ok, rota, filas) == (True, None, antes[2] + 1)


async def test_auditoria_detecta_fila_intermedia_borrada(
    base_migrada: BasePrueba, motor: AsyncEngine
) -> None:
    with base_migrada.conectar() as conexion:
        secuencias = [
            f[0] for f in conexion.execute("SELECT secuencia FROM auditoria ORDER BY secuencia")
        ]
        borrada, siguiente = secuencias[-3], secuencias[-2]
        conexion.execute("ALTER TABLE auditoria DISABLE TRIGGER USER")
        conexion.execute("DELETE FROM auditoria WHERE secuencia = %s", (borrada,))
        conexion.execute("ALTER TABLE auditoria ENABLE TRIGGER USER")
    assert (await _verificar(motor))[:2] == (False, siguiente)


async def test_auditoria_detecta_primera_fila_borrada(
    base_migrada: BasePrueba, motor: AsyncEngine
) -> None:
    with base_migrada.conectar() as conexion:
        primera, segunda = (
            f[0]
            for f in conexion.execute("SELECT secuencia FROM auditoria ORDER BY secuencia LIMIT 2")
        )
        conexion.execute("ALTER TABLE auditoria DISABLE TRIGGER USER")
        conexion.execute("DELETE FROM auditoria WHERE secuencia = %s", (primera,))
        conexion.execute("ALTER TABLE auditoria ENABLE TRIGGER USER")
    assert (await _verificar(motor))[:2] == (False, segunda)


async def test_auditoria_detecta_hash_previo_alterado(
    base_migrada: BasePrueba, motor: AsyncEngine
) -> None:
    with base_migrada.conectar() as conexion:
        (objetivo,) = conexion.execute(
            "SELECT secuencia FROM auditoria ORDER BY secuencia DESC OFFSET 1 LIMIT 1"
        ).fetchone() or (None,)
        conexion.execute("ALTER TABLE auditoria DISABLE TRIGGER USER")
        conexion.execute(
            "UPDATE auditoria SET hash_previo = '\\xdeadbeef' WHERE secuencia = %s", (objetivo,)
        )
        conexion.execute("ALTER TABLE auditoria ENABLE TRIGGER USER")
    assert (await _verificar(motor))[:2] == (False, objetivo)


async def test_auditoria_detecta_fila_insertada_con_triggers_desactivados(
    base_migrada: BasePrueba, motor: AsyncEngine
) -> None:
    with base_migrada.conectar() as conexion:
        conexion.execute("ALTER TABLE auditoria DISABLE TRIGGER USER")
        conexion.execute(
            "INSERT INTO auditoria (id, actor_tipo, accion, hash) "
            "VALUES (gen_random_uuid(), 'sistema', 'prueba.forjada', '\\x00')"
        )
        conexion.execute("ALTER TABLE auditoria ENABLE TRIGGER USER")
    ok, rota, _ = await _verificar(motor)
    assert (ok, rota is not None) == (False, True)


@pytest.mark.parametrize(
    ("columna", "valor"),
    [
        ("accion", "'prueba.no_es_valida'"),
        ("actor_tipo", "'usuario'"),
        ("entidad", "'otra'"),
        ("ip", "'10.0.0.1'::inet"),
        ("actor_id", "gen_random_uuid()"),
        ("ocurrido_en", "now() + interval '1 day'"),
    ],
)
async def test_auditoria_cualquier_columna_alterada_rompe_la_cadena(
    base_migrada: BasePrueba, motor: AsyncEngine, columna: str, valor: str
) -> None:
    consulta = f"UPDATE auditoria SET {columna} = {valor} WHERE accion = 'prueba.insertada'"  # noqa: S608 - constantes de la propia prueba
    with base_migrada.conectar() as conexion:
        conexion.execute("ALTER TABLE auditoria DISABLE TRIGGER USER")
        conexion.execute(consulta)  # type: ignore[arg-type]
        conexion.execute("ALTER TABLE auditoria ENABLE TRIGGER USER")
    ok, rota, _ = await _verificar(motor)
    assert (ok, rota is not None) == (False, True)
