"""Estructura de Alembic: una sola head, downgrades reales y SQL de procrastinate coherente."""

import ast
from importlib.metadata import version
from pathlib import Path
from typing import Final

import pytest
from alembic.script import ScriptDirectory

from app.infrastructure.db.bootstrap.migraciones import (
    DIRECTORIO_ALEMBIC,
    HeadsMultiples,
    configuracion_alembic,
    revision_head,
)

DIRECTORIO_VERSIONES: Final = DIRECTORIO_ALEMBIC / "versions"
DIRECTORIO_SQL_PROCRASTINATE: Final = DIRECTORIO_ALEMBIC / "sql" / "procrastinate"
REVISIONES: Final = sorted(DIRECTORIO_VERSIONES.glob("*.py"))


def _funcion(ruta: Path, nombre: str) -> ast.FunctionDef:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    return next(
        nodo for nodo in arbol.body if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre
    )


def test_alembic_una_sola_head() -> None:
    heads = ScriptDirectory.from_config(configuracion_alembic()).get_heads()
    assert (len(heads), revision_head()) == (1, heads[0])


def test_alembic_head_es_la_ultima_revision() -> None:
    assert revision_head() == "0006_revocar_migraciones_lg"


def test_alembic_varias_heads_lanzan_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ScriptDirectory, "get_heads", lambda self: ["a", "b"])
    with pytest.raises(HeadsMultiples):
        revision_head()


def test_alembic_revisiones_en_cadena() -> None:
    script = ScriptDirectory.from_config(configuracion_alembic())
    cadena = [rev.revision for rev in script.walk_revisions()]
    assert cadena == [
        "0006_revocar_migraciones_lg",
        "0005_revocar_alembic_version",
        "0004_procrastinate_3_10_0",
        "0003_config_agentes_taxonomia",
        "0002_identidad_auditoria",
        "0001_extensiones_esquemas",
    ]


@pytest.mark.parametrize("ruta", REVISIONES, ids=lambda ruta: ruta.stem)
def test_alembic_revision_igual_al_nombre_del_archivo(ruta: Path) -> None:
    script = ScriptDirectory.from_config(configuracion_alembic())
    revisiones = {rev.revision for rev in script.walk_revisions()}
    assert (ruta.stem in revisiones, len(ruta.stem) <= 32) == (True, True)


@pytest.mark.parametrize("ruta", REVISIONES, ids=lambda ruta: ruta.stem)
def test_alembic_cada_revision_tiene_downgrade_real(ruta: Path) -> None:
    cuerpo = _funcion(ruta, "downgrade").body
    llamadas = [n for n in cuerpo if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
    assert len(llamadas) > 0


def test_alembic_version_de_procrastinate_coincide_con_la_ultima_copia() -> None:
    copias = sorted(
        (ruta.name.removesuffix("_schema.sql") for ruta in DIRECTORIO_SQL_PROCRASTINATE.iterdir()),
        key=lambda v: tuple(int(parte) for parte in v.split(".")),
    )
    assert copias[-1] == version("procrastinate")


def test_alembic_sql_de_procrastinate_no_referencia_public() -> None:
    sql = (DIRECTORIO_SQL_PROCRASTINATE / "3.10.0_schema.sql").read_text(encoding="utf-8")
    assert "public." not in sql


def test_alembic_ini_no_contiene_url() -> None:
    contenido = (DIRECTORIO_ALEMBIC.parent / "alembic.ini").read_text(encoding="utf-8")
    assert ("sqlalchemy.url" in contenido, "postgresql" in contenido) == (False, False)
