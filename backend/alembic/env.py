"""Entorno de Alembic: modo programático (bootstrap) y modo CLI (desarrollo).

En modo programático la conexión llega en `config.attributes["connection"]` y no se lee el
entorno. En modo CLI la URL sale de `Settings` (migrador o, en rol único, la de la app) con el
driver psycopg. Los esquemas de librerías y `alembic_version` quedan fuera de autogenerate.
"""

from typing import Final

from alembic import context
from sqlalchemy import Connection, create_engine, pool

from app.core.config import cargar_settings
from app.core.logging import configurar_logging
from app.infrastructure.db.bootstrap.urls import url_psycopg
from app.infrastructure.db.modelos import Base

ESQUEMAS_DE_LIBRERIAS: Final = frozenset({"procrastinate", "langgraph"})
TABLAS_EXCLUIDAS: Final = frozenset({"alembic_version"})
LOCK_TIMEOUT: Final = "SET lock_timeout = '30s'"

target_metadata = Base.metadata


class ModoOfflineNoSoportado(RuntimeError):
    """Las migraciones necesitan una conexión real (usan el cursor DBAPI)."""

    def __init__(self) -> None:
        super().__init__("El modo offline no está soportado; usa una conexión real.")


def incluir_nombre(nombre: str | None, tipo: str, padres: dict[str, str | None]) -> bool:
    """Excluye esquemas de librerías y la tabla de versiones de la comparación."""
    if tipo == "schema":
        return nombre not in ESQUEMAS_DE_LIBRERIAS
    if tipo == "table":
        return nombre not in TABLAS_EXCLUIDAS and (
            padres.get("schema_name") not in ESQUEMAS_DE_LIBRERIAS
        )
    return True


def _migrar(conexion: Connection) -> None:
    """Fija `lock_timeout` de sesión y aplica las migraciones pedidas."""
    conexion.exec_driver_sql(LOCK_TIMEOUT)
    conexion.commit()
    context.configure(
        connection=conexion,
        target_metadata=target_metadata,
        include_name=incluir_nombre,
        transaction_per_migration=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _migrar_desde_cli() -> None:
    """Modo CLI: conecta con la URL de Settings (nunca se registra)."""
    settings = cargar_settings()
    configurar_logging(settings.log_level)
    motor = create_engine(url_psycopg(settings.url_base_datos_migrador()), poolclass=pool.NullPool)
    try:
        with motor.connect() as conexion:
            _migrar(conexion)
    finally:
        motor.dispose()


def main() -> None:
    """Punto de entrada que Alembic ejecuta al cargar el entorno."""
    if context.is_offline_mode():
        raise ModoOfflineNoSoportado
    conexion = context.config.attributes.get("connection")
    if isinstance(conexion, Connection):
        _migrar(conexion)
    else:
        _migrar_desde_cli()


main()
