"""El rol de aplicación solo lee `alembic_version` (BUG-03 de QA E0.2).

Revisión: 0005_revocar_alembic_version
Anterior: 0004_procrastinate_3_10_0

La sonda de readiness solo necesita `SELECT`. Con DML, una inyección SQL en la API podría
falsear la revisión que lee la sonda o alterar el siguiente bootstrap. La v2 de
`agente_conceder_privilegios` revoca ese DML cada vez que se ejecuta (migraciones y paso de
LangGraph), igual que con `auditoria`.
"""

from collections.abc import Sequence

from app.infrastructure.db.privilegios_migracion import (
    conceder_privilegios_app,
    crear_funcion_privilegios_v2,
    restaurar_funcion_privilegios_v1,
)

revision: str = "0005_revocar_alembic_version"
down_revision: str | None = "0004_procrastinate_3_10_0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Instala la v2 de la función y la aplica a `public` (revoca DML en `alembic_version`)."""
    crear_funcion_privilegios_v2()
    conceder_privilegios_app("public")


def downgrade() -> None:
    """Restaura la v1 y el DML de `agente_app` sobre `alembic_version` que concedía."""
    restaurar_funcion_privilegios_v1()
