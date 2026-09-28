"""Generación de identificadores UUID v7 (ordenables por tiempo) para claves primarias."""

import uuid

import uuid_utils


def nuevo_id() -> uuid.UUID:
    """Devuelve un UUID v7 como `uuid.UUID` de la biblioteca estándar."""
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)
