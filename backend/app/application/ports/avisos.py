"""Puerto para avisos al operador que no deben pasar por el log estructurado."""

from typing import Protocol


class AvisoOperadorPort(Protocol):
    """Muestra una sola vez información sensible al operador que ejecuta el bootstrap."""

    def mostrar_contrasena_inicial(self, email_enmascarado: str, contrasena: str) -> None:
        """Muestra la contraseña inicial del administrador."""
        ...
