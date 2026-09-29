"""Derivación de URLs del bootstrap y validación del nombre de la base (CA7, Q7)."""

import pytest

from app.infrastructure.db.bootstrap.errores import (
    ErrorBootstrap,
    NombreBaseInvalido,
    UrlInvalida,
)
from app.infrastructure.db.bootstrap.urls import (
    conninfo,
    nombre_base,
    url_mantenimiento,
    url_psycopg,
    usuario,
    validar_nombre_base,
)

CLAVE = "p@ss:w%rd/postgres"
URL = "postgresql+asyncpg://agente_app:p%40ss%3Aw%25rd%2Fpostgres@bd.ejemplo:6543/agente_correo"


def test_urls_psycopg_cambia_solo_el_driver() -> None:
    url = url_psycopg(URL)
    assert (url.drivername, url.username, url.password, url.host, url.port, url.database) == (
        "postgresql+psycopg",
        "agente_app",
        CLAVE,
        "bd.ejemplo",
        6543,
        "agente_correo",
    )


def test_urls_repr_y_str_ocultan_la_contrasena() -> None:
    url = url_psycopg(URL)
    assert ("p@ss" in repr(url), "p@ss" in str(url), "p%40ss" in str(url)) == (
        False,
        False,
        False,
    )


def test_urls_mantenimiento_apunta_a_postgres_con_la_misma_credencial() -> None:
    url = url_mantenimiento(url_psycopg(URL))
    assert (url.database, url.username, url.password) == ("postgres", "agente_app", CLAVE)


def test_urls_conninfo_libpq_con_opciones_decodifica_igual() -> None:
    import psycopg

    datos = psycopg.conninfo.conninfo_to_dict(conninfo(URL, options="-csearch_path=langgraph"))
    assert (datos["user"], datos["password"], datos["dbname"], datos["options"]) == (
        "agente_app",
        CLAVE,
        "agente_correo",
        "-csearch_path=langgraph",
    )


def test_urls_usuario() -> None:
    assert usuario(URL) == "agente_app"


def test_urls_nombre_base_valido() -> None:
    assert nombre_base(URL) == "agente_correo"


@pytest.mark.parametrize(
    "nombre",
    ["agente", "_privada", "A1_b2", "a" * 63],
)
def test_urls_nombres_de_base_validos(nombre: str) -> None:
    assert validar_nombre_base(nombre) == nombre


@pytest.mark.parametrize(
    "nombre",
    [
        None,
        "",
        "1empieza_con_digito",
        'con"comillas',
        "con'comilla",
        "con;punto_y_coma",
        "con espacio",
        "con-guion",
        "a" * 64,
        "agente\n",
        "ñandú",
        "x; DROP TABLE usuarios",
    ],
)
def test_urls_nombres_de_base_invalidos(nombre: str | None) -> None:
    with pytest.raises(NombreBaseInvalido) as error:
        validar_nombre_base(nombre)
    assert (error.value.paso, str(nombre) in str(error.value) if nombre else False) == (
        "configuracion",
        False,
    )


def test_urls_url_ininteligible_falla_sin_eco() -> None:
    texto = "esto-no-es-una-url-postgres"
    with pytest.raises(UrlInvalida) as error:
        url_psycopg(texto)
    assert (texto in str(error.value), error.value.__suppress_context__) == (False, True)


def test_urls_errores_no_incluyen_credenciales() -> None:
    error = ErrorBootstrap("espera", "OperationalError", "28P01")
    assert (str(error), error.tipo_error, error.sqlstate) == (
        "bootstrap.fallido en el paso espera",
        "OperationalError",
        "28P01",
    )


@pytest.mark.parametrize("clave", ["con espacio", " inicial y final ", "p@ss:w%rd/#?&=+ ñ;'\"x"])
def test_urls_conninfo_round_trip_con_caracteres_especiales_y_espacios(clave: str) -> None:
    """BUG-04: un espacio en la contraseña rompía la cadena libpq con ProgrammingError."""
    import psycopg
    from sqlalchemy.engine import URL as URL_SA

    url = URL_SA.create("postgresql+asyncpg", "agente_app", clave, "bd.ejemplo", 5432, "agente")
    datos = psycopg.conninfo.conninfo_to_dict(conninfo(url, options="-csearch_path=langgraph"))
    assert (datos["password"], datos["user"], datos["options"]) == (
        clave,
        "agente_app",
        "-csearch_path=langgraph",
    )
