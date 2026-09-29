"""Pruebas de los campos de base de datos y admin inicial de `Settings` (CA15, ADR-0008)."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import (
    URL_BD_DESARROLLO,
    ConfiguracionInvalida,
    Settings,
    cargar_settings,
)
from tests.soporte import DATABASE_URL_PRUEBA, valores_produccion

MARCADOR = "marcador-que-no-debe-aparecer"
URL_MIGRADOR_PRUEBA = "postgresql+asyncpg://migrador:postgres@bd.ejemplo:5432/agente"


def _settings(**valores: Any) -> Settings:
    """Construye Settings sin leer `.env`."""
    return Settings(_env_file=None, **valores)


def _error_de(**valores: Any) -> ValidationError:
    """Devuelve la ValidationError que produce la combinación indicada."""
    with pytest.raises(ValidationError) as capturado:
        _settings(**valores)
    return capturado.value


def _campos(error: ValidationError) -> set[str]:
    """Campos con error."""
    return {str(detalle["loc"][0]) for detalle in error.errors()}


def test_config_bd_valores_por_defecto() -> None:
    s = _settings()
    assert (
        s.database_url_migrador,
        s.db_auto_create,
        s.db_roles_separados,
        s.db_espera_max_s,
        s.db_bootstrap_lock_timeout_s,
        s.admin_initial_email,
        s.admin_initial_password,
    ) == (None, False, False, 60.0, 120.0, None, None)


def test_config_bd_produccion_rechaza_auto_create() -> None:
    error = _error_de(**valores_produccion(db_auto_create=True))
    assert _campos(error) == {"db_auto_create"}


def test_config_bd_produccion_exige_roles_separados() -> None:
    error = _error_de(**valores_produccion(db_roles_separados=False))
    assert _campos(error) == {"db_roles_separados"}


def test_config_bd_produccion_valida_sin_url_migrador() -> None:
    assert _settings(**valores_produccion()).database_url_migrador is None


@pytest.mark.parametrize("entorno", ["development", "test"])
def test_config_bd_fuera_de_produccion_admite_auto_create_y_rol_unico(entorno: str) -> None:
    s = _settings(env=entorno, db_auto_create=True, db_roles_separados=False)
    assert (s.db_auto_create, s.db_roles_separados) == (True, False)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://migrador:postgres@bd/agente",
        "postgresql+psycopg://migrador:postgres@bd/agente",
        "mysql://migrador:postgres@bd/agente",
    ],
)
def test_config_bd_url_migrador_exige_asyncpg(url: str) -> None:
    error = _error_de(database_url_migrador=url)
    assert (_campos(error), url in str(error)) == ({"database_url_migrador"}, False)


@pytest.mark.parametrize("vacia", ["", "   "])
def test_config_bd_url_migrador_vacia_equivale_a_ausente(vacia: str) -> None:
    assert _settings(database_url_migrador=vacia).database_url_migrador is None


def test_config_bd_url_migrador_se_devuelve_si_existe() -> None:
    s = _settings(database_url=DATABASE_URL_PRUEBA, database_url_migrador=URL_MIGRADOR_PRUEBA)
    assert s.url_base_datos_migrador() == URL_MIGRADOR_PRUEBA


def test_config_bd_url_migrador_sin_definir_usa_la_de_la_app() -> None:
    assert _settings(database_url=DATABASE_URL_PRUEBA).url_base_datos_migrador() == (
        DATABASE_URL_PRUEBA
    )


def test_config_bd_url_migrador_sin_nada_usa_la_local() -> None:
    assert _settings().url_base_datos_migrador() == URL_BD_DESARROLLO


def test_config_bd_url_migrador_no_aparece_en_repr() -> None:
    s = _settings(database_url_migrador=URL_MIGRADOR_PRUEBA)
    assert "migrador:postgres" not in repr(s)


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("db_espera_max_s", 0),
        ("db_espera_max_s", 601),
        ("db_bootstrap_lock_timeout_s", 0),
        ("db_bootstrap_lock_timeout_s", 1801),
    ],
)
def test_config_bd_tiempos_fuera_de_rango(campo: str, valor: float) -> None:
    assert _campos(_error_de(**{campo: valor})) == {campo}


def test_config_bd_admin_email_se_normaliza_a_minusculas() -> None:
    assert _settings(admin_initial_email="Admin@Ejemplo.COM").admin_initial_email == (
        "admin@ejemplo.com"
    )


@pytest.mark.parametrize(
    "email",
    [
        "sin-arroba",
        "a@b",
        "a b@ejemplo.com",
        "admin@ejemplo.com\nBcc: otro@ejemplo.com",
        "admin@ejemplo.com\n",
        "@ejemplo.com",
        "a" * 250 + "@ejemplo.com",
    ],
)
def test_config_bd_admin_email_invalido_sin_eco(email: str) -> None:
    error = _error_de(admin_initial_email=email)
    assert (_campos(error), email in str(error)) == ({"admin_initial_email"}, False)


@pytest.mark.parametrize("longitud", [1, 11, 129])
@pytest.mark.parametrize("entorno", ["development", "test", "production"])
def test_config_bd_admin_password_fuera_de_longitud(entorno: str, longitud: int) -> None:
    valor = "x" * longitud
    base = valores_produccion() if entorno == "production" else {"env": entorno}
    error = _error_de(**(base | {"admin_initial_password": valor}))
    assert (_campos(error), f"'{valor}'" in str(error)) == ({"admin_initial_password"}, False)


@pytest.mark.parametrize("longitud", [12, 128])
def test_config_bd_admin_password_en_limites_se_acepta(longitud: int) -> None:
    s = _settings(admin_initial_password="p" * longitud)
    assert s.admin_initial_password is not None
    assert s.admin_initial_password.get_secret_value() == "p" * longitud


def test_config_bd_admin_password_no_aparece_en_repr() -> None:
    s = _settings(admin_initial_password=f"{MARCADOR}-larga")
    assert MARCADOR not in repr(s)


def test_config_bd_cargar_settings_produccion_con_auto_create_falla_sin_valores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for clave, valor in valores_produccion(db_auto_create="true").items():
        monkeypatch.setenv(clave.upper(), str(valor))
    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", "corta")
    with pytest.raises(ConfiguracionInvalida) as capturado:
        cargar_settings()
    campos = {campo for campo, _ in capturado.value.errores}
    assert (campos, "corta" in str(capturado.value)) == (
        {"DB_AUTO_CREATE", "ADMIN_INITIAL_PASSWORD"},
        False,
    )
