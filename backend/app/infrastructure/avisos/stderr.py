"""Único módulo de `app/` que escribe directamente en stderr, fuera de structlog (ADR-0008)."""

import sys
from typing import Final

SEPARADOR: Final = "=" * 72
AVISO_UNA_VEZ: Final = "Se mostrará una sola vez; cámbiela en el primer inicio de sesión."


class AvisoStderr:
    """Muestra la contraseña inicial del admin en un bloque fijo (`AvisoOperadorPort`)."""

    def mostrar_contrasena_inicial(self, email_enmascarado: str, contrasena: str) -> None:
        """Escribe el bloque en stderr y lo vacía."""
        bloque = (
            f"{SEPARADOR}\n"
            f"Contraseña inicial del administrador {email_enmascarado}: {contrasena}\n"
            f"{AVISO_UNA_VEZ}\n"
            f"{SEPARADOR}\n"
        )
        sys.stderr.write(bloque)
        sys.stderr.flush()
