"""Tablas `agentes` y `versiones_prompt` (versiones publicadas inmutables)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.modelos.base import Base, ConMarcasTiempo, columna_id

CLAVES_AGENTE = "'guardian', 'clasificador', 'enrutador', 'redactor', 'webchat', 'extractor'"


class Agente(ConMarcasTiempo, Base):
    """Agente del enjambre; la versión activa debe pertenecer al mismo agente (FK compuesta)."""

    __tablename__ = "agentes"
    __table_args__ = (
        CheckConstraint(f"clave IN ({CLAVES_AGENTE})", name="clave_valida"),
        CheckConstraint("tipo IN ('decision', 'generativo', 'reglas')", name="tipo_valido"),
        CheckConstraint(
            "tipo = 'reglas' OR (proveedor_id IS NOT NULL AND modelo IS NOT NULL)",
            name="modelo_requerido",
        ),
        ForeignKeyConstraint(
            ["version_prompt_activa_id", "id"],
            ["versiones_prompt.id", "versiones_prompt.agente_id"],
            use_alter=True,
        ),
    )

    id: Mapped[uuid.UUID] = columna_id()
    clave: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("proveedores_ia.id", ondelete="RESTRICT")
    )
    modelo: Mapped[str | None] = mapped_column(Text)
    parametros: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    modelo_respaldo: Mapped[str | None] = mapped_column(Text)
    herramientas: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    version_prompt_activa_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    habilitado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())


class VersionPrompt(ConMarcasTiempo, Base):
    """Versión del prompt de un agente; inmutable una vez publicada (trigger)."""

    __tablename__ = "versiones_prompt"
    __table_args__ = (
        CheckConstraint("numero > 0", name="numero_positivo"),
        UniqueConstraint("agente_id", "numero"),
        UniqueConstraint("id", "agente_id"),
    )

    id: Mapped[uuid.UUID] = columna_id()
    agente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agentes.id", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_sistema: Mapped[str] = mapped_column(Text, nullable=False)
    # none_as_null: `None` se guarda como SQL NULL (no como JSON `null`).
    preguntas_jev: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    esquema_salida: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    notas: Mapped[str | None] = mapped_column(Text)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
