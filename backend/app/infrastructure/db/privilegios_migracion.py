"""Privilegios explícitos del rol de aplicación por esquema (ADR-0010).

Lo usan las revisiones de `backend/alembic/versions`. La función SQL
`agente_conceder_privilegios(esquema)` la crea la revisión 0001. Es idempotente
y no hace nada si los roles `agente_app`/`agente_lectura` no existen (modo de rol único). Al
final revoca a `agente_app` cualquier privilegio de modificación sobre `auditoria`.
"""

from typing import Final

import sqlalchemy as sa
from alembic import op

ESQUEMAS_PERMITIDOS: Final = ("public", "procrastinate", "langgraph")

CREAR_FUNCION: Final = r"""
CREATE OR REPLACE FUNCTION public.agente_conceder_privilegios(esquema text)
RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  es_propietario boolean;
BEGIN
  IF esquema NOT IN ('public', 'procrastinate', 'langgraph') THEN
    RAISE EXCEPTION 'esquema no permitido' USING ERRCODE = 'invalid_parameter_value';
  END IF;
  SELECT pg_has_role(current_user, n.nspowner, 'USAGE') INTO es_propietario
    FROM pg_namespace n WHERE n.nspname = esquema;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente_app') THEN
    IF es_propietario THEN
      EXECUTE format('GRANT USAGE ON SCHEMA %I TO agente_app', esquema);
    END IF;
    EXECUTE format(
      'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO agente_app', esquema);
    EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO agente_app', esquema);
    IF esquema <> 'public' THEN
      EXECUTE format('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA %I TO agente_app', esquema);
    END IF;
    IF to_regclass('public.auditoria') IS NOT NULL THEN
      REVOKE UPDATE, DELETE, TRUNCATE ON public.auditoria FROM agente_app;
    END IF;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agente_lectura') THEN
    IF es_propietario THEN
      EXECUTE format('GRANT USAGE ON SCHEMA %I TO agente_lectura', esquema);
    END IF;
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO agente_lectura', esquema);
  END IF;
END
$$
"""

REVOCAR_EJECUCION: Final = (
    "REVOKE EXECUTE ON FUNCTION public.agente_conceder_privilegios(text) FROM PUBLIC"
)
BORRAR_FUNCION: Final = "DROP FUNCTION IF EXISTS public.agente_conceder_privilegios(text)"
CONCEDER: Final = sa.text("SELECT public.agente_conceder_privilegios(:esquema)")


def crear_funcion_privilegios() -> None:
    """Crea la función de privilegios y la reserva al propietario."""
    op.execute(CREAR_FUNCION)
    op.execute(REVOCAR_EJECUCION)


def borrar_funcion_privilegios() -> None:
    """Elimina la función de privilegios."""
    op.execute(BORRAR_FUNCION)


def conceder_privilegios_app(esquema: str) -> None:
    """Concede al rol de aplicación los privilegios del esquema y protege `auditoria`."""
    if esquema not in ESQUEMAS_PERMITIDOS:
        raise ValueError(esquema)
    op.execute(CONCEDER.bindparams(esquema=esquema))
