"""Tablas de identidad: `usuarios`, `roles` y `usuarios_roles`."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    Text,
    Uuid,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.modelos.base import Base, ConMarcasTiempo, columna_id


class Usuario(ConMarcasTiempo, Base):
    """Usuario del panel; `hash_password` es Argon2id."""

    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint("position('@' in email) > 1", name="email_valido"),)

    id: Mapped[uuid.UUID] = columna_id()
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    hash_password: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    requiere_cambio_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    mfa_secreto_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary)
    ultimo_acceso_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Rol(ConMarcasTiempo, Base):
    """Rol del panel (`admin`, `operador`, `auditor`)."""

    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("nombre IN ('admin', 'operador', 'auditor')", name="nombre_valido"),
    )

    id: Mapped[uuid.UUID] = columna_id()
    nombre: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)


class UsuarioRol(Base):
    """Asignación de un rol a un usuario."""

    __tablename__ = "usuarios_roles"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True
    )
    rol_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
