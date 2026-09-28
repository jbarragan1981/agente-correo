"""Hash Argon2id y generador de contraseñas (`docs/07-seguridad.md` §2)."""

import secrets
from typing import Final

from argon2 import PasswordHasher, Type

COSTE_TIEMPO: Final = 3
COSTE_MEMORIA_KIB: Final = 65536
PARALELISMO: Final = 4
BYTES_CONTRASENA: Final = 18


class HasherArgon2:
    """Argon2id con m=65536, t=3, p=4 (implementa `HasherPasswordPort`)."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=COSTE_TIEMPO,
            memory_cost=COSTE_MEMORIA_KIB,
            parallelism=PARALELISMO,
            type=Type.ID,
        )

    def hashear(self, contrasena: str) -> str:
        """Devuelve el hash codificado `$argon2id$...`."""
        return self._hasher.hash(contrasena)


class GeneradorContrasenaSecrets:
    """`secrets.token_urlsafe(18)`: 24 caracteres (implementa `GeneradorContrasenaPort`)."""

    def generar(self) -> str:
        """Devuelve una contraseña aleatoria nueva."""
        return secrets.token_urlsafe(BYTES_CONTRASENA)
