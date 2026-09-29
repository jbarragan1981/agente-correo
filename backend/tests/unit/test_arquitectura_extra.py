"""Verificaciones de QA: lockfile (CA2 E0.1, CA1 E0.2), SDKs de IA dinámicos y `os.environ`."""

import ast
import re
import tomllib
from pathlib import Path
from typing import Final

import pytest

RAIZ_BACKEND: Final = Path(__file__).resolve().parents[2]
RAIZ_APP: Final = RAIZ_BACKEND / "app"
# E0.2 admite alembic, procrastinate, langgraph-checkpoint* y langchain-core/-protocol (ADR-0010);
# siguen prohibidos los SDKs de IA, las integraciones de LangChain, LangGraph completo y el correo.
PAQUETES_PROHIBIDOS: Final = re.compile(
    r'^name = "(anthropic|openai|google-genai|google-generativeai|typesafe.*'
    r"|langchain|langchain-(?!core\"|protocol\").*|langgraph|langgraph-(?!checkpoint).*"
    r"|aioimaplib|aiosmtplib)\"$",
    flags=re.IGNORECASE | re.MULTILINE,
)
NOMBRES_SDK: Final = ("anthropic", "openai", "google", "typesafe", "langchain")
DEPENDENCIAS_LANGCHAIN_PERMITIDAS: Final = frozenset({"langchain-core"})
FUNCIONES_IMPORT_DINAMICO: Final = {"import_module", "__import__"}


def _archivos_fuera_de_providers() -> list[Path]:
    return sorted(
        ruta
        for ruta in RAIZ_APP.rglob("*.py")
        if "providers" not in ruta.relative_to(RAIZ_APP).parts
    )


def test_lockfile_no_contiene_dependencias_de_ia_ni_de_fases_posteriores() -> None:
    lock = (RAIZ_BACKEND / "uv.lock").read_text(encoding="utf-8")
    assert PAQUETES_PROHIBIDOS.findall(lock) == []


def test_pyproject_no_declara_dependencias_de_ia() -> None:
    datos = tomllib.loads((RAIZ_BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    declaradas = [*datos["project"]["dependencies"], *datos["dependency-groups"]["dev"]]
    nombres = {re.split(r"[\[<>=~! ]", dep, maxsplit=1)[0].lower() for dep in declaradas}
    sdks = {n for n in nombres if n.startswith(NOMBRES_SDK)} - DEPENDENCIAS_LANGCHAIN_PERMITIDAS
    assert sdks == set()


@pytest.mark.parametrize(
    "nombre",
    ["anthropic", "openai", "google-genai", "langchain-anthropic", "langchain", "langgraph"],
)
def test_patron_de_lockfile_detecta_paquetes_prohibidos(nombre: str) -> None:
    assert PAQUETES_PROHIBIDOS.findall(f'name = "{nombre}"\n') == [nombre]


@pytest.mark.parametrize(
    "nombre", ["langchain-core", "langchain-protocol", "langgraph-checkpoint-postgres"]
)
def test_patron_de_lockfile_admite_dependencias_de_e0_2(nombre: str) -> None:
    assert PAQUETES_PROHIBIDOS.findall(f'name = "{nombre}"\n') == []


@pytest.mark.parametrize(
    "ruta", _archivos_fuera_de_providers(), ids=lambda r: str(r.relative_to(RAIZ_APP))
)
def test_ningun_modulo_fuera_de_providers_importa_sdks_de_ia_de_forma_dinamica(ruta: Path) -> None:
    llamadas = [
        nodo
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8")))
        if isinstance(nodo, ast.Call)
        and (
            (isinstance(nodo.func, ast.Attribute) and nodo.func.attr in FUNCIONES_IMPORT_DINAMICO)
            or (isinstance(nodo.func, ast.Name) and nodo.func.id in FUNCIONES_IMPORT_DINAMICO)
        )
    ]
    assert llamadas == []


@pytest.mark.parametrize(
    "ruta", _archivos_fuera_de_providers(), ids=lambda r: str(r.relative_to(RAIZ_APP))
)
def test_ningun_modulo_fuera_de_providers_nombra_un_sdk_de_ia_en_un_import(ruta: Path) -> None:
    modulos = [
        alias.name if isinstance(nodo, ast.Import) else (nodo.module or "")
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8")))
        if isinstance(nodo, ast.Import | ast.ImportFrom)
        for alias in (nodo.names if isinstance(nodo, ast.Import) else [ast.alias(name="")])
    ]
    assert [m for m in modulos if m.split(".")[0] in NOMBRES_SDK] == []


@pytest.mark.parametrize(
    "ruta",
    [r for r in sorted(RAIZ_APP.rglob("*.py")) if r.name != "config.py"],
    ids=lambda r: str(r.relative_to(RAIZ_APP)),
)
def test_solo_config_lee_variables_de_entorno(ruta: Path) -> None:
    fuente = ruta.read_text(encoding="utf-8")
    assert re.findall(r"os\.environ|os\.getenv|getenv\(", fuente) == []
