"""Fixtures de integración con PostgreSQL efímero (ADR-0011).

- `postgres_efimero` (sesión): servidor desechable con superusuario.
- `base_limpia` (función): base `prueba_<hex>` nueva, eliminada al terminar.
- `roles_separados` (función): aplica `infra/sql/roles.sql` en la base y asigna contraseñas
  aleatorias de la sesión con `psycopg.sql.Literal`.
- `backend_aislado` (sesión): copia de `app/` y `alembic/` sin `.env` para ejecutar
  `python -m app.bootstrap` en subprocesos que solo ven el entorno que fija cada prueba.
"""

import secrets
import shutil
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pytest
from psycopg import sql

from tests.integracion.pg_efimero import ServidorPg, servidor_efimero

RAIZ_BACKEND: Final = Path(__file__).resolve().parents[2]
ROLES_SQL: Final = RAIZ_BACKEND.parent / "infra" / "sql" / "roles.sql"
DRIVER_APP: Final = "postgresql+asyncpg"


@dataclass(frozen=True)
class BasePrueba:
    """Base desechable dentro del servidor efímero."""

    servidor: ServidorPg
    nombre: str

    def url(
        self,
        driver: str = DRIVER_APP,
        usuario: str | None = None,
        contrasena: str | None = None,
    ) -> str:
        """URL hacia esta base (por defecto como superusuario y con asyncpg)."""
        return self.servidor.url(self.nombre, driver, usuario, contrasena)

    def conectar(self):
        """Conexión psycopg en autocommit como superusuario."""
        return self.servidor.conectar(self.nombre)


@dataclass(frozen=True)
class RolesPrueba:
    """URLs asyncpg de `agente_migrador` y `agente_app` para una base con roles separados."""

    url_migrador: str = field(repr=False)
    url_app: str = field(repr=False)
    contrasena_migrador: str = field(repr=False)
    contrasena_app: str = field(repr=False)


@pytest.fixture(scope="session")
def postgres_efimero() -> Iterator[ServidorPg]:
    """Servidor de la sesión: PRUEBAS_PG_DSN, Docker o binarios locales; nunca `skip`."""
    with servidor_efimero() as servidor:
        yield servidor


def crear_base(servidor: ServidorPg, nombre: str) -> None:
    """Crea una base vacía."""
    with servidor.conectar() as conexion:
        conexion.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nombre)))


def eliminar_base(servidor: ServidorPg, nombre: str) -> None:
    """Elimina la base cerrando sus conexiones."""
    with servidor.conectar() as conexion:
        conexion.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(nombre))
        )


def nombre_prueba() -> str:
    """Nombre único con el prefijo que la fixture puede borrar."""
    return f"prueba_{uuid.uuid4().hex[:16]}"


@pytest.fixture
def base_limpia(postgres_efimero: ServidorPg) -> Iterator[BasePrueba]:
    """Base nueva por prueba."""
    nombre = nombre_prueba()
    crear_base(postgres_efimero, nombre)
    try:
        yield BasePrueba(postgres_efimero, nombre)
    finally:
        eliminar_base(postgres_efimero, nombre)


@pytest.fixture
def nombre_base_libre(postgres_efimero: ServidorPg) -> Iterator[str]:
    """Nombre de una base que no existe; se elimina al terminar si alguien la creó."""
    nombre = nombre_prueba()
    try:
        yield nombre
    finally:
        eliminar_base(postgres_efimero, nombre)


@pytest.fixture(scope="session")
def contrasenas_roles() -> tuple[str, str]:
    """Contraseñas aleatorias de la sesión para agente_migrador y agente_app."""
    return secrets.token_urlsafe(18), secrets.token_urlsafe(18)


def aplicar_roles(base: BasePrueba, contrasena_migrador: str, contrasena_app: str) -> None:
    """Ejecuta roles.sql en la base y asigna contraseñas (roles globales del clúster)."""
    with base.conectar() as conexion:
        conexion.execute(ROLES_SQL.read_text(encoding="utf-8"))  # type: ignore[arg-type]
        for rol, contrasena in (
            ("agente_migrador", contrasena_migrador),
            ("agente_app", contrasena_app),
        ):
            conexion.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(rol), sql.Literal(contrasena)
                )
            )


@pytest.fixture
def roles_separados(base_limpia: BasePrueba, contrasenas_roles: tuple[str, str]) -> RolesPrueba:
    """Roles de ADR-0008 aplicados sobre `base_limpia`."""
    migrador, app = contrasenas_roles
    aplicar_roles(base_limpia, migrador, app)
    return RolesPrueba(
        url_migrador=base_limpia.url(usuario="agente_migrador", contrasena=migrador),
        url_app=base_limpia.url(usuario="agente_app", contrasena=app),
        contrasena_migrador=migrador,
        contrasena_app=app,
    )


@pytest.fixture(scope="session")
def backend_aislado(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Copia de `app/` y `alembic/` (como en la imagen) sin `.env` en el árbol."""
    destino = tmp_path_factory.mktemp("bootstrap") / "backend"
    for directorio in ("app", "alembic"):
        shutil.copytree(
            RAIZ_BACKEND / directorio,
            destino / directorio,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    return destino
