"""Auxiliares de integración: bootstrap en proceso o en subproceso y consultas de verificación."""

import asyncio
import json
import os
import subprocess  # nosec B404 - el intérprete del venv con lista de argumentos
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import psycopg
from psycopg import sql

from app.core.config import Settings
from app.infrastructure.db.bootstrap.orquestador import ResultadoBootstrap, ejecutar_bootstrap
from tests.soporte import settings_prueba

TIMEOUT_PROCESO_S: Final = 120
TABLAS_PROPIAS: Final = (
    "usuarios",
    "roles",
    "usuarios_roles",
    "auditoria",
    "configuracion",
    "proveedores_ia",
    "agentes",
    "versiones_prompt",
    "taxonomias",
    "categorias",
)


class AvisoCapturado:
    """Doble de `AvisoOperadorPort` que guarda lo mostrado."""

    def __init__(self) -> None:
        self.mostrados: list[tuple[str, str]] = []

    def mostrar_contrasena_inicial(self, email_enmascarado: str, contrasena: str) -> None:
        """Guarda el aviso."""
        self.mostrados.append((email_enmascarado, contrasena))


def settings_bootstrap(url: str, **cambios: Any) -> Settings:
    """Settings de prueba (sin `.env`) apuntando a la URL indicada."""
    return settings_prueba(database_url=url, **cambios)


async def bootstrap_en_proceso(
    url: str, aviso: AvisoCapturado | None = None, **cambios: Any
) -> ResultadoBootstrap:
    """Ejecuta el orquestador en este proceso."""
    return await ejecutar_bootstrap(settings_bootstrap(url, **cambios), aviso or AvisoCapturado())


@dataclass(frozen=True)
class ResultadoProceso:
    """Salida de `python -m app.bootstrap`."""

    codigo: int
    stdout: str
    stderr: str
    duracion_s: float

    def logs(self) -> list[dict[str, Any]]:
        """Líneas JSON de stdout."""
        return [json.loads(linea) for linea in self.stdout.splitlines() if linea.strip()]

    def eventos(self) -> list[str]:
        """Nombres de evento en orden."""
        return [log["evento"] for log in self.logs()]


def entorno_proceso(variables: Mapping[str, str]) -> dict[str, str]:
    """Entorno mínimo: PATH, sin bytecode y las variables indicadas."""
    return {
        "PATH": os.environ["PATH"],
        "PYTHONDONTWRITEBYTECODE": "1",
        "ENV": "test",
        **variables,
    }


def argumentos_bootstrap() -> list[str]:
    """Comando del bootstrap con el intérprete del venv."""
    return [sys.executable, "-m", "app.bootstrap"]


def bootstrap_en_subproceso(backend: Path, variables: Mapping[str, str]) -> ResultadoProceso:
    """Ejecuta el comando real en un proceso aparte (sin `.env`)."""
    inicio = time.perf_counter()
    resultado = subprocess.run(  # noqa: S603 - argumentos fijos, sin shell
        argumentos_bootstrap(),
        cwd=backend,
        env=entorno_proceso(variables),
        capture_output=True,
        text=True,
        check=False,
        timeout=TIMEOUT_PROCESO_S,
    )
    return ResultadoProceso(
        resultado.returncode, resultado.stdout, resultado.stderr, time.perf_counter() - inicio
    )


async def bootstrap_en_subproceso_async(
    backend: Path, variables: Mapping[str, str]
) -> ResultadoProceso:
    """Variante asíncrona para lanzar varios bootstraps a la vez."""
    inicio = time.perf_counter()
    proceso = await asyncio.create_subprocess_exec(
        *argumentos_bootstrap(),
        cwd=backend,
        env=entorno_proceso(variables),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    salida, errores = await asyncio.wait_for(proceso.communicate(), TIMEOUT_PROCESO_S)
    return ResultadoProceso(
        proceso.returncode if proceso.returncode is not None else -1,
        salida.decode(),
        errores.decode(),
        time.perf_counter() - inicio,
    )


def consultar(conexion: psycopg.Connection, consulta: str, *parametros: object) -> list[tuple]:  # type: ignore[type-arg]
    """Ejecuta una consulta parametrizada y devuelve todas las filas."""
    return conexion.execute(consulta, parametros or None).fetchall()  # type: ignore[arg-type]


def tablas_de(conexion: psycopg.Connection, esquema: str) -> set[str]:  # type: ignore[type-arg]
    """Tablas de un esquema."""
    filas = consultar(conexion, "SELECT tablename FROM pg_tables WHERE schemaname = %s", esquema)
    return {str(fila[0]) for fila in filas}


def conteos(conexion: psycopg.Connection) -> dict[str, int]:  # type: ignore[type-arg]
    """Filas por tabla propia."""
    resultado: dict[str, int] = {}
    for tabla in TABLAS_PROPIAS:
        fila = conexion.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla))
        ).fetchone()
        resultado[tabla] = int(fila[0]) if fila else 0
    return resultado
