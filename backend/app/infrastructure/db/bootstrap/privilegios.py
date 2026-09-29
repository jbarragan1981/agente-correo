"""Verificación activa de privilegios con roles separados; falla cerrado (ADR-0008).

La pertenencia a roles se comprueba con `MEMBER` (no `USAGE`): un rol miembro sin herencia
puede hacer `SET ROLE` y obtener los privilegios igualmente (S-M1).
"""

from typing import Final

import psycopg
from psycopg.rows import dict_row
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.db.bootstrap.errores import PrivilegiosInseguros
from app.infrastructure.db.bootstrap.urls import conninfo

# Roles predefinidos que dan acceso a archivos o programas del servidor.
ROLES_DE_SERVIDOR: Final = (
    "pg_execute_server_program",
    "pg_read_server_files",
    "pg_write_server_files",
)

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
      AND pg_has_role(current_user, c.relowner, 'MEMBER')
  ) AS propietario_de_tablas,
  pg_has_role(current_user, %(migrador)s::name, 'MEMBER') AS miembro_del_migrador,
  (
    pg_has_role(current_user, 'pg_execute_server_program', 'MEMBER')
    OR pg_has_role(current_user, 'pg_read_server_files', 'MEMBER')
    OR pg_has_role(current_user, 'pg_write_server_files', 'MEMBER')
  ) AS rol_de_servidor,
  has_table_privilege('public.auditoria', 'UPDATE') AS update_en_auditoria,
  has_table_privilege('public.auditoria', 'DELETE') AS delete_en_auditoria,
  has_table_privilege('public.auditoria', 'TRUNCATE') AS truncate_en_auditoria,
  has_table_privilege('public.alembic_version', 'INSERT, UPDATE, DELETE, TRUNCATE')
    AS modifica_alembic_version,
  CASE WHEN to_regclass('langgraph.checkpoint_migrations') IS NULL THEN false
       ELSE has_table_privilege(
         'langgraph.checkpoint_migrations', 'INSERT, UPDATE, DELETE, TRUNCATE')
  END AS modifica_checkpoint_migrations
FROM pg_roles r WHERE r.rolname = current_user
"""
CONSULTA_MIGRADOR = text(
    """
    SELECT
      current_user AS rol,
      r.rolsuper AS superusuario,
      r.rolcreaterole AS crea_roles,
      r.rolcreatedb AS crea_bases,
      r.rolbypassrls AS salta_rls,
      (
        pg_has_role(current_user, 'pg_execute_server_program', 'MEMBER')
        OR pg_has_role(current_user, 'pg_read_server_files', 'MEMBER')
        OR pg_has_role(current_user, 'pg_write_server_files', 'MEMBER')
      ) AS rol_de_servidor
    FROM pg_roles r WHERE r.rolname = current_user
    """
)
COMPROBACIONES_MIGRADOR: Final = (
    "superusuario",
    "crea_roles",
    "crea_bases",
    "salta_rls",
    "rol_de_servidor",
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
    "miembro_del_migrador",
    "rol_de_servidor",
    "update_en_auditoria",
    "delete_en_auditoria",
    "truncate_en_auditoria",
    "modifica_alembic_version",
    "modifica_checkpoint_migrations",
)


def comprobaciones_fallidas(fila: dict[str, object], rol_migrador: str) -> tuple[str, ...]:
    """Nombres de las comprobaciones que no se cumplen para el rol de aplicación."""
    fallidas = [f"app.{nombre}" for nombre in COMPROBACIONES_APP if fila.get(nombre)]
    if fila.get("rol") == rol_migrador:
        fallidas.append("app.mismo_rol_que_migrador")
    return tuple(fallidas)


def comprobaciones_fallidas_migrador(fila: dict[str, object]) -> tuple[str, ...]:
    """Nombres de las comprobaciones que no se cumplen para el rol migrador."""
    return tuple(f"migrador.{nombre}" for nombre in COMPROBACIONES_MIGRADOR if fila.get(nombre))


async def fila_migrador(motor: AsyncEngine) -> dict[str, object]:
    """Atributos del rol migrador (el de la conexión del bootstrap)."""
    async with motor.connect() as conexion:
        fila = (await conexion.execute(CONSULTA_MIGRADOR)).mappings().one()
    return dict(fila)


async def _fila_app(url_app: URL, rol_migrador: str) -> dict[str, object]:
    """Consulta los atributos del rol de aplicación conectándose como él."""
    async with await psycopg.AsyncConnection.connect(
        conninfo(url_app), autocommit=True, row_factory=dict_row
    ) as conexion:
        cursor = await conexion.execute(CONSULTA_ROL_APP, {"migrador": rol_migrador})
        fila = await cursor.fetchone()
    return dict(fila) if fila is not None else {"superusuario": True}


async def verificar_privilegios(motor_migrador: AsyncEngine, url_app: URL) -> None:
    """Lanza `PrivilegiosInseguros` con la lista de comprobaciones fallidas (sin credenciales)."""
    migrador = await fila_migrador(motor_migrador)
    nombre_migrador = str(migrador["rol"])
    fallidas = [
        *comprobaciones_fallidas_migrador(migrador),
        *comprobaciones_fallidas(await _fila_app(url_app, nombre_migrador), nombre_migrador),
    ]
    if fallidas:
        raise PrivilegiosInseguros(tuple(fallidas))
