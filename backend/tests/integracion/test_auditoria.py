"""Auditoría append-only con hash encadenado y versiones de prompt inmutables (CA10, CA13)."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Final, LiteralString

import psycopg
import pytest
from psycopg import errors
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auditoria import ActorTipo, EntradaAuditoria
from app.infrastructure.db.repositorios.auditoria import RepositorioAuditoriaSql
from tests.integracion.conftest import BasePrueba, RolesPrueba
from tests.integracion.soporte_bd import bootstrap_en_proceso

INSERCIONES_CONCURRENTES: Final = 50
INSERTAR: Final = (
    "INSERT INTO auditoria (id, actor_tipo, accion, detalle) "
    "VALUES (gen_random_uuid(), 'sistema', 'prueba.insertada', %s)"
)
MODIFICACIONES: Final = (
    "UPDATE auditoria SET detalle = '{}'::jsonb",
    "DELETE FROM auditoria",
    "TRUNCATE auditoria",
)


@pytest.fixture
async def base_migrada(base_limpia: BasePrueba) -> BasePrueba:
    """Base con bootstrap completo en modo de rol único (superusuario propietario)."""
    await bootstrap_en_proceso(base_limpia.url())
    return base_limpia


@pytest.fixture
async def motor_psycopg(base_migrada: BasePrueba) -> AsyncIterator[AsyncEngine]:
    motor = create_async_engine(base_migrada.url("postgresql+psycopg"), poolclass=NullPool)
    try:
        yield motor
    finally:
        await motor.dispose()


def _url_libpq(base: BasePrueba, usuario: str | None = None, contrasena: str | None = None) -> str:
    return base.url("postgresql", usuario, contrasena)


def _insertar(url: str, detalle: dict[str, object]) -> None:
    with psycopg.connect(url, autocommit=True) as conexion:
        conexion.execute(INSERTAR, (json.dumps(detalle),))


async def _verificar(motor: AsyncEngine) -> tuple[bool, int | None, int]:
    async with motor.connect() as conexion:
        resultado = await RepositorioAuditoriaSql(conexion).verificar_cadena()
    return resultado.ok, resultado.primera_secuencia_rota, resultado.filas


# ------------------------------------------------------------------ modo rol único (propietario)


@pytest.mark.parametrize("sentencia", MODIFICACIONES)
async def test_auditoria_triggers_bloquean_al_propietario(
    base_migrada: BasePrueba, sentencia: LiteralString
) -> None:
    with base_migrada.conectar() as conexion, pytest.raises(errors.InsufficientPrivilege):
        conexion.execute(sentencia)


async def test_auditoria_ocurrido_en_del_cliente_se_ignora(base_migrada: BasePrueba) -> None:
    antiguo = datetime(2000, 1, 1, tzinfo=UTC)
    with base_migrada.conectar() as conexion:
        fila = conexion.execute(
            "INSERT INTO auditoria (id, actor_tipo, accion, ocurrido_en) "
            "VALUES (gen_random_uuid(), 'sistema', 'prueba.antedatada', %s) "
            "RETURNING ocurrido_en, hash IS NOT NULL",
            (antiguo,),
        ).fetchone()
    assert fila is not None
    assert (abs(datetime.now(UTC) - fila[0]) < timedelta(minutes=5), fila[1]) == (True, True)


async def test_auditoria_repositorio_registra_y_encadena(motor_psycopg: AsyncEngine) -> None:
    async with motor_psycopg.begin() as conexion:
        repositorio = RepositorioAuditoriaSql(conexion)
        await repositorio.registrar(
            EntradaAuditoria(ActorTipo.USUARIO, "prueba.registrada", "usuarios", "x", {"a": 1})
        )
    assert await _verificar(motor_psycopg) == (True, None, 4)


async def test_auditoria_cadena_valida_tras_inserciones_concurrentes(
    base_migrada: BasePrueba, motor_psycopg: AsyncEngine
) -> None:
    filas_previas = (await _verificar(motor_psycopg))[2]
    url = _url_libpq(base_migrada)
    await asyncio.gather(
        *(
            asyncio.to_thread(_insertar, url, {"n": numero})
            for numero in range(INSERCIONES_CONCURRENTES)
        )
    )
    with base_migrada.conectar() as conexion:
        enlazadas = conexion.execute(
            "SELECT count(*) FROM (SELECT hash_previo, lag(hash) OVER (ORDER BY secuencia) AS p "
            "FROM auditoria) c WHERE hash_previo IS NOT DISTINCT FROM p"
        ).fetchone()
    assert await _verificar(motor_psycopg) == (
        True,
        None,
        filas_previas + INSERCIONES_CONCURRENTES,
    )
    assert enlazadas == (filas_previas + INSERCIONES_CONCURRENTES,)


async def test_auditoria_detecta_la_primera_fila_manipulada(
    base_migrada: BasePrueba, motor_psycopg: AsyncEngine
) -> None:
    url = _url_libpq(base_migrada)
    for numero in range(5):
        _insertar(url, {"n": numero})
    with base_migrada.conectar() as conexion:
        objetivo = conexion.execute(
            "SELECT secuencia FROM auditoria ORDER BY secuencia OFFSET 4 LIMIT 1"
        ).fetchone()
        assert objetivo is not None
        conexion.execute("ALTER TABLE auditoria DISABLE TRIGGER USER")
        conexion.execute(
            "UPDATE auditoria SET detalle = '{\"n\": 999}'::jsonb WHERE secuencia = %s",
            (objetivo[0],),
        )
        conexion.execute("ALTER TABLE auditoria ENABLE TRIGGER USER")
    ok, rota, _ = await _verificar(motor_psycopg)
    assert (ok, rota) == (False, objetivo[0])


async def test_auditoria_detecta_hash_recalculado_por_el_enlace_siguiente(
    base_migrada: BasePrueba, motor_psycopg: AsyncEngine
) -> None:
    url = _url_libpq(base_migrada)
    for numero in range(3):
        _insertar(url, {"n": numero})
    with base_migrada.conectar() as conexion:
        filas = conexion.execute(
            "SELECT secuencia FROM auditoria ORDER BY secuencia DESC LIMIT 2"
        ).fetchall()
        ultima, penultima = filas[0][0], filas[1][0]
        conexion.execute("ALTER TABLE auditoria DISABLE TRIGGER USER")
        conexion.execute(
            "UPDATE auditoria SET detalle = '{\"n\": 7}'::jsonb, "
            "hash = auditoria_calcular_hash(hash_previo, secuencia, ocurrido_en, actor_id, "
            "actor_tipo, accion, entidad, entidad_id, '{\"n\": 7}'::jsonb, ip) "
            "WHERE secuencia = %s",
            (penultima,),
        )
        conexion.execute("ALTER TABLE auditoria ENABLE TRIGGER USER")
    ok, rota, _ = await _verificar(motor_psycopg)
    assert (ok, rota) == (False, ultima)


# ------------------------------------------------------------------ roles separados


@pytest.fixture
async def base_con_roles(base_limpia: BasePrueba, roles_separados: RolesPrueba) -> RolesPrueba:
    await bootstrap_en_proceso(
        roles_separados.url_app,
        database_url_migrador=roles_separados.url_migrador,
        db_roles_separados=True,
    )
    return roles_separados


def _url_app(base: BasePrueba, roles: RolesPrueba) -> str:
    return _url_libpq(base, "agente_app", roles.contrasena_app)


async def test_auditoria_rol_app_puede_insertar_y_leer(
    base_limpia: BasePrueba, base_con_roles: RolesPrueba
) -> None:
    url = _url_app(base_limpia, base_con_roles)
    _insertar(url, {"desde": "app"})
    with psycopg.connect(url, autocommit=True) as conexion:
        fila = conexion.execute(
            "SELECT count(*) FROM auditoria WHERE accion = 'prueba.insertada'"
        ).fetchone()
    assert fila == (1,)


@pytest.mark.parametrize("sentencia", MODIFICACIONES)
async def test_auditoria_rol_app_sin_privilegios_de_modificacion(
    base_limpia: BasePrueba, base_con_roles: RolesPrueba, sentencia: LiteralString
) -> None:
    url = _url_app(base_limpia, base_con_roles)
    with (
        psycopg.connect(url, autocommit=True) as conexion,
        pytest.raises(errors.InsufficientPrivilege) as error,
    ):
        conexion.execute(sentencia)
    assert "permission denied" in str(error.value)


# ------------------------------------------------------------------ versiones de prompt, CA13


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE versiones_prompt SET prompt_sistema = 'otro'",
        "UPDATE versiones_prompt SET preguntas_jev = '{}'::jsonb",
        "UPDATE versiones_prompt SET esquema_salida = '{}'::jsonb",
        "UPDATE versiones_prompt SET numero = numero + 10",
        "UPDATE versiones_prompt SET publicado_en = NULL",
        "UPDATE versiones_prompt SET publicado_en = now() + interval '1 day'",
        "DELETE FROM versiones_prompt",
        "DELETE FROM agentes WHERE clave = 'redactor'",
    ],
)
async def test_versiones_prompt_publicadas_inmutables(
    base_migrada: BasePrueba, sentencia: LiteralString
) -> None:
    with base_migrada.conectar() as conexion, pytest.raises(errors.IntegrityConstraintViolation):
        conexion.execute(sentencia)


async def test_versiones_prompt_notas_editables(base_migrada: BasePrueba) -> None:
    with base_migrada.conectar() as conexion:
        cursor = conexion.execute("UPDATE versiones_prompt SET notas = 'revisada'")
    assert cursor.rowcount == 5


async def test_versiones_prompt_borrador_no_publicado_se_puede_editar_y_borrar(
    base_migrada: BasePrueba,
) -> None:
    with base_migrada.conectar() as conexion:
        conexion.execute(
            "INSERT INTO versiones_prompt (id, agente_id, numero, prompt_sistema) "
            "SELECT gen_random_uuid(), id, 2, 'borrador' FROM agentes WHERE clave = 'redactor'"
        )
        editadas = conexion.execute(
            "UPDATE versiones_prompt SET prompt_sistema = 'borrador 2' WHERE numero = 2"
        ).rowcount
        borradas = conexion.execute("DELETE FROM versiones_prompt WHERE numero = 2").rowcount
    assert (editadas, borradas) == (1, 1)


async def test_versiones_prompt_version_activa_de_otro_agente_viola_la_fk(
    base_migrada: BasePrueba,
) -> None:
    with base_migrada.conectar() as conexion, pytest.raises(errors.ForeignKeyViolation):
        conexion.execute(
            "UPDATE agentes SET version_prompt_activa_id = ("
            "  SELECT v.id FROM versiones_prompt v JOIN agentes a ON a.id = v.agente_id"
            "  WHERE a.clave = 'guardian') "
            "WHERE clave = 'redactor'"
        )
