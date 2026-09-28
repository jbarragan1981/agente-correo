"""Creación de la base si no existe (solo con `DB_AUTO_CREATE=true`, prohibido en producción)."""

import psycopg
from psycopg import errors, sql
from sqlalchemy.engine import URL

from app.core.logging import obtener_logger
from app.infrastructure.db.bootstrap.errores import BaseInexistente
from app.infrastructure.db.bootstrap.urls import conninfo, url_mantenimiento, validar_nombre_base

EXISTE_BASE = "SELECT 1 FROM pg_database WHERE datname = %s"

_log = obtener_logger(__name__)


async def asegurar_base(url: URL, nombre: str, crear: bool) -> bool:
    """Devuelve `True` si creó la base; `BaseInexistente` si falta y no debe crearla."""
    validar_nombre_base(nombre)
    async with await psycopg.AsyncConnection.connect(
        conninfo(url_mantenimiento(url)), autocommit=True
    ) as conexion:
        cursor = await conexion.execute(EXISTE_BASE, (nombre,))
        if await cursor.fetchone() is not None:
            return False
        if not crear:
            raise BaseInexistente
        try:
            await conexion.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nombre)))
        except (errors.DuplicateDatabase, errors.UniqueViolation):
            return False
    _log.info("bootstrap.base_creada")
    return True
