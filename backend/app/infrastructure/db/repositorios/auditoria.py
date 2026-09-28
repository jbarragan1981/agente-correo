"""Repositorio SQL de auditoría (implementa `AuditoriaPort`, ADR-0009)."""

from dataclasses import dataclass
from typing import Final

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.ids import nuevo_id
from app.domain.auditoria import EntradaAuditoria
from app.infrastructure.db.modelos.auditoria import Auditoria

VERIFICAR_CADENA: Final = text(
    """
    WITH cadena AS (
      SELECT a.*, lag(a.hash) OVER (ORDER BY a.secuencia) AS previo_real
      FROM auditoria a
    )
    SELECT
      count(*) AS filas,
      min(secuencia) FILTER (
        WHERE hash_previo IS DISTINCT FROM previo_real
           OR hash IS DISTINCT FROM auditoria_calcular_hash(
                previo_real, secuencia, ocurrido_en, actor_id, actor_tipo, accion,
                entidad, entidad_id, detalle, ip)
      ) AS primera_rota
    FROM cadena
    """
)


@dataclass(frozen=True)
class VerificacionCadena:
    """Resultado de recalcular la cadena de hashes."""

    ok: bool
    primera_secuencia_rota: int | None
    filas: int


class RepositorioAuditoriaSql:
    """Inserta en la transacción del llamador; `ocurrido_en` y los hashes los fija el trigger."""

    def __init__(self, conexion: AsyncConnection) -> None:
        self._conexion = conexion

    async def registrar(self, entrada: EntradaAuditoria) -> None:
        """Inserta la entrada sin confirmar la transacción."""
        await self._conexion.execute(
            insert(Auditoria).values(
                id=nuevo_id(),
                actor_id=entrada.actor_id,
                actor_tipo=str(entrada.actor_tipo),
                accion=entrada.accion,
                entidad=entrada.entidad,
                entidad_id=entrada.entidad_id,
                detalle=dict(entrada.detalle),
                ip=entrada.ip,
            )
        )

    async def verificar_cadena(self) -> VerificacionCadena:
        """Recalcula la cadena en SQL y devuelve la primera `secuencia` rota, si la hay."""
        fila = (await self._conexion.execute(VERIFICAR_CADENA)).mappings().one()
        rota = fila["primera_rota"]
        return VerificacionCadena(
            ok=rota is None,
            primera_secuencia_rota=None if rota is None else int(rota),
            filas=int(fila["filas"]),
        )
