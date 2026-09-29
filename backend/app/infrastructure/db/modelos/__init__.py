"""Modelos SQLAlchemy de las tablas propias; importar el paquete registra toda la metadata."""

from app.infrastructure.db.modelos import (
    agentes,
    auditoria,
    configuracion,
    identidad,
    proveedores,
    taxonomia,
)
from app.infrastructure.db.modelos.base import Base

__all__ = [
    "Base",
    "agentes",
    "auditoria",
    "configuracion",
    "identidad",
    "proveedores",
    "taxonomia",
]
