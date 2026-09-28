"""Extensiones, esquemas de librerías y función de privilegios.

Revisión: 0001_extensiones_esquemas
Anterior: ninguna
"""

from collections.abc import Sequence

from alembic import op

from app.infrastructure.db.privilegios_migracion import (
    borrar_funcion_privilegios,
    conceder_privilegios_app,
    crear_funcion_privilegios,
)

revision: str = "0001_extensiones_esquemas"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea extensiones (trusted) y los esquemas `langgraph` y `procrastinate`."""
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE SCHEMA IF NOT EXISTS langgraph")
    op.execute("CREATE SCHEMA IF NOT EXISTS procrastinate")
    crear_funcion_privilegios()
    conceder_privilegios_app("langgraph")
    conceder_privilegios_app("procrastinate")


def downgrade() -> None:
    """Elimina esquemas de librerías (con su contenido), la función y las extensiones."""
    borrar_funcion_privilegios()
    op.execute("DROP SCHEMA IF EXISTS langgraph CASCADE")
    op.execute("DROP SCHEMA IF EXISTS procrastinate CASCADE")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS citext")
