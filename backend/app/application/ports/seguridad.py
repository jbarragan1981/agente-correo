"""Puertos de hash y generación de contraseñas."""

from typing import Protocol


class HasherPasswordPort(Protocol):
    """Deriva el hash almacenable de una contraseña (Argon2id, `docs/07-seguridad.md` §2)."""

    def hashear(self, contrasena: str) -> str:
        """Devuelve el hash codificado."""
        ...


class GeneradorContrasenaPort(Protocol):
    """Genera contraseñas aleatorias criptográficamente seguras."""

    def generar(self) -> str:
        """Devuelve una contraseña nueva."""
        ...
