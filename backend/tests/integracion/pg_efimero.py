"""Servidor PostgreSQL efímero para las pruebas de integración (ADR-0011).

Orden de resolución: `PRUEBAS_PG_DSN` → Docker (testcontainers) → binarios locales con un
clúster temporal. Si no hay ninguno, la sesión falla (nunca `skip`).
"""

import contextlib
import glob
import os
import secrets
import shutil
import socket
import subprocess  # nosec B404 - solo binarios de PostgreSQL con listas de argumentos
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final
from urllib.parse import quote, urlsplit

import psycopg

VARIABLE_DSN: Final = "PRUEBAS_PG_DSN"
IMAGEN_DOCKER: Final = "postgres:17-alpine"
USUARIO_SISTEMA: Final = "postgres"
SUPERUSUARIO: Final = "postgres"
TIMEOUT_ARRANQUE_S: Final = 60
MENSAJE_SIN_SERVIDOR: Final = (
    "No hay PostgreSQL para las pruebas de integración. Opciones: (1) define PRUEBAS_PG_DSN "
    "hacia un servidor desechable, (2) arranca el daemon de Docker, o (3) instala los "
    "binarios de PostgreSQL (initdb, pg_ctl)."
)


@dataclass(frozen=True)
class ServidorPg:
    """Datos de conexión de un servidor desechable con superusuario."""

    host: str
    puerto: int
    usuario: str
    contrasena: str = field(repr=False)
    version_mayor: int = 0

    def url(
        self,
        base: str,
        driver: str = "postgresql",
        usuario: str | None = None,
        contrasena: str | None = None,
    ) -> str:
        """URL con credenciales codificadas para el driver indicado."""
        usuario_url = quote(usuario or self.usuario, safe="")
        clave_url = quote(contrasena if contrasena is not None else self.contrasena, safe="")
        return f"{driver}://{usuario_url}:{clave_url}@{self.host}:{self.puerto}/{base}"

    def conectar(self, base: str = "postgres") -> psycopg.Connection:
        """Conexión psycopg en autocommit como superusuario."""
        return psycopg.connect(self.url(base), autocommit=True)


def _version_mayor(servidor: ServidorPg) -> ServidorPg:
    """Consulta la versión mayor del servidor."""
    with servidor.conectar() as conexion:
        fila = conexion.execute("SHOW server_version_num").fetchone()
    version = int(str(fila[0])) // 10000 if fila else 0
    return ServidorPg(
        servidor.host, servidor.puerto, servidor.usuario, servidor.contrasena, version
    )


def _desde_dsn(dsn: str) -> ServidorPg:
    """Servidor descrito por `PRUEBAS_PG_DSN`."""
    partes = urlsplit(dsn)
    return ServidorPg(
        host=partes.hostname or "127.0.0.1",
        puerto=partes.port or 5432,
        usuario=partes.username or SUPERUSUARIO,
        contrasena=partes.password or "",
    )


def _docker_disponible() -> bool:
    """Indica si hay un daemon Docker accesible."""
    docker = shutil.which("docker")
    if docker is None:
        return False
    resultado = subprocess.run(  # noqa: S603 - binario resuelto y sin shell
        [docker, "info"], capture_output=True, check=False, timeout=20
    )
    return resultado.returncode == 0


