"""Verificación activa de privilegios con roles separados; falla cerrado (ADR-0008)."""

from typing import Final

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.db.bootstrap.errores import PrivilegiosInseguros
from app.infrastructure.db.bootstrap.urls import conninfo

CONSULTA_ROL_APP: Final = """
SELECT
  current_user AS rol,
  r.rolsuper AS superusuario,
  r.rolcreaterole AS crea_roles,
  r.rolcreatedb AS crea_bases,
  r.rolbypassrls AS salta_rls,
  has_database_privilege(current_database(), 'CREATE') AS create_en_base,
  has_schema_privilege('public', 'CREATE') AS create_en_public,
  coalesce(has_schema_privilege('langgraph', 'CREATE'), false) AS create_en_langgraph,
  coalesce(has_schema_privilege('procrastinate', 'CREATE'), false) AS create_en_procrastinate,
  EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname IN ('public', 'langgraph', 'procrastinate')
      AND pg_has_role(current_user, c.relowner, 'USAGE')
  ) AS propietario_de_tablas,
  has_table_privilege('public.auditoria', 'UPDATE') AS update_en_auditoria,
  has_table_privilege('public.auditoria', 'DELETE') AS delete_en_auditoria,
  has_table_privilege('public.auditoria', 'TRUNCATE') AS truncate_en_auditoria
FROM pg_roles r WHERE r.rolname = current_user
"""
CONSULTA_MIGRADOR = text(
    "SELECT current_user AS rol, r.rolsuper AS superusuario "
    "FROM pg_roles r WHERE r.rolname = current_user"
)
COMPROBACIONES_APP: Final = (
    "superusuario",
    "crea_roles",
    "crea_bases",
    "salta_rls",
    "create_en_base",
    "create_en_public",
    "create_en_langgraph",
    "create_en_procrastinate",
    "propietario_de_tablas",
    "update_en_auditoria",
    "delete_en_auditoria",
    "truncate_en_auditoria",
)


def comprobaciones_fallidas(fila: dict[str, object], rol_migrador: str) -> tuple[str, ...]:
    """Nombres de las comprobaciones que no se cumplen para el rol de aplicación."""
    fallidas = [f"app.{nombre}" for nombre in COMPROBACIONES_APP if fila.get(nombre)]
    if fila.get("rol") == rol_migrador:
        fallidas.append("app.mismo_rol_que_migrador")
    return tuple(fallidas)


async def rol_migrador(motor: AsyncEngine) -> tuple[str, bool]:
    """Nombre del rol migrador y si es superusuario."""
    async with motor.connect() as conexion:
        fila = (await conexion.execute(CONSULTA_MIGRADOR)).mappings().one()
    return str(fila["rol"]), bool(fila["superusuario"])


async def _fila_app(url_app: URL) -> dict[str, object]:
    """Consulta los atributos del rol de aplicación conectándose como él."""
    async with await psycopg.AsyncConnection.connect(
        conninfo(url_app), autocommit=True, row_factory=dict_row
    ) as conexion:
        cursor = await conexion.execute(CONSULTA_ROL_APP)
        fila = await cursor.fetchone()
    return dict(fila) if fila is not None else {"superusuario": True}


async def verificar_privilegios(motor_migrador: AsyncEngine, url_app: URL) -> None:
    """Lanza `PrivilegiosInseguros` con la lista de comprobaciones fallidas (sin credenciales)."""
    nombre_migrador, migrador_superusuario = await rol_migrador(motor_migrador)
    fallidas = list(comprobaciones_fallidas(await _fila_app(url_app), nombre_migrador))
    if migrador_superusuario:
        fallidas.insert(0, "migrador.superusuario")
    if fallidas:
        raise PrivilegiosInseguros(tuple(fallidas))
