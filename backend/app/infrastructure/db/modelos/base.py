"""Base declarativa con convención de nombres determinista y mixin de marcas de tiempo."""

import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.ids import nuevo_id

CONVENCION_NOMBRES: Final = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base de todos los modelos propios (esquema `public`)."""

    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


def columna_id() -> Mapped[uuid.UUID]:
    """Clave primaria UUID v7 generada en la aplicación."""
    return mapped_column(Uuid, primary_key=True, default=nuevo_id)


class ConMarcasTiempo:
    """Añade `creado_en` y `actualizado_en` fijados por el servidor."""

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
