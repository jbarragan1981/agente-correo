"""Q3/Q5 adversarial: lo que el rol de aplicación no puede hacer aunque lo intente."""

import json
import os
import shutil
import subprocess  # nosec B404 - sh y psql locales con lista de argumentos
from pathlib import Path
from typing import Final

import psycopg
import pytest
from psycopg import errors

from tests.integracion.conftest import RAIZ_BACKEND, BasePrueba, RolesPrueba
from tests.integracion.soporte_bd import bootstrap_en_proceso

SCRIPT_ROLES: Final = RAIZ_BACKEND.parent / "infra" / "sql" / "00-roles.sh"
ROLES_SQL: Final = RAIZ_BACKEND.parent / "infra" / "sql" / "roles.sql"


@pytest.fixture
async def separada(base_limpia: BasePrueba, roles_separados: RolesPrueba) -> RolesPrueba:
    """Base migrada con roles separados."""
    await bootstrap_en_proceso(
        roles_separados.url_app,
        database_url_migrador=roles_separados.url_migrador,
        db_roles_separados=True,
    )
    return roles_separados


def _app(base: BasePrueba, roles: RolesPrueba) -> psycopg.Connection:  # type: ignore[type-arg]
    return psycopg.connect(
        base.url("postgresql", "agente_app", roles.contrasena_app), autocommit=True
    )


@pytest.mark.parametrize(
    "sentencia",
    [
        "ALTER TABLE auditoria DISABLE TRIGGER ALL",
        "ALTER TABLE auditoria DISABLE TRIGGER auditoria_inmutable_fila",
        "DROP TABLE auditoria",
        "DROP TRIGGER auditoria_inmutable_fila ON auditoria",
        "CREATE OR REPLACE FUNCTION public.auditoria_inmutable() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$",
        "SET session_replication_role = replica",
        "TRUNCATE usuarios",
        "ALTER TABLE usuarios ADD COLUMN intrusa int",
        "DROP TABLE versiones_prompt",
        "SELECT public.agente_conceder_privilegios('public')",
        "CREATE TEMP TABLE t (id int)",
    ],
)
async def test_app_no_puede_ejecutar_ddl_ni_evadir_la_auditoria(
    base_limpia: BasePrueba, separada: RolesPrueba, sentencia: str
) -> None:
    with (
        _app(base_limpia, separada) as conexion,
        pytest.raises((errors.InsufficientPrivilege, errors.WrongObjectType)),
    ):
        conexion.execute(sentencia)  # type: ignore[arg-type]


async def test_app_no_puede_falsificar_hash_secuencia_ni_fecha_de_la_auditoria(
    base_limpia: BasePrueba, separada: RolesPrueba
) -> None:
    with _app(base_limpia, separada) as conexion:
        conexion.execute(
            "INSERT INTO auditoria (id, secuencia, ocurrido_en, actor_tipo, accion, detalle, "
            "hash_previo, hash) OVERRIDING SYSTEM VALUE VALUES (gen_random_uuid(), 999999, "
            "'2000-01-01', 'sistema', 'prueba.falsa', %s, '\\x00', '\\x01')",
            (json.dumps({"a": 1}),),
        )
        fila = conexion.execute(
            "SELECT secuencia, ocurrido_en > '2001-01-01', hash <> '\\x01', "
            "hash_previo IS DISTINCT FROM '\\x00' FROM auditoria WHERE accion = 'prueba.falsa'"
        ).fetchone()
    assert fila is not None
    assert fila[0] != 999999
    assert fila[1:] == (True, True, True)


async def test_app_no_puede_modificar_alembic_version(
    base_limpia: BasePrueba, separada: RolesPrueba
) -> None:
    with _app(base_limpia, separada) as conexion:
        privilegios = conexion.execute(
            "SELECT has_table_privilege('alembic_version', 'UPDATE'), "
            "has_table_privilege('alembic_version', 'DELETE'), "
            "has_table_privilege('alembic_version', 'INSERT'), "
            "has_table_privilege('alembic_version', 'TRUNCATE'), "
            "has_table_privilege('alembic_version', 'SELECT')"
        ).fetchone()
    assert privilegios == (False, False, False, False, True)


@pytest.mark.parametrize("clave", ["con espacio y 'comillas'", 'dólar$HOME"y\\barra;--', "a\nb"])
def test_script_de_roles_asigna_contrasenas_con_caracteres_de_shell_y_sql(
    base_limpia: BasePrueba, tmp_path: Path, clave: str
) -> None:
    psql = shutil.which("psql")
    assert psql is not None
    enlaces = tmp_path / "bin"
    enlaces.mkdir()
    (enlaces / "psql").symlink_to(psql)
    servidor = base_limpia.servidor
    resultado = subprocess.run(  # noqa: S603 - argumentos fijos, sin shell propio
        ["/bin/sh", str(SCRIPT_ROLES)],
        env={
            "PATH": f"{enlaces}:{os.environ['PATH']}",
            "PGHOST": servidor.host,
            "PGPORT": str(servidor.puerto),
            "PGPASSWORD": servidor.contrasena,
            "POSTGRES_USER": servidor.usuario,
            "POSTGRES_DB": base_limpia.nombre,
            "ROLES_SQL": str(ROLES_SQL),
            "AGENTE_MIGRADOR_PASSWORD": clave + "-m",
            "AGENTE_APP_PASSWORD": clave + "-a",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    with psycopg.connect(
        base_limpia.url("postgresql", "agente_app", clave + "-a"), autocommit=True
    ) as conexion:
        conectado = conexion.execute("SELECT current_user").fetchone()
    assert (resultado.returncode, conectado) == (0, ("agente_app",))
    assert clave not in resultado.stdout + resultado.stderr
