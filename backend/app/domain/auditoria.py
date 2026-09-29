"""Entradas de auditoría del dominio (ADR-0009)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID

PATRON_ACCION: Final = re.compile(r"[a-z_]+(\.[a-z_]+)+")


class ActorTipo(StrEnum):
    """Quién realiza la acción auditada."""

    USUARIO = "usuario"
    SISTEMA = "sistema"
    AGENTE = "agente"


class AccionAuditoriaInvalida(ValueError):
    """La acción no sigue el formato `dominio.verbo`."""

    def __init__(self) -> None:
        super().__init__("la acción debe tener la forma dominio.verbo")


@dataclass(frozen=True)
class EntradaAuditoria:
    """Hecho auditable; `detalle` debe llegar ya redactado (sin secretos ni PII)."""

    actor_tipo: ActorTipo
    accion: str
    entidad: str | None = None
    entidad_id: str | None = None
    detalle: Mapping[str, object] = field(default_factory=dict)
    actor_id: UUID | None = None
    ip: str | None = None

    def __post_init__(self) -> None:
        """Valida la acción con el mismo patrón que el CHECK de la tabla y congela el detalle."""
        if PATRON_ACCION.fullmatch(self.accion) is None:
            raise AccionAuditoriaInvalida
        object.__setattr__(self, "detalle", MappingProxyType(dict(self.detalle)))
