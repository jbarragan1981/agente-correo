"""Contenido sembrado por el bootstrap (CA11)."""

from decimal import Decimal

import pytest

from app.domain.catalogo_inicial import CLAUSULA_DATOS_NO_CONFIABLES, catalogo_inicial
from app.infrastructure.db.bootstrap.migraciones import revision_head
from tests.integracion.conftest import BasePrueba
from tests.integracion.soporte_bd import AvisoCapturado, bootstrap_en_proceso


@pytest.fixture
async def sembrada(base_limpia: BasePrueba) -> BasePrueba:
    await bootstrap_en_proceso(base_limpia.url())
    return base_limpia


def _filas(base: BasePrueba, consulta: str, *parametros: object) -> list[tuple]:  # type: ignore[type-arg]
    with base.conectar() as conexion:
        return conexion.execute(consulta, parametros or None).fetchall()  # type: ignore[arg-type]


async def test_semillas_roles(sembrada: BasePrueba) -> None:
    assert _filas(sembrada, "SELECT nombre FROM roles ORDER BY nombre") == [
        ("admin",),
        ("auditor",),
        ("operador",),
    ]


async def test_semillas_proveedores_deshabilitados(sembrada: BasePrueba) -> None:
    assert _filas(
        sembrada, "SELECT nombre, habilitado, config FROM proveedores_ia ORDER BY nombre"
    ) == [
        (nombre, False, {"timeout_s": 30, "reintentos": 2})
        for nombre in ("anthropic", "gemini", "jev", "openai")
    ]


async def test_semillas_taxonomia_base_activa_con_7_categorias(sembrada: BasePrueba) -> None:
    taxonomias = _filas(sembrada, "SELECT nombre, activa FROM taxonomias")
    categorias = _filas(
        sembrada, "SELECT clave, umbral_confianza, prioridad FROM categorias ORDER BY prioridad"
    )
    assert taxonomias == [("Base Viamatica", True)]
    assert categorias == [
        (clave, Decimal("0.70"), prioridad)
        for clave, prioridad in (
            ("facturacion", 10),
            ("soporte", 20),
            ("comercial", 30),
            ("spam", 40),
            ("phishing", 50),
            ("interno", 60),
            ("otro", 70),
        )
    ]


async def test_semillas_agentes(sembrada: BasePrueba) -> None:
    filas = _filas(
        sembrada,
        "SELECT a.clave, a.tipo, p.nombre, a.modelo, a.modelo_respaldo, a.habilitado, "
        "a.herramientas FROM agentes a LEFT JOIN proveedores_ia p ON p.id = a.proveedor_id "
        "ORDER BY a.clave",
    )
    assert filas == [
        ("clasificador", "decision", "jev", "jev-latest", "anthropic:claude-haiku-4-5", True, []),
        ("enrutador", "reglas", None, None, "anthropic:claude-haiku-4-5", True, []),
        ("guardian", "decision", "jev", "jev-latest", "anthropic:claude-haiku-4-5", True, []),
        (
            "redactor",
            "generativo",
            "anthropic",
            "claude-opus-5-5",
            "anthropic:claude-sonnet-5-5",
            False,
            ["buscar_hilo", "consultar_base_conocimiento", "obtener_datos_cliente"],
        ),
        (
            "webchat",
            "generativo",
            "anthropic",
            "claude-sonnet-5-5",
            "anthropic:claude-opus-5-5",
            False,
            ["consultar_base_conocimiento"],
        ),
    ]


async def test_semillas_parametros_de_agentes(sembrada: BasePrueba) -> None:
    assert dict(_filas(sembrada, "SELECT clave, parametros FROM agentes")) == {
        "guardian": {},
        "clasificador": {"diferencia_minima": 0.15},
        "enrutador": {"desempate_con_llm": False},
        "redactor": {"effort": "medium", "max_tokens": 2048},
        "webchat": {"effort": "low", "max_tokens": 1024},
    }


async def test_semillas_version_v1_publicada_y_activa(sembrada: BasePrueba) -> None:
    filas = _filas(
        sembrada,
        "SELECT a.clave, v.numero, v.publicado_en IS NOT NULL, a.version_prompt_activa_id = v.id, "
        "position(%s in v.prompt_sistema) > 0 "
        "FROM agentes a JOIN versiones_prompt v ON v.agente_id = a.id ORDER BY a.clave",
        CLAUSULA_DATOS_NO_CONFIABLES,
    )
    assert filas == [
        (clave, 1, True, True, True)
        for clave in ("clasificador", "enrutador", "guardian", "redactor", "webchat")
    ]


async def test_semillas_preguntas_del_clasificador_son_las_categorias(
    sembrada: BasePrueba,
) -> None:
    (fila,) = _filas(
        sembrada,
        "SELECT v.preguntas_jev FROM versiones_prompt v JOIN agentes a ON a.id = v.agente_id "
        "WHERE a.clave = 'clasificador'",
    )
    claves = sorted(_filas(sembrada, "SELECT clave FROM categorias"))
    assert sorted(fila[0]["categoria"]["criteria"]) == [clave for (clave,) in claves]


async def test_semillas_preguntas_solo_en_agentes_de_decision(sembrada: BasePrueba) -> None:
    filas = _filas(
        sembrada,
        "SELECT a.clave FROM versiones_prompt v JOIN agentes a ON a.id = v.agente_id "
        "WHERE v.preguntas_jev IS NOT NULL ORDER BY a.clave",
    )
    assert filas == [("clasificador",), ("guardian",)]


async def test_semillas_configuracion(sembrada: BasePrueba) -> None:
    assert dict(_filas(sembrada, "SELECT clave, valor FROM configuracion")) == {
        "retencion_dias_mensajes": 180,
        "umbral_riesgo_cuarentena": "alto",
        "envio_automatico_habilitado": False,
    }


async def test_semillas_auditoria_de_la_primera_ejecucion(sembrada: BasePrueba) -> None:
    filas = _filas(sembrada, "SELECT accion, detalle FROM auditoria ORDER BY secuencia")
    assert [accion for accion, _ in filas] == [
        "usuario.admin_inicial_creado",
        "bd.migrada",
        "bd.semillas_aplicadas",
    ]
    assert filas[1][1] == {"desde": None, "hasta": revision_head()}
    assert filas[2][1]["insertadas"]["categorias"] == len(catalogo_inicial().taxonomia.categorias)


async def test_semillas_no_pisan_cambios_del_admin(sembrada: BasePrueba) -> None:
    with sembrada.conectar() as conexion:
        conexion.execute("UPDATE agentes SET habilitado = true WHERE clave = 'redactor'")
        conexion.execute(
            "UPDATE configuracion SET valor = '90' WHERE clave = 'retencion_dias_mensajes'"
        )
        conexion.execute("DELETE FROM categorias WHERE clave = 'interno'")
    await bootstrap_en_proceso(sembrada.url(), AvisoCapturado())
    assert (
        _filas(sembrada, "SELECT habilitado FROM agentes WHERE clave = 'redactor'"),
        _filas(sembrada, "SELECT valor FROM configuracion WHERE clave = 'retencion_dias_mensajes'"),
        _filas(sembrada, "SELECT count(*) FROM categorias"),
    ) == ([(True,)], [(90,)], [(7,)])
