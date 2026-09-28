"""Pruebas de `Settings` y `cargar_settings` (CA5, CA10, ADR-0007)."""

import base64
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import (
    URL_BD_DESARROLLO,
    ConfiguracionInvalida,
    Settings,
    cargar_settings,
)
from tests.soporte import (
    APP_MASTER_KEY_PRUEBA,
    DATABASE_URL_PRUEBA,
    JWT_SECRET_PRUEBA,
    valores_produccion,
)

MARCADOR_SECRETO = "valor-marcador-secreto"


def _settings(**valores: Any) -> Settings:
    """Construye Settings sin leer `.env`."""
    return Settings(_env_file=None, **valores)


def _campos_con_error(error: ValidationError) -> set[str]:
    """Nombres de campo con error en una ValidationError."""
    return {str(detalle["loc"][0]) for detalle in error.errors()}


@pytest.fixture
def sin_archivo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hace que `cargar_settings` lea solo variables de proceso."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)


def test_settings_produccion_valida_carga_sin_error() -> None:
    settings = _settings(**valores_produccion())
    assert settings.es_produccion


def test_settings_desarrollo_sin_variables_usa_defaults_seguros() -> None:
    settings = _settings()
    assert (settings.env, settings.cors_origenes, settings.url_base_datos()) == (
        "development",
        [],
        URL_BD_DESARROLLO,
    )


def test_settings_url_explicita_se_devuelve_tal_cual() -> None:
    settings = _settings(database_url=DATABASE_URL_PRUEBA)
    assert settings.url_base_datos() == DATABASE_URL_PRUEBA


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"app_master_key": None}, "app_master_key"),
        ({"app_master_key": "no-es-base64!!"}, "app_master_key"),
        ({"app_master_key": base64.b64encode(b"k" * 31).decode()}, "app_master_key"),
        ({"app_master_key": base64.b64encode(b"k" * 33).decode()}, "app_master_key"),
        ({"jwt_secret": None}, "jwt_secret"),
        ({"jwt_secret": "j" * 31}, "jwt_secret"),
        ({"database_url": None}, "database_url"),
        ({"debug": True}, "debug"),
        ({"cors_origenes": ""}, "cors_origenes"),
        ({"cors_origenes": "http://panel.ejemplo.com"}, "cors_origenes"),
    ],
    ids=[
        "sin_app_master_key",
        "app_master_key_no_base64",
        "app_master_key_31_bytes",
        "app_master_key_33_bytes",
        "sin_jwt_secret",
        "jwt_secret_31_bytes",
        "sin_database_url",
        "debug_true",
        "cors_vacio",
        "cors_http",
    ],
)
def test_settings_produccion_invalida_falla_en_el_campo(
    cambios: dict[str, Any], campo: str
) -> None:
    with pytest.raises(ValidationError) as error:
        _settings(**valores_produccion(**cambios))
    assert _campos_con_error(error.value) == {campo}


@pytest.mark.parametrize(
    "origen",
    ["*", "https://panel.ejemplo.com/ruta", "panel.ejemplo.com", "https://*.ejemplo.com"],
    ids=["comodin", "con_ruta", "sin_esquema", "comodin_subdominio"],
)
def test_settings_cors_origen_invalido_falla(origen: str) -> None:
    with pytest.raises(ValidationError):
        _settings(cors_origenes=origen)


def test_settings_cors_lista_con_espacios_se_normaliza() -> None:
    settings = _settings(cors_origenes=" https://a.ejemplo.com , http://localhost:4200 ,")
    assert settings.cors_origenes == ["https://a.ejemplo.com", "http://localhost:4200"]


def test_settings_database_url_con_otro_esquema_falla() -> None:
    with pytest.raises(ValidationError):
        _settings(database_url="postgresql://usuario:postgres@bd.ejemplo/agente")


def test_settings_error_de_validacion_no_contiene_el_valor() -> None:
    with pytest.raises(ValidationError) as error:
        _settings(**valores_produccion(jwt_secret=MARCADOR_SECRETO))
    assert MARCADOR_SECRETO not in str(error.value)


def test_settings_repr_no_contiene_secretos() -> None:
    texto = repr(_settings(**valores_produccion()))
    assert not any(
        secreto in texto
        for secreto in (APP_MASTER_KEY_PRUEBA, JWT_SECRET_PRUEBA, "clave-de-prueba")
    )


@pytest.mark.usefixtures("sin_archivo_env")
def test_cargar_settings_invalida_lanza_sin_valores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", MARCADOR_SECRETO)
    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_settings()
    assert MARCADOR_SECRETO not in str(error.value)


@pytest.mark.usefixtures("sin_archivo_env")
def test_cargar_settings_invalida_nombra_los_campos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_settings()
    assert {campo for campo, _ in error.value.errores} == {
        "DATABASE_URL",
        "APP_MASTER_KEY",
        "JWT_SECRET",
        "CORS_ORIGENES",
    }


@pytest.mark.usefixtures("sin_archivo_env")
def test_cargar_settings_valida_lee_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGENES", "https://a.ejemplo.com,https://b.ejemplo.com")
    assert cargar_settings().cors_origenes == ["https://a.ejemplo.com", "https://b.ejemplo.com"]
