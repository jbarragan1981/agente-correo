"""Pruebas del procesador `redactar` y de la salida JSON (CA12)."""

import base64
import json
import logging
from collections.abc import Callable
from typing import Any

import pytest
import structlog
from pydantic import SecretStr

from app.core.logging import (
    CLAVES_SENSIBLES,
    LONGITUD_MAXIMA,
    LONGITUD_MAXIMA_TRAZA,
    REDACTADO,
    SECRETO_ENMASCARADO,
    configurar_logging,
    obtener_logger,
    redactar,
    redactar_texto,
    redactar_traza,
)

LeerLogs = Callable[[], list[dict[str, Any]]]


def _b64(texto: str) -> str:
    """Base64 URL sin relleno, como en un JWT."""
    return base64.urlsafe_b64encode(texto.encode()).decode().rstrip("=")


JWT_PRUEBA = ".".join(
    [_b64('{"alg":"HS256","typ":"JWT"}'), _b64('{"sub":"usuario-de-prueba"}'), "firma" * 5]
)
CLAVE_ANTHROPIC_PRUEBA = "sk-ant-" + "x" * 24
CLAVE_OPENAI_PRUEBA = "sk-" + "y" * 24
CLAVE_TYPESAFE_PRUEBA = "ts_" + "z" * 16
DSN_PRUEBA = "postgresql+asyncpg://usuario:" + "clave-marcador" + "@bd.ejemplo/agente"


def _lanzar(mensaje: str) -> None:
    """Lanza un RuntimeError con el mensaje dado."""
    raise RuntimeError(mensaje)


def _procesar(evento: dict[str, Any]) -> dict[str, Any]:
    """Aplica `redactar` a una copia del evento."""
    return dict(redactar(None, "info", dict(evento)))


@pytest.mark.parametrize("clave", CLAVES_SENSIBLES)
def test_redactar_clave_sensible_oculta_el_valor(clave: str) -> None:
    assert _procesar({"event": "x", clave: "valor-marcador"})[clave] == REDACTADO


def test_redactar_clave_sensible_sin_distinguir_mayusculas() -> None:
    assert _procesar({"event": "x", "X-Api-Key-Header": "valor"})["X-Api-Key-Header"] == REDACTADO


def test_redactar_clave_anidada_en_dict_y_lista() -> None:
    evento = _procesar({"event": "x", "datos": {"cuentas": [{"password": "valor-marcador"}]}})
    assert "valor-marcador" not in json.dumps(evento)


@pytest.mark.parametrize(
    "secreto",
    [
        f"Bearer {JWT_PRUEBA}",
        JWT_PRUEBA,
        CLAVE_ANTHROPIC_PRUEBA,
        CLAVE_OPENAI_PRUEBA,
        CLAVE_TYPESAFE_PRUEBA,
    ],
    ids=["bearer", "jwt", "sk_ant", "sk", "ts"],
)
def test_redactar_patron_de_token_en_evento(secreto: str) -> None:
    evento = _procesar({"event": f"llamada con {secreto} fallida"})
    assert secreto not in evento["event"]


def test_redactar_dsn_con_contrasena_conserva_usuario_y_host() -> None:
    assert redactar_texto(DSN_PRUEBA) == "postgresql+asyncpg://usuario:***@bd.ejemplo/agente"


def test_redactar_parametro_sensible_en_query() -> None:
    assert "valor-marcador" not in redactar_texto("GET /ruta?token=valor-marcador&x=1")


def test_redactar_email_deja_inicial_y_dominio() -> None:
    assert redactar_texto("de juan.perez@dominio.com") == "de j***@dominio.com"


def test_redactar_secretstr_se_enmascara() -> None:
    assert _procesar({"event": "x", "valor": SecretStr("oculto")})["valor"] == SECRETO_ENMASCARADO


def test_redactar_texto_largo_se_trunca() -> None:
    resultado = redactar_texto("a" * (LONGITUD_MAXIMA + 50))
    assert resultado == "a" * LONGITUD_MAXIMA + "…[truncado]"


def test_redactar_traza_larga_conserva_el_final() -> None:
    traza = "x" * (LONGITUD_MAXIMA_TRAZA + 10) + "RuntimeError: final"
    assert redactar_traza(traza).endswith("RuntimeError: final")


def test_redactar_profundidad_excesiva_se_corta() -> None:
    anidado: dict[str, Any] = {"hoja": "valor-profundo"}
    for _ in range(12):
        anidado = {"nivel": anidado}
    assert "valor-profundo" not in json.dumps(_procesar({"event": "x", "datos": anidado}))


def test_redactar_objeto_desconocido_se_convierte_y_redacta() -> None:
    class Objeto:
        def __str__(self) -> str:
            return f"objeto con {CLAVE_ANTHROPIC_PRUEBA}"

    assert CLAVE_ANTHROPIC_PRUEBA not in str(_procesar({"event": "x", "obj": Objeto()})["obj"])


def test_log_linea_es_json_con_campos_base(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    obtener_logger("prueba").info("evento.prueba")
    linea = capturar_logs()[-1]
    assert {"timestamp", "nivel", "evento"} <= linea.keys()


def test_log_incluye_correlation_id_de_contextvars(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    with structlog.contextvars.bound_contextvars(correlation_id="id-de-prueba"):
        obtener_logger("prueba").info("evento.prueba")
    assert capturar_logs()[-1]["correlation_id"] == "id-de-prueba"


def test_log_excepcion_redacta_la_traza(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    try:
        _lanzar(f"conexión {DSN_PRUEBA} con {CLAVE_ANTHROPIC_PRUEBA}")
    except RuntimeError:
        obtener_logger("prueba").exception("evento.fallo")
    salida = json.dumps(capturar_logs())
    assert "clave-marcador" not in salida
    assert CLAVE_ANTHROPIC_PRUEBA not in salida


def test_log_uvicorn_error_sale_como_json_redactado(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    logging.getLogger("uvicorn.error").error("fallo con %s", f"Bearer {JWT_PRUEBA}")
    linea = capturar_logs()[-1]
    assert (linea["logger"], JWT_PRUEBA in linea["evento"]) == ("uvicorn.error", False)


def test_log_uvicorn_access_esta_silenciado(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    logging.getLogger("uvicorn.access").info("GET /ruta?token=valor-marcador")
    assert capturar_logs() == []


def test_log_extra_de_libreria_estandar_aparece_como_campo(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    logging.getLogger("app.prueba").warning("evento.extra", extra={"sonda": "base_datos"})
    assert capturar_logs()[-1]["sonda"] == "base_datos"


def test_configurar_logging_dos_veces_no_duplica_lineas(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    configurar_logging("INFO")
    obtener_logger("prueba").info("evento.unico")
    assert len(capturar_logs()) == 1


def test_log_quita_color_message_de_uvicorn(capturar_logs: LeerLogs) -> None:
    configurar_logging("INFO")
    logging.getLogger("uvicorn.error").info("arranque", extra={"color_message": "\x1b[36marranque"})
    assert "color_message" not in capturar_logs()[-1]
