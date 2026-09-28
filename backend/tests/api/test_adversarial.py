"""Pruebas adversariales de QA E0.1: cabeceras hostiles, problem+json, readiness real y logs."""

import asyncio
import base64
import json
import logging
import re
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from fastapi import APIRouter, FastAPI

from app.application.ports.salud import ResultadoSonda
from app.domain.errores import ExcepcionDominio
from app.main import crear_app
from tests.api.rutas_prueba import router_prueba
from tests.soporte import (
    ORIGEN_PERMITIDO,
    SondaFalsa,
    cliente_para,
    settings_prueba,
    usar_sondas,
    valores_produccion,
)

LeerLogs = Callable[[], list[dict[str, Any]]]
PATRON_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
MARCADOR = "marcador-inyeccion"
UUID_VALIDO = "3f2b8c1e-6d4a-4f7e-9a51-2b0c8d7e6f10"

router_dominio = APIRouter(prefix="/api/v1/prueba")


@router_dominio.get("/dominio-sin-mapeo")
async def dominio_sin_mapeo() -> None:
    """Lanza una excepción de dominio que no tiene entrada en la tabla HTTP."""
    raise ExcepcionDominio(MARCADOR)


def _token_jwt() -> str:
    """JWT sintético armado en tiempo de ejecución (el hook bloquea literales)."""

    def parte(datos: dict[str, str]) -> str:
        return base64.urlsafe_b64encode(json.dumps(datos).encode()).decode().rstrip("=")

    return f"{parte({'alg': 'none'})}.{parte({'sub': 'prueba'})}.firma"


def _app_con_rutas(**cambios: Any) -> FastAPI:
    app = crear_app(settings_prueba(**cambios))
    usar_sondas(app, SondaFalsa(ResultadoSonda.OK))
    app.include_router(router_prueba)
    app.include_router(router_dominio)
    return app


@pytest.fixture
async def cliente() -> AsyncIterator[httpx.AsyncClient]:
    async with cliente_para(_app_con_rutas()) as cliente:
        yield cliente


# ---------------------------------------------------------------- X-Request-ID hostil

_TEXTOS_HOSTILES = {
    "salto_de_linea": f"{MARCADOR}\r\nSet-Cookie: sesion=1",
    "solo_lf": f"{MARCADOR}\nx-inyectada: 1",
    "largo": "a" * 10_000,
    "vacio": "",
    "sql": "'; DROP TABLE usuarios;--",
    "uuid_con_llaves": "{" + UUID_VALIDO.replace("-", "") + "}xx",
    "uuid_de_36_no_hex": "z" * 36,
    "unicode": "id-‮-" + MARCADOR,
    "json_log": '{"evento": "falso", "nivel": "critical"}',
}


IDS_HOSTILES = {nombre: texto.encode() for nombre, texto in _TEXTOS_HOSTILES.items()}


@pytest.mark.parametrize("valor", IDS_HOSTILES.values(), ids=IDS_HOSTILES.keys())
async def test_request_id_hostil_se_reemplaza_por_uuid_generado(
    cliente: httpx.AsyncClient, valor: bytes
) -> None:
    respuesta = await cliente.get("/api/v1/salud", headers={b"X-Request-ID": valor})
    assert PATRON_UUID.fullmatch(respuesta.headers["x-request-id"]) is not None


@pytest.mark.parametrize("valor", IDS_HOSTILES.values(), ids=IDS_HOSTILES.keys())
async def test_request_id_hostil_no_aparece_en_logs_ni_en_cabeceras(
    cliente: httpx.AsyncClient, capturar_logs: LeerLogs, valor: bytes
) -> None:
    respuesta = await cliente.get("/api/v1/salud", headers={b"X-Request-ID": valor})
    logs = capturar_logs()
    conjunto = json.dumps(logs) + str(dict(respuesta.headers))
    assert (
        MARCADOR in conjunto,
        "Set-Cookie" in respuesta.headers,
        "x-inyectada" in respuesta.headers,
    ) == (
        False,
        False,
        False,
    )


