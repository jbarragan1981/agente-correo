"""Tabla `auditoria` append-only con hash encadenado (ADR-0009)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    LargeBinary,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.modelos.base import Base, columna_id


class Auditoria(Base):
    """Entrada de auditoría; `ocurrido_en`, `hash_previo` y `hash` los fija un trigger."""

    __tablename__ = "auditoria"
    __table_args__ = (
        CheckConstraint("actor_tipo IN ('usuario', 'sistema', 'agente')", name="actor_tipo_valido"),
        CheckConstraint(r"accion ~ '^[a-z_]+(\.[a-z_]+)+$'", name="accion_valida"),
        Index("ix_auditoria_entidad_entidad_id", "entidad", "entidad_id"),
        Index("ix_auditoria_actor_id_ocurrido_en", "actor_id", "ocurrido_en"),
        Index("ix_auditoria_ocurrido_en_brin", "ocurrido_en", postgresql_using="brin"),
    )

    id: Mapped[uuid.UUID] = columna_id()
    secuencia: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), nullable=False, unique=True
    )
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_tipo: Mapped[str] = mapped_column(Text, nullable=False)
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    entidad: Mapped[str | None] = mapped_column(Text)
    entidad_id: Mapped[str | None] = mapped_column(Text)
    detalle: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    ip: Mapped[str | None] = mapped_column(INET)
    hash_previo: Mapped[bytes | None] = mapped_column(LargeBinary)
    hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
