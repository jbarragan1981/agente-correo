"""Puerto de auditoría append-only (ADR-0009)."""

from typing import Protocol

from app.domain.auditoria import EntradaAuditoria


class AuditoriaPort(Protocol):
    """Registra hechos auditables en la transacción del llamador."""

    async def registrar(self, entrada: EntradaAuditoria) -> None:
        """Añade la entrada; el adaptador no confirma la transacción."""
        ...
