"""Reglas de dependencias hexagonales verificadas sobre el AST de `app/` (CA14)."""

import ast
import sys
from pathlib import Path
from typing import Final

import pytest

RAIZ_APP: Final = Path(__file__).resolve().parents[2] / "app"
PROHIBIDOS_EN_APLICACION: Final = (
    "fastapi",
    "starlette",
    "sqlalchemy",
    "pydantic_settings",
    "structlog",
    "app.api",
    "app.infrastructure",
)
SDKS_IA: Final = (
    "anthropic",
    "openai",
    "google.genai",
    "google.generativeai",
    "typesafe_sdk",
    "langchain_anthropic",
    "langchain_openai",
    "langchain_google_genai",
)


def _nombre_modulo(ruta: Path) -> str:
    """Convierte una ruta de `app/` en nombre de módulo con puntos."""
    partes = ruta.relative_to(RAIZ_APP.parent).with_suffix("").parts
    return ".".join(partes[:-1] if partes[-1] == "__init__" else partes)


def _resolver_relativo(modulo: str, es_paquete: bool, nivel: int, destino: str | None) -> str:
    """Resuelve un `from ..x import y` a nombre absoluto."""
    base = modulo.split(".")
    base = base if es_paquete else base[:-1]
    base = base[: len(base) - (nivel - 1)]
    return ".".join([*base, destino] if destino else base)


def _importaciones(ruta: Path) -> set[str]:
    """Módulos importados por un archivo, resueltos a nombre absoluto."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulo = _nombre_modulo(ruta)
    encontrados: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            encontrados.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                es_paquete = ruta.name == "__init__.py"
                encontrados.add(_resolver_relativo(modulo, es_paquete, nodo.level, nodo.module))
            elif nodo.module:
                encontrados.add(nodo.module)
    return encontrados


def _archivos(capa: str) -> list[Path]:
    """Archivos Python de una capa de `app/`."""
    return sorted((RAIZ_APP / capa).rglob("*.py")) if capa else sorted(RAIZ_APP.rglob("*.py"))


def _coincide(importado: str, prefijo: str) -> bool:
    """Indica si `importado` es `prefijo` o un submódulo suyo."""
    return importado == prefijo or importado.startswith(f"{prefijo}.")


def _es_stdlib_o_dominio(importado: str) -> bool:
    """Admite solo la biblioteca estándar y el propio dominio."""
    return importado.split(".")[0] in sys.stdlib_module_names or _coincide(importado, "app.domain")


def test_arquitectura_hay_archivos_que_analizar() -> None:
    assert (len(_archivos("domain")) > 0, len(_archivos("application")) > 0) == (True, True)


@pytest.mark.parametrize("ruta", _archivos("domain"), ids=lambda ruta: ruta.name)
def test_arquitectura_dominio_solo_importa_stdlib(ruta: Path) -> None:
    ajenos = {i for i in _importaciones(ruta) if not _es_stdlib_o_dominio(i)}
    assert ajenos == set()


@pytest.mark.parametrize("ruta", _archivos("application"), ids=lambda ruta: ruta.name)
def test_arquitectura_aplicacion_no_importa_frameworks_ni_adaptadores(ruta: Path) -> None:
    prohibidos = {
        i for i in _importaciones(ruta) for p in PROHIBIDOS_EN_APLICACION if _coincide(i, p)
    }
    assert prohibidos == set()


@pytest.mark.parametrize(
    "ruta",
    [r for r in _archivos("") if "providers" not in r.relative_to(RAIZ_APP).parts],
    ids=lambda ruta: str(ruta.relative_to(RAIZ_APP)),
)
def test_arquitectura_sdks_de_ia_solo_en_providers(ruta: Path) -> None:
    sdks = {i for i in _importaciones(ruta) for sdk in SDKS_IA if _coincide(i, sdk)}
    assert sdks == set()


def test_arquitectura_resolver_relativo_sube_niveles() -> None:
    assert _resolver_relativo("app.application.use_cases.x", False, 2, "ports") == (
        "app.application.ports"
    )
