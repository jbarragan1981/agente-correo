"""Identidad (`usuarios`, `roles`, `usuarios_roles`) y `auditoria` append-only (ADR-0009).

Revisión: 0002_identidad_auditoria
Anterior: 0001_extensiones_esquemas
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.infrastructure.db.privilegios_migracion import conceder_privilegios_app

revision: str = "0002_identidad_auditoria"
down_revision: str | None = "0001_extensiones_esquemas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCION_HASH = r"""
CREATE FUNCTION public.auditoria_calcular_hash(
  hash_previo bytea, secuencia bigint, ocurrido_en timestamptz, actor_id uuid, actor_tipo text,
  accion text, entidad text, entidad_id text, detalle jsonb, ip inet
) RETURNS bytea
LANGUAGE sql IMMUTABLE
SET search_path = public, pg_temp
AS $$
  SELECT digest(
    coalesce(hash_previo, ''::bytea) || convert_to(
      jsonb_build_array(
        secuencia,
        (extract(epoch FROM ocurrido_en) * 1000000)::bigint,
        actor_id, actor_tipo, accion, entidad, entidad_id, detalle, host(ip)
      )::text,
      'UTF8'
    ),
    'sha256'
  )
$$
"""

FUNCION_ENCADENAR = r"""
CREATE FUNCTION public.auditoria_encadenar() RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  previo bytea;
BEGIN
  -- 0xA6E17F: serializa las inserciones para que la cadena sea lineal.
  PERFORM pg_advisory_xact_lock(10936703);
  -- La secuencia se asigna tras el lock para que su orden coincida con el de la cadena.
  NEW.secuencia := nextval(pg_get_serial_sequence('public.auditoria', 'secuencia'));
  SELECT a.hash INTO previo FROM public.auditoria a ORDER BY a.secuencia DESC LIMIT 1;
  NEW.ocurrido_en := now();
  NEW.hash_previo := previo;
  NEW.hash := public.auditoria_calcular_hash(
    previo, NEW.secuencia, NEW.ocurrido_en, NEW.actor_id, NEW.actor_tipo, NEW.accion,
    NEW.entidad, NEW.entidad_id, NEW.detalle, NEW.ip
  );
  RETURN NEW;
END
$$
"""

FUNCION_INMUTABLE = r"""
CREATE FUNCTION public.auditoria_inmutable() RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  RAISE EXCEPTION 'la auditoría es append-only' USING ERRCODE = 'insufficient_privilege';
END
$$
"""

TRIGGERS = (
    "CREATE TRIGGER auditoria_encadenar BEFORE INSERT ON public.auditoria "
    "FOR EACH ROW EXECUTE FUNCTION public.auditoria_encadenar()",
    "CREATE TRIGGER auditoria_inmutable_fila BEFORE UPDATE OR DELETE ON public.auditoria "
    "FOR EACH ROW EXECUTE FUNCTION public.auditoria_inmutable()",
    "CREATE TRIGGER auditoria_inmutable_truncate BEFORE TRUNCATE ON public.auditoria "
    "FOR EACH STATEMENT EXECUTE FUNCTION public.auditoria_inmutable()",
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


def _crear_identidad() -> None:
    """Crea `usuarios`, `roles` y `usuarios_roles`."""
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("hash_password", sa.Text(), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "requiere_cambio_password", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("mfa_secreto_cifrado", sa.LargeBinary(), nullable=True),
        sa.Column("ultimo_acceso_en", sa.DateTime(timezone=True), nullable=True),
        *_marcas_tiempo(),
        sa.CheckConstraint("position('@' in email) > 1", name="ck_usuarios_email_valido"),
        sa.PrimaryKeyConstraint("id", name="pk_usuarios"),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        *_marcas_tiempo(),
        sa.CheckConstraint(
            "nombre IN ('admin', 'operador', 'auditor')", name="ck_roles_nombre_valido"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint("nombre", name="uq_roles_nombre"),
    )
    op.create_table(
        "usuarios_roles",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("rol_id", sa.Uuid(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name="fk_usuarios_roles_usuario_id_usuarios",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rol_id"], ["roles.id"], name="fk_usuarios_roles_rol_id_roles", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("usuario_id", "rol_id", name="pk_usuarios_roles"),
    )


def _crear_auditoria() -> None:
    """Crea `auditoria`, sus índices, funciones y triggers."""
    op.create_table(
        "auditoria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("secuencia", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "ocurrido_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_tipo", sa.Text(), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("entidad", sa.Text(), nullable=True),
        sa.Column("entidad_id", sa.Text(), nullable=True),
        sa.Column(
            "detalle",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("hash_previo", sa.LargeBinary(), nullable=True),
        sa.Column("hash", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint(
            "actor_tipo IN ('usuario', 'sistema', 'agente')",
            name="ck_auditoria_actor_tipo_valido",
        ),
        sa.CheckConstraint(r"accion ~ '^[a-z_]+(\.[a-z_]+)+$'", name="ck_auditoria_accion_valida"),
        sa.PrimaryKeyConstraint("id", name="pk_auditoria"),
        sa.UniqueConstraint("secuencia", name="uq_auditoria_secuencia"),
    )
    op.create_index("ix_auditoria_entidad_entidad_id", "auditoria", ["entidad", "entidad_id"])
    op.create_index("ix_auditoria_actor_id_ocurrido_en", "auditoria", ["actor_id", "ocurrido_en"])
    op.create_index(
        "ix_auditoria_ocurrido_en_brin", "auditoria", ["ocurrido_en"], postgresql_using="brin"
    )
    op.execute(FUNCION_HASH)
    op.execute(FUNCION_ENCADENAR)
    op.execute(FUNCION_INMUTABLE)
    for trigger in TRIGGERS:
        op.execute(trigger)


def upgrade() -> None:
    """Crea identidad y auditoría y concede privilegios al rol de aplicación."""
    _crear_identidad()
    _crear_auditoria()
    conceder_privilegios_app("public")


def downgrade() -> None:
    """Elimina auditoría (tabla, triggers y funciones) e identidad."""
    op.drop_table("auditoria")
    op.execute("DROP FUNCTION IF EXISTS public.auditoria_inmutable()")
    op.execute("DROP FUNCTION IF EXISTS public.auditoria_encadenar()")
    op.execute(
        "DROP FUNCTION IF EXISTS public.auditoria_calcular_hash("
        "bytea, bigint, timestamptz, uuid, text, text, text, text, jsonb, inet)"
    )
    op.drop_table("usuarios_roles")
    op.drop_table("roles")
    op.drop_table("usuarios")
