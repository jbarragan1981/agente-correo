"""Esquema del checkpointer de LangGraph en `langgraph` (ADR-0010)."""

from typing import Final

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.engine import URL

from app.infrastructure.db.bootstrap.urls import conninfo

OPCION_ESQUEMA: Final = "-csearch_path=langgraph"  # sin espacios: libpq no decodifica "+"
CONCEDER: Final = "SELECT public.agente_conceder_privilegios(%s)"
ESQUEMA: Final = "langgraph"


async def preparar_checkpointer(url: URL) -> None:
    """Ejecuta `setup()` (idempotente) y concede privilegios al rol de aplicación."""
    async with AsyncPostgresSaver.from_conn_string(conninfo(url, options=OPCION_ESQUEMA)) as saver:
        await saver.setup()
    async with await psycopg.AsyncConnection.connect(conninfo(url), autocommit=True) as conexion:
        await conexion.execute(CONCEDER, (ESQUEMA,))
