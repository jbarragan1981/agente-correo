"""Tablas `taxonomias` y `categorias`."""

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.modelos.base import Base, ConMarcasTiempo, columna_id


class Taxonomia(ConMarcasTiempo, Base):
    """Conjunto de categorías aplicable a una cuenta."""

    __tablename__ = "taxonomias"

    id: Mapped[uuid.UUID] = columna_id()
    nombre: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())


class Categoria(ConMarcasTiempo, Base):
    """Categoría de una taxonomía; su descripción alimenta las preguntas de Jev."""

    __tablename__ = "categorias"
    __table_args__ = (
        CheckConstraint("clave ~ '^[a-z][a-z0-9_]{1,39}$'", name="clave_valida"),
        CheckConstraint("umbral_confianza BETWEEN 0 AND 1", name="umbral_en_rango"),
        CheckConstraint("color ~ '^#[0-9a-fA-F]{6}$'", name="color_hex"),
        UniqueConstraint("taxonomia_id", "clave"),
    )

    id: Mapped[uuid.UUID] = columna_id()
    taxonomia_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("taxonomias.id", ondelete="CASCADE"), nullable=False
    )
    clave: Mapped[str] = mapped_column(Text, nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion_para_modelo: Mapped[str] = mapped_column(Text, nullable=False)
    umbral_confianza: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, server_default=text("0.70")
    )
    prioridad: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    color: Mapped[str] = mapped_column(Text, nullable=False)
