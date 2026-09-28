"""Derivación de URLs del bootstrap; los objetos `URL` ocultan la contraseña en `repr`/`str`."""

import re
from typing import Final

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from app.infrastructure.db.bootstrap.errores import NombreBaseInvalido, UrlInvalida

DRIVER_BOOTSTRAP: Final = "postgresql+psycopg"
DRIVER_LIBPQ: Final = "postgresql"
BASE_MANTENIMIENTO: Final = "postgres"
PATRON_NOMBRE_BASE: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}")


def _interpretar(url: str | URL) -> URL:
    """Convierte a `URL` sin propagar el texto original en el error."""
    try:
        return make_url(url)
    except (ArgumentError, ValueError):
        raise UrlInvalida from None


def url_psycopg(url: str | URL) -> URL:
    """Misma URL con el driver psycopg (host, puerto, base y credenciales intactos)."""
    return _interpretar(url).set(drivername=DRIVER_BOOTSTRAP)


def validar_nombre_base(nombre: str | None) -> str:
    """Devuelve el nombre si es un identificador simple; si no, `NombreBaseInvalido`."""
    if nombre is None or PATRON_NOMBRE_BASE.fullmatch(nombre) is None:
        raise NombreBaseInvalido
    return nombre


def nombre_base(url: str | URL) -> str:
    """Nombre de la base validado."""
    return validar_nombre_base(_interpretar(url).database)


def url_mantenimiento(url: str | URL) -> URL:
    """Misma credencial contra la base de mantenimiento `postgres`."""
    return _interpretar(url).set(database=BASE_MANTENIMIENTO)


def usuario(url: str | URL) -> str:
    """Nombre del rol de la URL (no es secreto, pero no se registra)."""
    return _interpretar(url).username or ""


def conninfo(url: str | URL, **opciones: str) -> str:
    """Cadena libpq para psycopg o LangGraph; solo vive en memoria, nunca se registra."""
    libpq = _interpretar(url).set(drivername=DRIVER_LIBPQ)
    if opciones:
        libpq = libpq.update_query_dict(opciones)
    # SQLAlchemy deja los espacios sin codificar y libpq los rechaza (BUG-04 de QA de E0.2).
    return libpq.render_as_string(hide_password=False).replace(" ", "%20")
