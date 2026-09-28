"""Casos límite de redacción de logs (QA E0.1)."""

import base64
import json
from typing import Any

import pytest
from pydantic import SecretStr

from app.core.logging import REDACTADO, redactar


def _jwt() -> str:
    """JWT sintético armado en tiempo de ejecución."""

    def parte(datos: dict[str, str]) -> str:
        return base64.urlsafe_b64encode(json.dumps(datos).encode()).decode().rstrip("=")

    return f"{parte({'alg': 'none'})}.{parte({'sub': 'prueba'})}.firma"


def _limpiar(**campos: Any) -> dict[str, Any]:
    return dict(redactar(None, "info", dict(campos)))


@pytest.mark.parametrize(
    "clave",
    ["x-api-key", "X-API-KEY", "Set-Cookie", "proxy-authorization", "refresh_token", "Password2"],
)
def test_redactar_variantes_de_clave_con_guiones_y_mayusculas(clave: str) -> None:
    assert _limpiar(**{clave: "valor-secreto"})[clave] == REDACTADO


def test_redactar_cabeceras_anidadas_en_lista_de_tuplas_de_dicts() -> None:
    evento = _limpiar(peticion=({"cabeceras": [{"Authorization": "Basic abc"}]},))
    assert evento["peticion"] == [{"cabeceras": [{"Authorization": REDACTADO}]}]


def test_redactar_claves_no_string_no_rompen() -> None:
    assert _limpiar(mapa={1: "a", None: "b"})["mapa"] == {1: "a", None: "b"}


def test_redactar_bytes_pasan_por_los_patrones() -> None:
    assert "sk-" + "b" * 30 not in _limpiar(cuerpo=("sk-" + "b" * 30).encode())["cuerpo"]


def test_redactar_jwt_incrustado_en_texto_largo() -> None:
    jwt = _jwt()
    assert jwt not in _limpiar(evento_texto=f"antes {jwt} despues")["evento_texto"]


def test_redactar_secretstr_dentro_de_estructura() -> None:
    assert _limpiar(datos=[{"v": SecretStr("valor-oculto")}])["datos"] == [{"v": "**********"}]


def test_redactar_dsn_con_contrasena_que_contiene_arroba_no_deja_resto_visible() -> None:
    texto = _limpiar(e="postgresql://u:pa@ss-secreta@host/db")["e"]
    assert "secreta" not in texto


def test_redactar_query_con_token_en_url_completa() -> None:
    texto = _limpiar(url="https://h.ejemplo/x?a=1&access_token=valor-x&sig=otro-y")["url"]
    assert ("valor-x" in texto, "otro-y" in texto, "a=1" in texto) == (False, False, True)


def test_redactar_email_en_mayusculas_y_con_subdominios() -> None:
    assert _limpiar(e="ANA.Lopez@Mail.Corp.Ejemplo.com")["e"] == "A***@Mail.Corp.Ejemplo.com"


def test_redactar_no_altera_numeros_booleanos_ni_none() -> None:
    assert _limpiar(a=1, b=1.5, c=True, d=None) == {"a": 1, "b": 1.5, "c": True, "d": None}


def test_redactar_valor_con_secreto_en_repr_de_objeto_desconocido() -> None:
    class Rara:
        def __repr__(self) -> str:
            return "Rara(token_visible=Bearer abc123def)"

        __str__ = __repr__

    assert "abc123def" not in _limpiar(obj=Rara())["obj"]