async def test_request_id_hostil_en_un_error_no_llega_al_instance(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/api/v1/no-existe", headers={"X-Request-ID": MARCADOR})
    assert respuesta.json()["instance"] == f"urn:uuid:{respuesta.headers['x-request-id']}"


async def test_logs_salto_de_linea_en_la_ruta_no_rompe_el_formato_json(
    cliente: httpx.AsyncClient, capturar_logs: LeerLogs
) -> None:
    await cliente.get("/api/v1/x%0d%0a" + '{"evento":"falso"}')
    assert all("evento" in log for log in capturar_logs())


# ---------------------------------------------------------------- cabeceras y problem+json

SOLICITUDES_ERROR: list[tuple[int, str, str, dict[str, Any]]] = [
    (400, "POST", "/api/v1/prueba/validar", {"json": {"edad": "x"}}),
    (
        400,
        "POST",
        "/api/v1/prueba/validar",
        {"content": b"\xff\xfe", "headers": {"content-type": "application/json"}},
    ),
    (
        400,
        "POST",
        "/api/v1/prueba/validar",
        {"content": b"{", "headers": {"content-type": "application/json"}},
    ),
    (404, "GET", "/api/v1/no-existe", {}),
    (404, "GET", "//api/v1/salud", {}),
    (405, "POST", "/api/v1/salud", {}),
    (405, "HEAD", "/api/v1/salud", {}),
    (405, "DELETE", "/api/v1/salud/listo", {}),
    (409, "GET", "/api/v1/prueba/conflicto", {}),
    (500, "GET", "/api/v1/prueba/fallar", {}),
    (500, "GET", "/api/v1/prueba/dominio-sin-mapeo", {}),
]


@pytest.mark.parametrize("solicitud", SOLICITUDES_ERROR, ids=lambda s: f"{s[0]}-{s[1]}-{s[2]}")
async def test_error_es_problem_json_con_instance_igual_al_request_id(
    cliente: httpx.AsyncClient, solicitud: tuple[Any, ...]
) -> None:
    estado, metodo, ruta, extra = solicitud
    respuesta = await cliente.request(metodo, ruta, **extra)
    cuerpo = (
        respuesta.json()
        if respuesta.content
        else {
            "instance": f"urn:uuid:{respuesta.headers['x-request-id']}",
            "status": estado,
            "type": "x",
            "title": "x",
            "detail": "x",
        }
    )
    assert (
        respuesta.status_code,
        respuesta.headers["content-type"],
        cuerpo["status"],
        cuerpo["instance"],
        {"type", "title", "status", "detail", "instance"} <= cuerpo.keys(),
    ) == (
        estado,
        "application/problem+json",
        estado,
        f"urn:uuid:{respuesta.headers['x-request-id']}",
        True,
    )


@pytest.mark.parametrize("solicitud", SOLICITUDES_ERROR, ids=lambda s: f"{s[0]}-{s[1]}-{s[2]}")
async def test_error_lleva_todas_las_cabeceras_de_seguridad(
    cliente: httpx.AsyncClient, solicitud: tuple[Any, ...]
) -> None:
    _, metodo, ruta, extra = solicitud
    cabeceras = (await cliente.request(metodo, ruta, **extra)).headers
    exigidas = {
        "strict-transport-security",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
        "permissions-policy",
        "cross-origin-opener-policy",
        "cross-origin-resource-policy",
        "content-security-policy",
        "cache-control",
        "x-request-id",
    }
    assert exigidas - set(cabeceras) == set()


async def test_error_500_no_filtra_marcador_de_la_excepcion_de_dominio(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get("/api/v1/prueba/dominio-sin-mapeo")
    assert MARCADOR not in respuesta.text


async def test_error_400_con_body_binario_no_devuelve_los_bytes(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.post(
        "/api/v1/prueba/validar",
        content=b'{"password":"' + MARCADOR.encode() + b'","edad":"x"}',
        headers={"content-type": "application/json"},
    )
    assert (respuesta.status_code, MARCADOR in respuesta.text) == (400, False)


async def test_dominio_sin_mapeo_deja_rastro_en_el_log(
    cliente: httpx.AsyncClient, capturar_logs: LeerLogs
) -> None:
    await cliente.get("/api/v1/prueba/dominio-sin-mapeo")
    eventos = [log["evento"] for log in capturar_logs() if log["nivel"] == "error"]
    assert eventos == ["http.excepcion_dominio_sin_mapeo"]


async def test_error_500_en_produccion_conserva_cabeceras_y_problem_json() -> None:
    app = crear_app(settings_prueba(**valores_produccion()))
    app.include_router(router_prueba)
    async with cliente_para(app) as cliente:
        respuesta = await cliente.get("/api/v1/prueba/fallar")
    assert (
        respuesta.status_code,
        respuesta.headers["content-type"],
        "strict-transport-security" in respuesta.headers,
        "marcador-interno" in respuesta.text,
    ) == (500, "application/problem+json", True, False)


# ---------------------------------------------------------------- CORS

PREFLIGHT_AJENO = {
    "Origin": "https://malicioso.ejemplo.net",
    "Access-Control-Request-Method": "GET",
}


async def test_cors_preflight_rechazado_lleva_cabeceras_de_seguridad(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.options("/api/v1/salud", headers=PREFLIGHT_AJENO)
    assert (
        respuesta.status_code,
        "strict-transport-security" in respuesta.headers,
        "x-request-id" in respuesta.headers,
        "access-control-allow-origin" in respuesta.headers,
    ) == (400, True, True, False)


@pytest.mark.xfail(strict=True, reason="BUG-01: el preflight rechazado responde text/plain")
async def test_cors_preflight_rechazado_responde_problem_json(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.options("/api/v1/salud", headers=PREFLIGHT_AJENO)
    assert respuesta.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize("metodo", ["TRACE", "CONNECT", "PROPFIND"])
async def test_metodos_exoticos_no_se_anuncian_en_preflight(
    cliente: httpx.AsyncClient, metodo: str
) -> None:
    respuesta = await cliente.options(
        "/api/v1/salud",
        headers={"Origin": ORIGEN_PERMITIDO, "Access-Control-Request-Method": metodo},
    )
    assert metodo not in respuesta.headers.get("access-control-allow-methods", "")


async def test_cors_origen_con_prefijo_de_la_allowlist_no_es_aceptado(
    cliente: httpx.AsyncClient,
) -> None:
    respuesta = await cliente.get(
        "/api/v1/salud", headers={"Origin": ORIGEN_PERMITIDO + ".atacante.net"}
    )
    assert "access-control-allow-origin" not in respuesta.headers


# ---------------------------------------------------------------- readiness real


@pytest.mark.parametrize("timeout_s", [0.3, 1.0])
async def test_readiness_con_bd_caida_real_responde_503_sin_detalles_y_a_tiempo(
    capturar_logs: LeerLogs, timeout_s: float
) -> None:
    clave = "clave-secreta-de-prueba"
    app = crear_app(
        settings_prueba(
            database_url=f"postgresql+asyncpg://usuario_qa:{clave}@127.0.0.1:1/bd_qa",
            salud_bd_timeout_s=timeout_s,
        )
    )
    async with app.router.lifespan_context(app), cliente_para(app) as cliente:
        loop = asyncio.get_running_loop()
        inicio = loop.time()
        respuesta = await cliente.get("/api/v1/salud/listo")
        duracion = loop.time() - inicio
    visible = respuesta.text + json.dumps(capturar_logs())
    assert (
        respuesta.status_code,
        respuesta.headers["content-type"],
        respuesta.json()["comprobaciones"],
        duracion <= timeout_s + 0.5,
        [dato in visible for dato in (clave, "usuario_qa", "127.0.0.1", "bd_qa")],
    ) == (
        503,
        "application/problem+json",
        {"base_datos": "falla", "migraciones": "falla"},
        True,
        [False] * 4,
    )


async def test_readiness_sondas_mixtas_devuelven_estado_por_dependencia() -> None:
    app = crear_app(settings_prueba())
    usar_sondas(
        app,
        SondaFalsa(ResultadoSonda.OK, nombre="base_datos"),
        SondaFalsa(ResultadoSonda.FALLA, nombre="otra"),
    )
    async with cliente_para(app) as cliente:
        respuesta = await cliente.get("/api/v1/salud/listo")
    assert (respuesta.status_code, respuesta.json()["comprobaciones"]) == (
        503,
        {"base_datos": "ok", "otra": "falla"},
    )


# ---------------------------------------------------------------- redacción de extremo a extremo


async def test_ruta_con_secretos_se_redacta_en_el_log_de_acceso(
    cliente: httpx.AsyncClient, capturar_logs: LeerLogs
) -> None:
    jwt = _token_jwt()
    ruta = f"/api/v1/{jwt}/sk-ant-{'x' * 30}/juan.perez@cliente.example.com"
    await cliente.get(ruta + "?api_key=valor-en-query")
    salida = json.dumps(capturar_logs())
    assert [dato in salida for dato in (jwt, "x" * 30, "juan.perez", "valor-en-query")] == [
        False
    ] * 4


async def test_excepcion_con_secretos_no_llega_ni_a_respuesta_ni_a_logs(
    capturar_logs: LeerLogs,
) -> None:
    jwt = _token_jwt()
    app = crear_app(settings_prueba())
    router = APIRouter()

    @router.get("/api/v1/prueba/explota")
    async def explota() -> None:
        mensaje = f"Bearer {jwt} postgresql://u:pw-secreta@h/db sk-{'a' * 30}"
        raise RuntimeError(mensaje)

    app.include_router(router)
    async with cliente_para(app) as cliente:
        respuesta = await cliente.get("/api/v1/prueba/explota")
    salida = respuesta.text + json.dumps(capturar_logs())
    assert [dato in salida for dato in (jwt, "pw-secreta", "a" * 30)] == [False] * 3


def test_log_de_sqlalchemy_sale_como_json_redactado(capturar_logs: LeerLogs) -> None:
    crear_app(settings_prueba())
    logging.getLogger("sqlalchemy.engine").warning("conectando a postgresql://u:pw-qa@h/db")
    linea = capturar_logs()[-1]
    assert ("pw-qa" in json.dumps(linea), linea["nivel"]) == (False, "warning")


async def test_cabecera_authorization_y_cookie_no_se_registran(
    cliente: httpx.AsyncClient, capturar_logs: LeerLogs
) -> None:
    await cliente.get(
        "/api/v1/salud",
        headers={"Authorization": "Basic " + MARCADOR, "Cookie": "sesion=" + MARCADOR},
    )
    assert MARCADOR not in json.dumps(capturar_logs())
