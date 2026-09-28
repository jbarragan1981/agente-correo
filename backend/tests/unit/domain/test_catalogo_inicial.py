"""Catálogo inicial: claves únicas, denegar por defecto, modelos válidos y preguntas (CA11)."""

from decimal import Decimal
from typing import Final

import pytest

from app.domain.agentes.preguntas import TipoPregunta, preguntas_como_json
from app.domain.catalogo_inicial import AgenteInicial, catalogo_inicial

MODELOS_VALIDOS: Final = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5", "jev-latest"}
PROVEEDORES_VALIDOS: Final = {"anthropic", "openai", "gemini", "jev"}
CATALOGO: Final = catalogo_inicial()


def _agente(clave: str) -> AgenteInicial:
    return next(a for a in CATALOGO.agentes if a.clave == clave)


def test_catalogo_roles() -> None:
    assert [r.nombre for r in CATALOGO.roles] == ["admin", "operador", "auditor"]


def test_catalogo_proveedores_todos_soportados() -> None:
    assert {p.nombre for p in CATALOGO.proveedores} == PROVEEDORES_VALIDOS


def test_catalogo_proveedores_config_por_defecto() -> None:
    assert {tuple(sorted(p.config.items())) for p in CATALOGO.proveedores} == {
        (("reintentos", 2), ("timeout_s", 30))
    }


def test_catalogo_categorias_base() -> None:
    assert [c.clave for c in CATALOGO.taxonomia.categorias] == [
        "facturacion",
        "soporte",
        "comercial",
        "spam",
        "phishing",
        "interno",
        "otro",
    ]


def test_catalogo_categorias_prioridad_umbral_y_color() -> None:
    categorias = CATALOGO.taxonomia.categorias
    assert (
        [c.prioridad for c in categorias],
        {c.umbral_confianza for c in categorias},
        all(c.color.startswith("#") and len(c.color) == 7 for c in categorias),
    ) == ([10, 20, 30, 40, 50, 60, 70], {Decimal("0.70")}, True)


@pytest.mark.parametrize(
    "claves",
    [
        [r.nombre for r in CATALOGO.roles],
        [p.nombre for p in CATALOGO.proveedores],
        [c.clave for c in CATALOGO.taxonomia.categorias],
        [a.clave for a in CATALOGO.agentes],
        [c.clave for c in CATALOGO.configuracion],
    ],
)
def test_catalogo_claves_unicas(claves: list[str]) -> None:
    assert len(claves) == len(set(claves))


def test_catalogo_agentes_por_defecto() -> None:
    assert [a.clave for a in CATALOGO.agentes] == [
        "guardian",
        "clasificador",
        "enrutador",
        "redactor",
        "webchat",
    ]


def test_catalogo_agentes_generativos_deshabilitados() -> None:
    assert {a.clave: a.habilitado for a in CATALOGO.agentes if a.tipo == "generativo"} == {
        "redactor": False,
        "webchat": False,
    }


def test_catalogo_modelos_con_ids_exactos() -> None:
    usados = {a.modelo for a in CATALOGO.agentes if a.modelo} | {
        a.modelo_respaldo.split(":", 1)[1] for a in CATALOGO.agentes if a.modelo_respaldo
    }
    assert usados <= MODELOS_VALIDOS


def test_catalogo_respaldos_con_proveedor_valido() -> None:
    assert {
        a.modelo_respaldo.split(":", 1)[0] for a in CATALOGO.agentes if a.modelo_respaldo
    } <= PROVEEDORES_VALIDOS


def test_catalogo_agentes_no_reglas_tienen_proveedor_y_modelo() -> None:
    assert all(a.proveedor and a.modelo for a in CATALOGO.agentes if a.tipo != "reglas")


def test_catalogo_enrutador_sin_proveedor() -> None:
    enrutador = _agente("enrutador")
    assert (enrutador.tipo, enrutador.proveedor, enrutador.modelo) == ("reglas", None, None)


def test_catalogo_herramientas_solo_en_generativos() -> None:
    assert {a.clave: a.herramientas for a in CATALOGO.agentes if a.herramientas} == {
        "redactor": ("buscar_hilo", "consultar_base_conocimiento", "obtener_datos_cliente"),
        "webchat": ("consultar_base_conocimiento",),
    }


def test_catalogo_preguntas_del_clasificador_son_las_categorias() -> None:
    preguntas = _agente("clasificador").preguntas
    assert preguntas is not None
    criterios = preguntas["categoria"].criterios
    assert isinstance(criterios, dict)
    assert list(criterios) == [c.clave for c in CATALOGO.taxonomia.categorias]


def test_catalogo_preguntas_del_guardian() -> None:
    preguntas = _agente("guardian").preguntas
    assert preguntas is not None
    assert {k: p.tipo for k, p in preguntas.items()} == {
        "jailbreak": TipoPregunta.NOUL,
        "phishing": TipoPregunta.NOUL,
        "riesgo": TipoPregunta.SCORE,
    }


def test_catalogo_preguntas_serializadas_a_json() -> None:
    preguntas = _agente("clasificador").preguntas
    assert preguntas is not None
    json = preguntas_como_json(preguntas)
    assert (
        json["urgencia"],
        json["requiere_respuesta"],
    ) == (
        {
            "type": "score",
            "instructions": "¿Qué tan pronto requiere atención?",
            "criteria": ["Puede esperar", "Esta semana", "Hoy"],
        },
        {"type": "noul", "instructions": "¿El remitente espera una respuesta?"},
    )


def test_catalogo_agentes_sin_preguntas_si_no_son_de_decision() -> None:
    assert {a.clave for a in CATALOGO.agentes if a.preguntas} == {"guardian", "clasificador"}


def test_catalogo_configuracion_por_defecto() -> None:
    assert {c.clave: c.valor for c in CATALOGO.configuracion} == {
        "retencion_dias_mensajes": 180,
        "umbral_riesgo_cuarentena": "alto",
        "envio_automatico_habilitado": False,
    }


def test_catalogo_es_inmutable() -> None:
    with pytest.raises(TypeError):
        _agente("clasificador").parametros["diferencia_minima"] = 0.5  # type: ignore[index]
