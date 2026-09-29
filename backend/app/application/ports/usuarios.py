"""Puerto mínimo de usuarios para crear el administrador inicial."""

from typing import Protocol
from uuid import UUID


class RepositorioUsuariosPort(Protocol):
    """Acceso a `usuarios` y `usuarios_roles`."""

    async def hay_usuarios(self) -> bool:
        """Indica si existe al menos un usuario."""
        ...

    async def crear_con_rol(
        self,
        email: str,
        nombre: str,
        hash_password: str,
        requiere_cambio_password: bool,
        rol: str,
    ) -> UUID:
        """Crea el usuario, le asigna el rol indicado y devuelve su id."""
        ...
