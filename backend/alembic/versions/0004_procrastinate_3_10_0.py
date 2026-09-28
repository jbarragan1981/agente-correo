"""Esquema de procrastinate 3.10.0 en el esquema `procrastinate` (ADR-0010).

Revisión: 0004_procrastinate_3_10_0
Anterior: 0003_config_agentes_taxonomia

El SQL se ejecuta con el cursor DBAPI de psycopg sin parámetros: es multi-sentencia y contiene
`%`, así que no sirve `op.execute` ni `exec_driver_sql`.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Final

from alembic import op

from app.infrastructure.db.privilegios_migracion import conceder_privilegios_app

revision: str = "0004_procrastinate_3_10_0"
down_revision: str | None = "0003_config_agentes_taxonomia"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VERSION_PROCRASTINATE: Final = "3.10.0"
ARCHIVO_SQL: Final = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "procrastinate"
    / f"{VERSION_PROCRASTINATE}_schema.sql"
)


def _ejecutar_script(script: str) -> None:
    """Ejecuta un script multi-sentencia con el cursor DBAPI de la conexión de Alembic."""
    cursor = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cursor.execute(script)
    finally:
        cursor.close()


def upgrade() -> None:
    """Aplica el esquema copiado de procrastinate y concede privilegios a la app."""
    op.execute("SET LOCAL search_path = procrastinate")
    _ejecutar_script(ARCHIVO_SQL.read_text(encoding="utf-8"))
    op.execute("SET LOCAL search_path = public")
    conceder_privilegios_app("procrastinate")


def downgrade() -> None:
    """Vacía el esquema `procrastinate` (lo sigue gestionando la revisión 0001)."""
    op.execute("DROP SCHEMA IF EXISTS procrastinate CASCADE")
    op.execute("CREATE SCHEMA procrastinate")
    conceder_privilegios_app("procrastinate")
