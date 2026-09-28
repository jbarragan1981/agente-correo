"""Casos límite de configuración (QA E0.1): entorno real, mensajes sin valores y CORS estricto."""

import base64

import pytest
from pydantic import ValidationError

from app.core.config import ConfiguracionInvalida, Settings, cargar_settings
from tests.soporte import valores_produccion

SECRETO_VISIBLE = "valor-sensible-que-no-debe-salir-en-ningun-mensaje"


@pytest.fixture(autouse=True)
def _sin_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nunca lee el `.env` real durante estas pruebas."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)


def _fijar_entorno(monkeypatch: pytest.MonkeyPatch, valores: dict[str, object]) -> None:
    """Exporta los valores como variables de entorno con nombre en mayúsculas."""
    for nombre, valor in valores.items():
        monkeypatch.setenv(nombre.upper(), str(valor))


@pytest.mark.parametrize("bytes_clave", [0, 1, 16, 24, 31, 33, 64])
def test_produccion_clave_maestra_de_longitud_incorrecta_falla(
    monkeypatch: pytest.MonkeyPatch, bytes_clave: int
) -> None:
    clave = base64.b64encode(b"k" * bytes_clave).decode()
    _fijar_entorno(monkeypatch, valores_produccion(app_master_key=clave))
    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_settings()
    assert [campo for campo, _ in error.value.errores] == ["APP_MASTER_KEY"]


@pytest.mark.parametrize("valor", ["true", "TRUE", "1", "yes", "on"])
def test_produccion_debug_verdadero_en_cualquier_forma_falla(
    monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    _fijar_entorno(monkeypatch, valores_produccion(debug=valor))
    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_settings()
    assert [campo for campo, _ in error.value.errores] == ["DEBUG"]


@pytest.mark.parametrize("entorno", ["PRODUCTION", "Production", "prod", "produccion", ""])
def test_entorno_desconocido_no_cae_a_desarrollo(
    monkeypatch: pytest.MonkeyPatch, entorno: str
) -> None:
    monkeypatch.setenv("ENV", entorno)
    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_settings()
    assert [campo for campo, _ in error.value.errores] == ["ENV"]


@pytest.mark.parametrize("origenes", ["", " ", ",", " , ,"])
def test_produccion_cors_vacio_o_solo_separadores_falla(
    monkeypatch: pytest.MonkeyPatch, origenes: str
) -> None:
    _fijar_entorno(monkeypatch, valores_produccion(cors_origenes=origenes))
    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_settings()
    assert [campo for campo, _ in error.value.errores] == ["CORS_ORIGENES"]


@pytest.mark.parametrize(
    "origenes",
    ["*", "https://*", "https://a.ejemplo.com,*", "https://*.ejemplo.com", "null"],
    ids=["solo", "esquema", "en_lista", "subdominio", "null"],
)
@pytest.mark.parametrize("entorno", ["development", "test", "production"])
def test_cors_comodin_se_rechaza_en_todo_entorno(
    monkeypatch: pytest.MonkeyPatch, entorno: str, origenes: str
) -> None:
    _fijar_entorno(monkeypatch, valores_produccion(env=entorno, cors_origenes=origenes))
    with pytest.raises(ConfiguracionInvalida):
        cargar_settings()


@pytest.mark.parametrize(
    "origen",
    [
        "https://a.ejemplo.com:abc",
        "https://a.ejemplo.com:99999",
        "HTTPS://a.ejemplo.com",
        "https://A.Ejemplo.com",
        "https://usuario@a.ejemplo.com",
        "https://a.ejemplo.com?x=1",
        "https://a.ejemplo.com#f",
        "https://a.ejemplo.com/",
        "ftp://a.ejemplo.com",
        "https://",
    ],
)
def test_cors_origen_mal_formado_o_que_nunca_coincidiria_falla(origen: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **valores_produccion(cors_origenes=origen))


@pytest.mark.parametrize(
    "campo",
    ["app_master_key", "jwt_secret", "database_url", "cors_origenes", "debug"],
)
def test_produccion_mensaje_no_contiene_el_valor_invalido(
    monkeypatch: pytest.MonkeyPatch, campo: str
) -> None:
    invalido = {
        "app_master_key": SECRETO_VISIBLE,
        "jwt_secret": SECRETO_VISIBLE[:20],
        "database_url": f"mysql://usuario:{SECRETO_VISIBLE}@bd.ejemplo/x",
        "cors_origenes": f"http://{SECRETO_VISIBLE}.ejemplo.com",
        "debug": SECRETO_VISIBLE,
    }[campo]
    _fijar_entorno(monkeypatch, valores_produccion(**{campo: invalido}))
    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_settings()
    texto = f"{error.value!s} {error.value!r} {error.value.errores} {error.value.__cause__}"
    assert (SECRETO_VISIBLE[:20] in texto, campo.upper() in texto) == (False, True)


def test_produccion_todo_invalido_nombra_todos_los_campos_sin_valores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fijar_entorno(
        monkeypatch,
        {"env": "production", "debug": "true", "jwt_secret": SECRETO_VISIBLE[:5]},
    )
    with pytest.raises(ConfiguracionInvalida) as error:
        cargar_settings()
    campos = {campo for campo, _ in error.value.errores}
    assert (campos, SECRETO_VISIBLE[:5] in str(error.value)) == (
        {"DEBUG", "DATABASE_URL", "APP_MASTER_KEY", "JWT_SECRET", "CORS_ORIGENES"},
        False,
    )


def test_desarrollo_con_debug_verdadero_es_valido_y_no_cambia_el_entorno() -> None:
    settings = Settings(_env_file=None, env="development", debug=True)
    assert (settings.debug, settings.es_produccion) == (True, False)


def test_jwt_secret_cuenta_bytes_utf8_no_caracteres() -> None:
    # 16 caracteres de 2 bytes = 32 bytes: válido; 15 caracteres = 30 bytes: inválido.
    assert Settings(_env_file=None, jwt_secret="ñ" * 16).jwt_secret is not None
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret="ñ" * 15)
