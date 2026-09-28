"""Q4 adversarial de semillas y readiness: idempotencia, forma de las preguntas y BD caída."""

import socket
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.catalogo_inicial import catalogo_inicial
from app.infrastructure.db.semillas import leer_prompt, sembrar_catalogo
from app.main import crear_app
from tests.integracion.conftest import BasePrueba
from tests.integracion.soporte_bd import bootstrap_en_proceso, conteos
from tests.soporte import cliente_para, settings_prueba

TIPOS_JEV: Final = {"noul", "choice", "score"}
MODELOS_VALIDOS: Final = {
    "jev-latest",
    "claude-opus-5-5",
    "claude-sonnet-5-5",
    "claude-haiku-4-5",
    "anthropic:claude-haiku-4-5",
    "anthropic:claude-sonnet-5-5",
    "anthropic:claude-opus-5-5",
}


@pytest.fixture
async def sembrada(base_limpia: BasePrueba) -> BasePrueba:
    await bootstrap_en_proceso(base_limpia.url())
    return base_limpia


async def test_sembrar_catalogo_dos_veces_seguidas_no_inserta_nada_la_segunda(
    sembrada: BasePrueba,
) -> None:
    with sembrada.conectar() as conexion:
        antes = conteos(conexion)
    motor = create_async_engine(sembrada.url("postgresql+psycopg"), poolclass=NullPool)
    try:
        async with motor.begin() as conexion:
            primera = await sembrar_catalogo(conexion, catalogo_inicial())
        async with motor.begin() as conexion:
            segunda = await sembrar_catalogo(conexion, catalogo_inicial())
    finally:
        await motor.dispose()
    with sembrada.conectar() as conexion:
        despues = conteos(conexion)
    assert (sum(primera.values()), sum(segunda.values()), despues) == (0, 0, antes)


def test_preguntas_jev_almacenadas_tienen_forma_valida(sembrada: BasePrueba) -> None:
    with sembrada.conectar() as conexion:
        filas = conexion.execute(
            "SELECT a.clave, v.preguntas_jev FROM versiones_prompt v "
            "JOIN agentes a ON a.id = v.agente_id WHERE v.preguntas_jev IS NOT NULL"
        ).fetchall()
    assert {clave for clave, _ in filas} == {"guardian", "clasificador"}
    for _, preguntas in filas:
        assert preguntas
        for nombre, pregunta in preguntas.items():
            assert nombre
            assert pregunta["type"] in TIPOS_JEV
            assert pregunta["instructions"].strip()
            criterios = pregunta.get("criteria")
            if pregunta["type"] == "score":
                assert isinstance(criterios, list)
                assert len(criterios) >= 2
                assert all(isinstance(c, str) and c for c in criterios)
            if pregunta["type"] == "choice":
                assert isinstance(criterios, dict)
                assert len(criterios) >= 2
            if pregunta["type"] == "noul" and criterios is not None:
                assert set(criterios) == {"true", "false"}


def test_prompts_almacenados_coinciden_con_los_archivos_y_no_estan_vacios(
    sembrada: BasePrueba,
) -> None:
    with sembrada.conectar() as conexion:
        filas = conexion.execute(
            "SELECT a.clave, v.prompt_sistema FROM versiones_prompt v "
            "JOIN agentes a ON a.id = v.agente_id WHERE v.numero = 1"
        ).fetchall()
    esperados = {a.clave: leer_prompt(a.archivo_prompt) for a in catalogo_inicial().agentes}
    assert dict(filas) == esperados
    assert all(len(texto.strip()) > 100 for texto in esperados.values())


def test_modelos_sembrados_son_los_ids_exactos(sembrada: BasePrueba) -> None:
    with sembrada.conectar() as conexion:
        filas = conexion.execute("SELECT modelo, modelo_respaldo FROM agentes").fetchall()
    usados = {m for fila in filas for m in fila if m is not None}
    assert usados <= MODELOS_VALIDOS


async def test_rerun_no_revierte_la_version_activa_elegida_por_el_admin(
    sembrada: BasePrueba,
) -> None:
    with sembrada.conectar() as conexion:
        conexion.execute(
            "INSERT INTO versiones_prompt (id, agente_id, numero, prompt_sistema, publicado_en) "
            "SELECT gen_random_uuid(), id, 2, 'v2 del admin', now() FROM agentes "
            "WHERE clave = 'guardian'"
        )
        conexion.execute(
            "UPDATE agentes SET version_prompt_activa_id = "
            "(SELECT v.id FROM versiones_prompt v WHERE v.agente_id = agentes.id AND v.numero = 2) "
            "WHERE clave = 'guardian'"
        )
    await bootstrap_en_proceso(sembrada.url())
    with sembrada.conectar() as conexion:
        activa = conexion.execute(
            "SELECT v.numero FROM agentes a JOIN versiones_prompt v "
            "ON v.id = a.version_prompt_activa_id WHERE a.clave = 'guardian'"
        ).fetchone()
        versiones = conexion.execute("SELECT count(*) FROM versiones_prompt").fetchone()
    assert (activa, versiones) == ((2,), (6,))


# ------------------------------------------------------------------ readiness con BD caída


def _puerto_cerrado() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def test_readiness_con_bd_caida_responde_503_sin_detalles() -> None:
    puerto = _puerto_cerrado()
    url = f"postgresql+asyncpg://usuario_qa:clave-qa-secreta@127.0.0.1:{puerto}/bd_qa"
    app = crear_app(settings_prueba(database_url=url, salud_bd_timeout_s=1.0))
    async with app.router.lifespan_context(app), cliente_para(app) as cliente:
        respuesta = await cliente.get("/api/v1/salud/listo")
    prohibidos = ("usuario_qa", "clave-qa", "bd_qa", str(puerto), "127.0.0.1", "asyncpg", "Refused")
    assert (respuesta.status_code, respuesta.json()["comprobaciones"]) == (
        503,
        {"base_datos": "falla", "migraciones": "falla"},
    )
    assert [p for p in prohibidos if p in respuesta.text] == []
