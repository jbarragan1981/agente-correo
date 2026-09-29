"""Tabla `configuracion` (clave → valor JSONB)."""

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Text, Uuid, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.modelos.base import Base, ConMarcasTiempo


class Configuracion(ConMarcasTiempo, Base):
    """Parámetro de configuración editable desde el panel."""

    __tablename__ = "configuracion"
    __table_args__ = (CheckConstraint("clave ~ '^[a-z][a-z0-9_]{2,62}$'", name="clave_valida"),)

    clave: Mapped[str] = mapped_column(Text, primary_key=True)
    valor: Mapped[Any] = mapped_column(JSONB, nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    editable_ui: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="SET NULL")
    )
