"""El rol de aplicación no escribe en `langgraph.checkpoint_migrations` (S-B1 de seguridad E0.2).

Revisión: 0006_revocar_migraciones_lg
Anterior: 0005_revocar_alembic_version

La app usa el checkpointer (tablas `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`)
pero nunca ejecuta `setup()`; con DML sobre la tabla de versiones, una inyección SQL podría
hacer que el siguiente `setup()` omita o repita migraciones. La v3 de
`agente_conceder_privilegios` lo revoca cada vez que se ejecuta, también tras el paso de
LangGraph del bootstrap (en una base nueva la tabla aún no existe durante esta revisión).
"""

from collections.abc import Sequence

from app.infrastructure.db.privilegios_migracion import (
    conceder_privilegios_app,
    crear_funcion_privilegios_v3,
    restaurar_funcion_privilegios_v2,
)

revision: str = "0006_revocar_migraciones_lg"
down_revision: str | None = "0005_revocar_alembic_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Instala la v3 y la aplica a `langgraph` (revoca DML en `checkpoint_migrations`)."""
    crear_funcion_privilegios_v3()
    conceder_privilegios_app("langgraph")


def downgrade() -> None:
    """Restaura la v2 y la aplica a `langgraph`, que vuelve a conceder el DML que concedía."""
    restaurar_funcion_privilegios_v2()
    conceder_privilegios_app("langgraph")
