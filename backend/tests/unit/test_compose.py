"""Compose con postura de producción (CA17, observaciones M1 y B6 de E0.1).

Ejecuta `docker compose config` (no necesita daemon). Las aserciones comparan valores
derivados, nunca imprimen el entorno de los servicios.
"""

import json
import os
import shutil
import subprocess  # nosec B404 - binario de docker con lista de argumentos
from pathlib import Path
from typing import Any, Final

import pytest

RAIZ_REPO: Final = Path(__file__).resolve().parents[3]
BASE: Final = RAIZ_REPO / "infra" / "docker-compose.yml"
DEV: Final = RAIZ_REPO / "infra" / "docker-compose.dev.yml"
CONTRASENAS: Final = {
    "POSTGRES_PASSWORD": "postgres",
    "AGENTE_MIGRADOR_PASSWORD": "migrador_local",
    "AGENTE_APP_PASSWORD": "app_local",
}


def _docker() -> str:
    """Ruta del CLI de docker; falla (no omite) si no existe."""
    docker = shutil.which("docker")
    if docker is None:
        pytest.fail("Se necesita el CLI de docker para validar Compose (no hace falta el daemon)")
    return docker


def _config(*archivos: Path, **variables: str) -> subprocess.CompletedProcess[str]:
    """Ejecuta `docker compose config --format json` con un entorno controlado."""
    entorno = {
        clave: valor
        for clave, valor in os.environ.items()
        if clave not in CONTRASENAS and not clave.startswith(("POSTGRES_", "COMPOSE_"))
    }
    argumentos = [_docker(), "compose"]
    for archivo in archivos:
        argumentos += ["-f", str(archivo)]
    return subprocess.run(  # noqa: S603 - argumentos fijos, sin shell
        [*argumentos, "config", "--format", "json"],
        env=entorno | variables,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _servicios(*archivos: Path) -> dict[str, Any]:
    resultado = _config(*archivos, **CONTRASENAS)
    assert resultado.returncode == 0, "docker compose config falló con las contraseñas definidas"
    servicios: dict[str, Any] = json.loads(resultado.stdout)["services"]
    return servicios


@pytest.mark.parametrize("variable", sorted(CONTRASENAS))
def test_compose_falla_si_falta_una_contrasena(variable: str) -> None:
    resultado = _config(BASE, **{k: v for k, v in CONTRASENAS.items() if k != variable})
    assert (resultado.returncode != 0, variable in resultado.stderr) == (True, True)


def test_compose_base_db_sin_puertos() -> None:
    assert "ports" not in _servicios(BASE)["db"]


def test_compose_dev_publica_la_bd_solo_en_localhost() -> None:
    puertos = _servicios(BASE, DEV)["db"]["ports"]
    assert [(p["host_ip"], p["published"], p["target"]) for p in puertos] == [
        ("127.0.0.1", "5432", 5432)
    ]


def test_compose_api_depende_del_migrador_completado() -> None:
    assert _servicios(BASE)["api"]["depends_on"]["migrador"]["condition"] == (
        "service_completed_successfully"
    )


def test_compose_migrador_one_shot_con_bootstrap() -> None:
    migrador = _servicios(BASE)["migrador"]
    assert (
        migrador["command"],
        migrador["restart"],
        migrador["depends_on"]["db"]["condition"],
    ) == (
        ["python", "-m", "app.bootstrap"],
        "no",
        "service_healthy",
    )


def test_compose_api_no_recibe_url_del_migrador() -> None:
    entorno = _servicios(BASE)["api"]["environment"]
    assert entorno.get("DATABASE_URL_MIGRADOR", "") == ""


def test_compose_api_se_conecta_como_agente_app() -> None:
    entorno = _servicios(BASE)["api"]["environment"]
    assert (
        entorno["DATABASE_URL"].split("://")[1].split(":")[0],
        entorno["DB_ROLES_SEPARADOS"],
    ) == (
        "agente_app",
        "true",
    )


def test_compose_migrador_se_conecta_como_agente_migrador() -> None:
    entorno = _servicios(BASE)["migrador"]["environment"]
    usuario = entorno["DATABASE_URL_MIGRADOR"].split("://")[1].split(":")[0]
    assert (usuario, entorno["DB_ROLES_SEPARADOS"]) == ("agente_migrador", "true")


def test_compose_ningun_servicio_base_activa_auto_create() -> None:
    servicios = _servicios(BASE)
    activan = [
        nombre
        for nombre, servicio in servicios.items()
        if str(servicio.get("environment", {}).get("DB_AUTO_CREATE", "")).lower() == "true"
    ]
    assert activan == []


def test_compose_dev_activa_auto_create_solo_en_el_migrador() -> None:
    servicios = _servicios(BASE, DEV)
    activan = [
        nombre
        for nombre, servicio in servicios.items()
        if str(servicio.get("environment", {}).get("DB_AUTO_CREATE", "")).lower() == "true"
    ]
    assert activan == ["migrador"]


@pytest.mark.parametrize("servicio", ["migrador", "api"])
def test_compose_servicios_backend_endurecidos(servicio: str) -> None:
    definicion = _servicios(BASE)[servicio]
    assert (
        definicion["read_only"],
        definicion["cap_drop"],
        definicion["security_opt"],
    ) == (True, ["ALL"], ["no-new-privileges:true"])


def test_compose_db_monta_el_script_de_roles_en_solo_lectura() -> None:
    volumenes = {
        v["target"]: v.get("read_only", False)
        for v in _servicios(BASE)["db"]["volumes"]
        if v["type"] == "bind"
    }
    assert volumenes == {
        "/docker-entrypoint-initdb.d/00-roles.sh": True,
        "/sql/roles.sql": True,
    }
