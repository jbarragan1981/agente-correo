"""Pruebas API del log de acceso propio (CA12, CA13, R13)."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx

LeerLogs = Callable[[], list[dict[str, Any]]]
VALOR_MARCADOR = "valor-marcador-query"


def _accesos(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filtra los eventos de acceso HTTP."""
    return [log for log in logs if log.get("evento") == "http.peticion"]


async def test_logs_acceso_registra_campos_sin_query(
    cliente_api: httpx.AsyncClient, capturar_logs: LeerLogs
) -> None:
    respuesta = await cliente_api.get(f"/api/v1/salud?token={VALOR_MARCADOR}")
    acceso = _accesos(capturar_logs())[-1]
    assert (
        acceso["metodo"],
        acceso["ruta"],
        acceso["estado"],
        isinstance(acceso["duracion_ms"], float | int),
        acceso["correlation_id"],
    ) == ("GET", "/api/v1/salud", 200, True, respuesta.headers["x-request-id"])


async def test_logs_acceso_no_contiene_la_query_string(
    cliente_api: httpx.AsyncClient, capturar_logs: LeerLogs
) -> None:
    await cliente_api.get(f"/api/v1/salud?token={VALOR_MARCADOR}")
    assert VALOR_MARCADOR not in json.dumps(capturar_logs())


async def test_logs_toda_linea_es_json_con_campos_base(
    cliente_api: httpx.AsyncClient, capturar_logs: LeerLogs
) -> None:
    await cliente_api.get("/api/v1/salud/listo")
    logs = capturar_logs()
    completas = [log for log in logs if {"timestamp", "nivel", "evento"} <= log.keys()]
    assert (len(logs) > 0, completas) == (True, logs)


async def test_logs_peticiones_concurrentes_no_mezclan_correlation_id(
    cliente_api: httpx.AsyncClient, capturar_logs: LeerLogs
) -> None:
    respuestas = await asyncio.gather(*(cliente_api.get("/api/v1/salud/listo") for _ in range(5)))
    enviados = {respuesta.headers["x-request-id"] for respuesta in respuestas}
    registrados = {acceso["correlation_id"] for acceso in _accesos(capturar_logs())}
    assert (len(enviados), registrados) == (5, enviados)