@contextlib.contextmanager
def _con_docker() -> Iterator[ServidorPg]:
    """PostgreSQL 17 con testcontainers."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(IMAGEN_DOCKER) as contenedor:
        yield ServidorPg(
            host=contenedor.get_container_host_ip(),
            puerto=int(contenedor.get_exposed_port(5432)),
            usuario=contenedor.username,
            contrasena=contenedor.password,
        )


def _directorio_binarios() -> Path | None:
    """Directorio de `initdb` de la versión mayor más alta instalada."""
    pg_config = shutil.which("pg_config")
    if pg_config is not None:
        salida = subprocess.run(  # noqa: S603 - binario resuelto y sin shell
            [pg_config, "--bindir"], capture_output=True, text=True, check=False
        )
        candidato = Path(salida.stdout.strip())
        if (candidato / "initdb").exists():
            return candidato
    instalados = glob.glob("/usr/lib/postgresql/*/bin/initdb")  # noqa: PTH207 - comodín en ruta
    if not instalados:
        return None
    return Path(max(instalados, key=lambda ruta: int(Path(ruta).parts[-3]))).parent


def _puerto_libre() -> int:
    """Puerto TCP libre en 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _como_postgres(argumentos: list[str]) -> list[str]:
    """Antepone `runuser -u postgres --` si el proceso corre como root."""
    if os.geteuid() != 0:
        return argumentos
    runuser = shutil.which("runuser") or "/usr/sbin/runuser"
    return [runuser, "-u", USUARIO_SISTEMA, "--", *argumentos]


def _ejecutar(argumentos: list[str]) -> None:
    """Ejecuta un binario de PostgreSQL y falla con su salida si termina mal."""
    resultado = subprocess.run(  # noqa: S603 - argumentos fijos, sin shell
        _como_postgres(argumentos),
        capture_output=True,
        text=True,
        check=False,
        timeout=TIMEOUT_ARRANQUE_S,
    )
    if resultado.returncode != 0:
        mensaje = f"{Path(argumentos[0]).name} terminó con {resultado.returncode}: "
        raise RuntimeError(mensaje + resultado.stderr[-2000:])


def _entregar_a_postgres(ruta: Path) -> None:
    """Hace a `postgres` propietario del directorio temporal (solo si somos root)."""
    if os.geteuid() == 0:
        shutil.chown(ruta, user=USUARIO_SISTEMA, group=USUARIO_SISTEMA)


@contextlib.contextmanager
def _con_binarios(bindir: Path) -> Iterator[ServidorPg]:
    """Clúster temporal con initdb + pg_ctl en 127.0.0.1 y scram-sha-256."""
    raiz = Path(tempfile.mkdtemp(prefix="agente_pg_"))
    datos, archivo_clave = raiz / "datos", raiz / "clave"
    contrasena = secrets.token_urlsafe(24)
    puerto = _puerto_libre()
    try:
        archivo_clave.write_text(contrasena, encoding="utf-8")
        archivo_clave.chmod(0o600)
        _entregar_a_postgres(raiz)
        _entregar_a_postgres(archivo_clave)
        _ejecutar(
            [
                str(bindir / "initdb"),
                "-D",
                str(datos),
                "-U",
                SUPERUSUARIO,
                "--auth=scram-sha-256",
                f"--pwfile={archivo_clave}",
                "--encoding=UTF8",
                "--locale=C",
            ]
        )
        archivo_clave.unlink()
        opciones = f"-p {puerto} -k {raiz} -c listen_addresses=127.0.0.1 -c fsync=off"
        _ejecutar(
            [
                str(bindir / "pg_ctl"),
                "start",
                "-w",
                "-D",
                str(datos),
                "-l",
                str(raiz / "servidor.log"),
                "-o",
                opciones,
            ]
        )
        try:
            yield ServidorPg("127.0.0.1", puerto, SUPERUSUARIO, contrasena)
        finally:
            _ejecutar([str(bindir / "pg_ctl"), "stop", "-m", "fast", "-w", "-D", str(datos)])
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


@contextlib.contextmanager
def servidor_efimero() -> Iterator[ServidorPg]:
    """Resuelve y entrega un servidor desechable; lo apaga y borra al salir si lo creó."""
    dsn = os.environ.get(VARIABLE_DSN)
    if dsn:
        yield _version_mayor(_desde_dsn(dsn))
        return
    if _docker_disponible():
        with _con_docker() as servidor:
            yield _version_mayor(servidor)
        return
    bindir = _directorio_binarios()
    if bindir is None:
        raise RuntimeError(MENSAJE_SIN_SERVIDOR)
    with _con_binarios(bindir) as servidor:
        yield _version_mayor(servidor)
