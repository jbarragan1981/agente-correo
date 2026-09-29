"""Repositorio SQL mínimo de usuarios (implementa `RepositorioUsuariosPort`)."""

import uuid

from sqlalchemy import exists, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.ids import nuevo_id
from app.infrastructure.db.modelos.identidad import Rol, Usuario, UsuarioRol


class RepositorioUsuariosSql:
    """Opera en la transacción del llamador."""

    def __init__(self, conexion: AsyncConnection) -> None:
        self._conexion = conexion

    async def hay_usuarios(self) -> bool:
        """Indica si existe algún usuario."""
        return bool((await self._conexion.execute(select(exists().select_from(Usuario)))).scalar())

    async def crear_con_rol(
        self,
        email: str,
        nombre: str,
        hash_password: str,
        requiere_cambio_password: bool,
        rol: str,
    ) -> uuid.UUID:
        """Crea el usuario y lo asocia al rol (que debe existir)."""
        usuario_id = nuevo_id()
        await self._conexion.execute(
            insert(Usuario).values(
                id=usuario_id,
                email=email,
                nombre=nombre,
                hash_password=hash_password,
                requiere_cambio_password=requiere_cambio_password,
            )
        )
        rol_id = (
            await self._conexion.execute(select(Rol.id).where(Rol.nombre == rol))
        ).scalar_one()
        await self._conexion.execute(
            insert(UsuarioRol).values(usuario_id=usuario_id, rol_id=rol_id)
        )
        return usuario_id
