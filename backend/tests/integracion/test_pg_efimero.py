"""La fixture rechaza servidores que no son UTF8 con un mensaje claro (BUG-07)."""

from collections.abc import Iterator

import pytest
from psycopg import sql

from tests.integracion.conftest import eliminar_base, nombre_prueba
from tests.integracion.pg_efimero import ServidorNoUtf8, ServidorPg, exigir_utf8


@pytest.fixture
def base_sql_ascii(postgres_efimero: ServidorPg) -> Iterator[str]:
    """Base con `server_encoding` SQL_ASCII (la codificación es por base)."""
    nombre = nombre_prueba()
    with postgres_efimero.conectar() as conexion:
        conexion.execute(
            sql.SQL(
                "CREATE DATABASE {} ENCODING 'SQL_ASCII' TEMPLATE template0 "
                "LC_COLLATE 'C' LC_CTYPE 'C'"
            ).format(sql.Identifier(nombre))
        )
    try:
        yield nombre
    finally:
        eliminar_base(postgres_efimero, nombre)


def test_pg_efimero_servidor_utf8_se_acepta(postgres_efimero: ServidorPg) -> None:
    assert exigir_utf8(postgres_efimero) is postgres_efimero


def test_pg_efimero_servidor_sql_ascii_falla_con_mensaje_claro(
    postgres_efimero: ServidorPg, base_sql_ascii: str
) -> None:
    with pytest.raises(ServidorNoUtf8) as error:
        exigir_utf8(postgres_efimero, base_sql_ascii)
    mensaje = str(error.value)
    assert (
        "server_encoding=SQL_ASCII" in mensaje,
        "--encoding=UTF8" in mensaje,
        postgres_efimero.contrasena in mensaje,
    ) == (True, True, False)
