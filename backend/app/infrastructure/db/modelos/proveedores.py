"""Tabla `proveedores_ia`."""

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Text, false, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.modelos.base import Base, ConMarcasTiempo, columna_id


class ProveedorIa(ConMarcasTiempo, Base):
    """Proveedor de IA; deshabilitado hasta que tenga credencial (E1.2)."""

    __tablename__ = "proveedores_ia"
    __table_args__ = (
        CheckConstraint("nombre IN ('anthropic', 'openai', 'gemini', 'jev')", name="nombre_valido"),
    )

    id: Mapped[uuid.UUID] = columna_id()
    nombre: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    habilitado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    base_url: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
