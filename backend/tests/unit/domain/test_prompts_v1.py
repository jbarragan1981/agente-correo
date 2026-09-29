"""Prompts v1: cinco archivos, cláusula de datos no confiables, sin frases prohibidas."""

import re
from pathlib import Path
from typing import Final

import pytest

from app.domain.catalogo_inicial import (
    CLAUSULA_DATOS_NO_CONFIABLES,
    FRASES_PROHIBIDAS_EN_PROMPTS,
    catalogo_inicial,
)

DIRECTORIO_PROMPTS: Final = Path(__file__).resolve().parents[3] / "app" / "agents" / "prompts"
ARCHIVOS: Final = sorted(DIRECTORIO_PROMPTS.glob("*.md"))
PATRONES_SECRETO: Final = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bts_[A-Za-z0-9_-]{8,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ"),
    re.compile(r"(?i)(password|contraseña)\s*[:=]\s*\S+"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}"),
)
TAMANO_MAXIMO_BYTES: Final = 32 * 1024


def test_prompts_hay_uno_por_agente_del_catalogo() -> None:
    assert [r.name for r in ARCHIVOS] == sorted(
        a.archivo_prompt for a in catalogo_inicial().agentes
    )


@pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda r: r.name)
def test_prompts_contienen_la_clausula_literal(ruta: Path) -> None:
    assert CLAUSULA_DATOS_NO_CONFIABLES in ruta.read_text(encoding="utf-8")


@pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda r: r.name)
def test_prompts_sin_frases_prohibidas(ruta: Path) -> None:
    texto = ruta.read_text(encoding="utf-8").lower()
    assert [frase for frase in FRASES_PROHIBIDAS_EN_PROMPTS if frase in texto] == []


@pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda r: r.name)
def test_prompts_sin_patrones_de_secreto_ni_emails(ruta: Path) -> None:
    texto = ruta.read_text(encoding="utf-8")
    assert [p.pattern for p in PATRONES_SECRETO if p.search(texto)] == []


@pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda r: r.name)
def test_prompts_tamano_acotado(ruta: Path) -> None:
    assert 0 < ruta.stat().st_size <= TAMANO_MAXIMO_BYTES


def test_prompts_redactor_sigue_el_resumen_de_docs_05() -> None:
    texto = (DIRECTORIO_PROMPTS / "redactor_v1.md").read_text(encoding="utf-8")
    assert all(
        fragmento in texto
        for fragmento in ("180 palabras", "base de conocimiento", "idioma del remitente")
    )
