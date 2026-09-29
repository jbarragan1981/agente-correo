"""Configuración, proveedores, taxonomía y agentes con versiones de prompt inmutables.

Revisión: 0003_config_agentes_taxonomia
Anterior: 0002_identidad_auditoria
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.infrastructure.db.privilegios_migracion import conceder_privilegios_app

revision: str = "0003_config_agentes_taxonomia"
down_revision: str | None = "0002_identidad_auditoria"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_VERSION_ACTIVA = "fk_agentes_version_prompt_activa_id_versiones_prompt"
CLAVES_AGENTE = "'guardian', 'clasificador', 'enrutador', 'redactor', 'webchat', 'extractor'"

FUNCION_VERSION_INMUTABLE = r"""
CREATE FUNCTION public.versiones_prompt_inmutable() RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  IF OLD.publicado_en IS NULL THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;
  IF TG_OP = 'DELETE'
     OR NEW.numero IS DISTINCT FROM OLD.numero
     OR NEW.agente_id IS DISTINCT FROM OLD.agente_id
     OR NEW.prompt_sistema IS DISTINCT FROM OLD.prompt_sistema
     OR NEW.preguntas_jev IS DISTINCT FROM OLD.preguntas_jev
     OR NEW.esquema_salida IS DISTINCT FROM OLD.esquema_salida
     OR NEW.publicado_en IS DISTINCT FROM OLD.publicado_en THEN
    RAISE EXCEPTION 'una versión de prompt publicada es inmutable'
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END
$$
"""

TRIGGER_VERSION_INMUTABLE = (
    "CREATE TRIGGER versiones_prompt_inmutable BEFORE UPDATE OR DELETE ON public.versiones_prompt "
    "FOR EACH ROW EXECUTE FUNCTION public.versiones_prompt_inmutable()"
)


def _marcas_tiempo() -> list[sa.Column[object]]:
    """Columnas `creado_en` y `actualizado_en`."""
    return [
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def _crear_configuracion_y_proveedores() -> None:
    """Crea `configuracion` y `proveedores_ia`."""
    op.create_table(
        "configuracion",
        sa.Column("clave", sa.Text(), nullable=False),
        sa.Column("valor", postgresql.JSONB(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("editable_ui", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("actualizado_por", sa.Uuid(), nullable=True),
        *_marcas_tiempo(),
        sa.CheckConstraint(
            "clave ~ '^[a-z][a-z0-9_]{2,62}$'", name="ck_configuracion_clave_valida"
        ),
        sa.ForeignKeyConstraint(
            ["actualizado_por"],
            ["usuarios.id"],
            name="fk_configuracion_actualizado_por_usuarios",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("clave", name="pk_configuracion"),
    )
    op.create_table(
        "proveedores_ia",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("habilitado", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column(
            "config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        *_marcas_tiempo(),
        sa.CheckConstraint(
            "nombre IN ('anthropic', 'openai', 'gemini', 'jev')",
            name="ck_proveedores_ia_nombre_valido",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_proveedores_ia"),
        sa.UniqueConstraint("nombre", name="uq_proveedores_ia_nombre"),
    )


def _crear_taxonomia() -> None:
    """Crea `taxonomias` y `categorias`."""
    op.create_table(
        "taxonomias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("activa", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_marcas_tiempo(),
        sa.PrimaryKeyConstraint("id", name="pk_taxonomias"),
        sa.UniqueConstraint("nombre", name="uq_taxonomias_nombre"),
    )
    op.create_table(
        "categorias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taxonomia_id", sa.Uuid(), nullable=False),
        sa.Column("clave", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("descripcion_para_modelo", sa.Text(), nullable=False),
        sa.Column(
            "umbral_confianza",
            sa.Numeric(precision=3, scale=2),
            server_default=sa.text("0.70"),
            nullable=False,
        ),
        sa.Column("prioridad", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        *_marcas_tiempo(),
        sa.CheckConstraint("clave ~ '^[a-z][a-z0-9_]{1,39}$'", name="ck_categorias_clave_valida"),
        sa.CheckConstraint(
            "umbral_confianza BETWEEN 0 AND 1", name="ck_categorias_umbral_en_rango"
        ),
        sa.CheckConstraint("color ~ '^#[0-9a-fA-F]{6}$'", name="ck_categorias_color_hex"),
        sa.ForeignKeyConstraint(
            ["taxonomia_id"],
            ["taxonomias.id"],
            name="fk_categorias_taxonomia_id_taxonomias",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categorias"),
        sa.UniqueConstraint("taxonomia_id", "clave", name="uq_categorias_taxonomia_id"),
    )


def _crear_agentes() -> None:
    """Crea `agentes`, `versiones_prompt`, la FK compuesta y el trigger de inmutabilidad."""
    op.create_table(
        "agentes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clave", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("proveedor_id", sa.Uuid(), nullable=True),
        sa.Column("modelo", sa.Text(), nullable=True),
        sa.Column(
            "parametros",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("modelo_respaldo", sa.Text(), nullable=True),
        sa.Column(
            "herramientas",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("version_prompt_activa_id", sa.Uuid(), nullable=True),
        sa.Column("habilitado", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_marcas_tiempo(),
        sa.CheckConstraint(f"clave IN ({CLAVES_AGENTE})", name="ck_agentes_clave_valida"),
        sa.CheckConstraint(
            "tipo IN ('decision', 'generativo', 'reglas')", name="ck_agentes_tipo_valido"
        ),
        sa.CheckConstraint(
            "tipo = 'reglas' OR (proveedor_id IS NOT NULL AND modelo IS NOT NULL)",
            name="ck_agentes_modelo_requerido",
        ),
        sa.ForeignKeyConstraint(
            ["proveedor_id"],
            ["proveedores_ia.id"],
            name="fk_agentes_proveedor_id_proveedores_ia",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agentes"),
        sa.UniqueConstraint("clave", name="uq_agentes_clave"),
    )
    op.create_table(
        "versiones_prompt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agente_id", sa.Uuid(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("prompt_sistema", sa.Text(), nullable=False),
        sa.Column("preguntas_jev", postgresql.JSONB(), nullable=True),
        sa.Column("esquema_salida", postgresql.JSONB(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        *_marcas_tiempo(),
        sa.CheckConstraint("numero > 0", name="ck_versiones_prompt_numero_positivo"),
        sa.ForeignKeyConstraint(
            ["agente_id"],
            ["agentes.id"],
            name="fk_versiones_prompt_agente_id_agentes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuarios.id"],
            name="fk_versiones_prompt_creado_por_usuarios",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_versiones_prompt"),
        sa.UniqueConstraint("agente_id", "numero", name="uq_versiones_prompt_agente_id"),
        sa.UniqueConstraint("id", "agente_id", name="uq_versiones_prompt_id"),
    )
    op.create_foreign_key(
        FK_VERSION_ACTIVA,
        "agentes",
        "versiones_prompt",
        ["version_prompt_activa_id", "id"],
        ["id", "agente_id"],
    )
    op.execute(FUNCION_VERSION_INMUTABLE)
    op.execute(TRIGGER_VERSION_INMUTABLE)


def upgrade() -> None:
    """Crea las tablas de configuración, proveedores, taxonomía y agentes."""
    _crear_configuracion_y_proveedores()
    _crear_taxonomia()
    _crear_agentes()
    conceder_privilegios_app("public")


def downgrade() -> None:
    """Elimina primero la FK compuesta y el trigger, luego las tablas."""
    op.drop_constraint(FK_VERSION_ACTIVA, "agentes", type_="foreignkey")
    op.execute("DROP TRIGGER IF EXISTS versiones_prompt_inmutable ON public.versiones_prompt")
    op.execute("DROP FUNCTION IF EXISTS public.versiones_prompt_inmutable()")
    op.drop_table("versiones_prompt")
    op.drop_table("agentes")
    op.drop_table("categorias")
    op.drop_table("taxonomias")
    op.drop_table("proveedores_ia")
    op.drop_table("configuracion")
