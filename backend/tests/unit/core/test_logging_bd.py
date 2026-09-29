"""Redacción de logs para las URLs y claves nuevas de E0.2 (Q7, R5)."""

import pytest

from app.core.logging import REDACTADO, redactar, redactar_texto

CLAVE = "clave-marcador-qa"


@pytest.mark.parametrize(
    "texto",
    [
        f"postgresql+psycopg://agente_migrador:{CLAVE}@db:5432/agente_correo",
        f"postgresql+asyncpg://agente_app:{CLAVE}@db:5432/agente_correo",
        f"postgresql://agente_app:{CLAVE}@127.0.0.1:5432/postgres?options=-csearch_path=langgraph",
        f"host=db port=5432 user=agente_app password={CLAVE} dbname=agente_correo",
        f"host=db password='{CLAVE}' dbname=x",
        f"HOST=db PASSWORD={CLAVE}",
        f"conninfo: passwd = {CLAVE} sslmode=require",
        f"postgresql://u:x@h/db?password={CLAVE}&sslmode=require",
    ],
)
def test_redaccion_de_urls_y_dsn_de_bd_oculta_la_contrasena(texto: str) -> None:
    assert CLAVE not in redactar_texto(texto)


def test_redaccion_de_dsn_libpq_conserva_el_resto_del_texto() -> None:
    limpio = redactar_texto(f"connection failed host=db password={CLAVE} dbname=x")
    assert limpio == f"connection failed host=db password={REDACTADO} dbname=x"


@pytest.mark.parametrize(
    "clave",
    [
        "database_url",
        "DATABASE_URL_MIGRADOR",
        "admin_initial_password",
        "ADMIN_INITIAL_PASSWORD",
        "contrasena_generada",
        "contrasena",
        "AGENTE_MIGRADOR_PASSWORD",
        "AGENTE_APP_PASSWORD",
        "POSTGRES_PASSWORD",
        "pass_migrador_secret",
    ],
)
def test_redaccion_por_clave_cubre_las_variables_nuevas(clave: str) -> None:
    assert redactar(None, "info", {clave: CLAVE})[clave] == REDACTADO


def test_redaccion_conserva_el_booleano_generada_aleatoriamente() -> None:
    evento = redactar(None, "info", {"generada_aleatoriamente": True, "email": "a@ejemplo.com"})
    assert evento == {"generada_aleatoriamente": True, "email": "a***@ejemplo.com"}


def test_redaccion_de_trazas_con_dsn_libpq() -> None:
    evento = redactar(
        None, "error", {"exception": f"psycopg.OperationalError: host=db password={CLAVE}"}
    )
    assert CLAVE not in str(evento["exception"])
