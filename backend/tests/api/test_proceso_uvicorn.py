"""Arranque real con `uvicorn --factory` en un proceso aparte (QA E0.1, sin `.env`).

La app se copia a un directorio temporal para que `RAIZ_REPO/.env` no exista y el
proceso solo vea las variables de entorno que fija cada prueba.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import httpx
import pytest

RAIZ_BACKEND: Final = Path(__file__).resolve().parents[2]
SECRETO_VISIBLE: Final = "secreto-corto-que-no-debe-aparecer"
TIEMPO_MAXIMO_S: Final = 30

pytestmark = pytest.mark.lento


@pytest.fixture
def backend_aislado(tmp_path: Path) -> Path:
    """Copia `app/` y `alembic/` a `tmp/backend` como en la imagen (sin `.env` en el árbol)."""
    destino = tmp_path / "backend"
    for directorio in ("app", "alembic"):
        shutil.copytree(
            RAIZ_BACKEND / directorio,
            destino / directorio,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    return destino


def _entorno(**variables: str) -> dict[str, str]:
    """Entorno mínimo: solo PATH y las variables indicadas."""
    return {"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1", **variables}


def _lanzar(directorio: Path, puerto: int, **variables: str) -> subprocess.Popen[str]:
    """Lanza uvicorn; usar como context manager para cerrar las tuberías."""
    return subprocess.Popen(  # noqa: S603 - argumentos fijos, sin entrada externa
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            "app.main:crear_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(puerto),
            "--no-server-header",
            "--no-access-log",
        ],
        cwd=directorio,
        env=_entorno(**variables),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


@pytest.fixture
def proceso_desarrollo(backend_aislado: Path) -> Iterator[tuple[subprocess.Popen[str], int]]:
    """Servidor en desarrollo con puerto 0; devuelve el proceso y el puerto real."""
    with _lanzar(backend_aislado, 0, ENV="development", LOG_LEVEL="INFO") as proceso:
        assert proceso.stdout is not None
        puerto = 0
        for linea in proceso.stdout:  # bloquea hasta que uvicorn anuncia el puerto
            if "Uvicorn running on" in linea:
                puerto = int(json.loads(linea)["evento"].split("127.0.0.1:")[1].split()[0])
                break
        yield proceso, puerto
        if proceso.poll() is None:
            proceso.send_signal(signal.SIGINT)
        try:
            proceso.wait(timeout=TIEMPO_MAXIMO_S)
        except subprocess.TimeoutExpired:  # pragma: no cover - solo si el apagado se cuelga
            proceso.kill()


def test_uvicorn_factory_en_desarrollo_responde_salud_y_cabeceras(
    proceso_desarrollo: tuple[subprocess.Popen[str], int],
) -> None:
    _, puerto = proceso_desarrollo
    respuesta = httpx.get(f"http://127.0.0.1:{puerto}/api/v1/salud", timeout=TIEMPO_MAXIMO_S)
    assert (
        respuesta.status_code,
        respuesta.json(),
        respuesta.headers["x-content-type-options"],
        "server" in respuesta.headers,
    ) == (200, {"estado": "vivo"}, "nosniff", False)


def test_uvicorn_factory_en_desarrollo_readiness_sin_bd_responde_503(
    proceso_desarrollo: tuple[subprocess.Popen[str], int],
) -> None:
    _, puerto = proceso_desarrollo
    respuesta = httpx.get(f"http://127.0.0.1:{puerto}/api/v1/salud/listo", timeout=TIEMPO_MAXIMO_S)
    assert (respuesta.status_code, respuesta.headers["content-type"]) == (
        503,
        "application/problem+json",
    )


def test_uvicorn_factory_en_desarrollo_apaga_limpio_con_sigint(
    proceso_desarrollo: tuple[subprocess.Popen[str], int],
) -> None:
    proceso, _ = proceso_desarrollo
    proceso.send_signal(signal.SIGINT)
    assert proceso.wait(timeout=TIEMPO_MAXIMO_S) == 0


def test_uvicorn_factory_en_produccion_sin_claves_termina_con_1_sin_volcar_valores(
    backend_aislado: Path,
) -> None:
    with _lanzar(backend_aislado, 0, ENV="production", JWT_SECRET=SECRETO_VISIBLE[:12]) as proceso:
        salida, _ = proceso.communicate(timeout=TIEMPO_MAXIMO_S)
    lineas = [json.loads(linea) for linea in salida.splitlines() if linea.strip()]
    campos = {error["campo"] for linea in lineas for error in linea.get("errores", [])}
    assert (proceso.returncode, SECRETO_VISIBLE[:12] in salida, "Traceback" in salida) == (
        1,
        False,
        False,
    )
    assert {"DATABASE_URL", "APP_MASTER_KEY", "JWT_SECRET", "CORS_ORIGENES"} <= campos


def test_uvicorn_factory_en_produccion_con_debug_verdadero_termina_con_1(
    backend_aislado: Path,
) -> None:
    with _lanzar(backend_aislado, 0, ENV="production", DEBUG="true") as proceso:
        salida, _ = proceso.communicate(timeout=TIEMPO_MAXIMO_S)
    assert (proceso.returncode, '"DEBUG"' in salida) == (1, True)
