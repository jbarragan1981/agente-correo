"""Orquestación del bootstrap: espera, base, lock, migraciones, LangGraph, privilegios, semillas.

Idempotente y seguro ante procesos concurrentes (advisory lock). Nunca registra URLs, usuarios
ni contraseñas de la BD; la contraseña generada del admin solo sale por `AvisoOperadorPort`.
"""

import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import MappingProxyType

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.ports.avisos import AvisoOperadorPort
from app.application.use_cases.crear_admin_inicial import (
    AdminSinEmail,
    CrearAdminInicial,
    ResultadoAdminInicial,
)
from app.core.config import Settings
from app.core.logging import obtener_logger
from app.domain.auditoria import ActorTipo, EntradaAuditoria
from app.domain.catalogo_inicial import catalogo_inicial
from app.infrastructure.db.bootstrap.bloqueo import bloqueo_bootstrap
from app.infrastructure.db.bootstrap.creacion import asegurar_base
from app.infrastructure.db.bootstrap.errores import (
    AdminSinEmailEnProduccion,
    ErrorBootstrap,
    FalloEnPaso,
    FaltaUrlMigrador,
)
from app.infrastructure.db.bootstrap.espera import esperar_postgres
from app.infrastructure.db.bootstrap.langgraph import preparar_checkpointer
from app.infrastructure.db.bootstrap.migraciones import aplicar_migraciones, revision_actual
from app.infrastructure.db.bootstrap.privilegios import verificar_privilegios
from app.infrastructure.db.bootstrap.urls import nombre_base, url_psycopg
from app.infrastructure.db.repositorios.auditoria import RepositorioAuditoriaSql
from app.infrastructure.db.repositorios.usuarios import RepositorioUsuariosSql
from app.infrastructure.db.semillas import sembrar_catalogo
from app.infrastructure.seguridad.argon2 import GeneradorContrasenaSecrets, HasherArgon2

_log = obtener_logger(__name__)


@dataclass(frozen=True)
class ResultadoBootstrap:
    """Resumen de una ejecución del bootstrap (sin secretos)."""

    revision_inicial: str | None
    revision_final: str
    insertadas: Mapping[str, int]
    admin_creado: bool


def _ms_desde(inicio: float) -> int:
    """Milisegundos transcurridos."""
    return round((time.perf_counter() - inicio) * 1000)


@asynccontextmanager
async def paso(nombre: str) -> AsyncIterator[None]:
    """Mide el paso, emite `bootstrap.paso` y envuelve errores inesperados con su nombre."""
    inicio = time.perf_counter()
    try:
        yield
    except ErrorBootstrap:
        _log.info("bootstrap.paso", paso=nombre, duracion_ms=_ms_desde(inicio), resultado="error")
        raise
    except Exception as exc:
        _log.info("bootstrap.paso", paso=nombre, duracion_ms=_ms_desde(inicio), resultado="error")
        sqlstate = getattr(exc, "sqlstate", None) or getattr(
            getattr(exc, "orig", None), "sqlstate", None
        )
        raise FalloEnPaso(nombre, type(exc).__name__, sqlstate) from exc
    _log.info("bootstrap.paso", paso=nombre, duracion_ms=_ms_desde(inicio), resultado="ok")


def urls_bootstrap(settings: Settings) -> tuple[URL, URL]:
    """(URL del migrador, URL de la app) con driver psycopg; exige el migrador si hay roles."""
    if settings.db_roles_separados and settings.database_url_migrador is None:
        raise FaltaUrlMigrador
    return (
        url_psycopg(settings.url_base_datos_migrador()),
        url_psycopg(settings.url_base_datos()),
    )


async def registrar_auditoria_bootstrap(
    auditoria: RepositorioAuditoriaSql,
    inicial: str | None,
    final: str,
    insertadas: Mapping[str, int],
) -> None:
    """Deja `bd.migrada` y `bd.semillas_aplicadas` solo si hubo cambios."""
    if inicial != final:
        await auditoria.registrar(
            EntradaAuditoria(
                ActorTipo.SISTEMA, "bd.migrada", detalle={"desde": inicial, "hasta": final}
            )
        )
    con_filas = {tabla: n for tabla, n in insertadas.items() if n > 0}
    if con_filas:
        await auditoria.registrar(
            EntradaAuditoria(
                ActorTipo.SISTEMA, "bd.semillas_aplicadas", detalle={"insertadas": con_filas}
            )
        )


async def _crear_admin(conexion: AsyncConnection, settings: Settings) -> ResultadoAdminInicial:
    """Ejecuta el caso de uso del admin inicial con los adaptadores SQL."""
    contrasena = settings.admin_initial_password
    caso_de_uso = CrearAdminInicial(
        RepositorioUsuariosSql(conexion),
        HasherArgon2(),
        GeneradorContrasenaSecrets(),
        RepositorioAuditoriaSql(conexion),
    )
    try:
        return await caso_de_uso.ejecutar(
            email=settings.admin_initial_email,
            contrasena=None if contrasena is None else contrasena.get_secret_value(),
            es_produccion=settings.es_produccion,
        )
    except AdminSinEmail:
        raise AdminSinEmailEnProduccion from None


async def _sembrar(
    motor: AsyncEngine, settings: Settings, inicial: str | None, final: str
) -> tuple[dict[str, int], ResultadoAdminInicial]:
    """Semillas, admin y auditoría en una sola transacción."""
    async with motor.begin() as conexion:
        insertadas = await sembrar_catalogo(conexion, catalogo_inicial())
        admin = await _crear_admin(conexion, settings)
        await registrar_auditoria_bootstrap(
            RepositorioAuditoriaSql(conexion), inicial, final, insertadas
        )
    return insertadas, admin


async def _pasos_bloqueados(
    motor: AsyncEngine, settings: Settings, url_migrador: URL, url_app: URL
) -> tuple[ResultadoBootstrap, ResultadoAdminInicial]:
    """Pasos que requieren el advisory lock."""
    async with paso("migraciones"):
        inicial = await revision_actual(motor)
        final = await aplicar_migraciones(motor)
    async with paso("langgraph"):
        await preparar_checkpointer(url_migrador)
    if settings.db_roles_separados:
        async with paso("privilegios"):
            await verificar_privilegios(motor, url_app)
    else:
        _log.warning("bd.rol_unico")
    async with paso("semillas"):
        insertadas, admin = await _sembrar(motor, settings, inicial, final)
    resultado = ResultadoBootstrap(inicial, final, MappingProxyType(insertadas), admin.creado)
    return resultado, admin


async def ejecutar_bootstrap(settings: Settings, avisos: AvisoOperadorPort) -> ResultadoBootstrap:
    """Ejecuta todos los pasos; la contraseña generada se muestra tras el COMMIT."""
    inicio = time.perf_counter()
    _log.info("bootstrap.inicio")
    async with paso("configuracion"):
        url_migrador, url_app = urls_bootstrap(settings)
        nombre = nombre_base(url_migrador)
    async with paso("espera"):
        estado = await esperar_postgres(url_migrador, max_s=settings.db_espera_max_s)
    async with paso("creacion"):
        if not estado.base_existe:
            await asegurar_base(url_migrador, nombre, crear=settings.db_auto_create)
    motor = create_async_engine(url_migrador, poolclass=NullPool)
    try:
        async with bloqueo_bootstrap(motor, timeout_s=settings.db_bootstrap_lock_timeout_s):
            resultado, admin = await _pasos_bloqueados(motor, settings, url_migrador, url_app)
    finally:
        await motor.dispose()
    if admin.creado:
        _log.info(
            "bootstrap.admin_inicial_creado",
            email=admin.email_enmascarado,
            generada_aleatoriamente=admin.contrasena_generada is not None,
        )
    if admin.contrasena_generada is not None and admin.email_enmascarado is not None:
        avisos.mostrar_contrasena_inicial(admin.email_enmascarado, admin.contrasena_generada)
    _log.info(
        "bootstrap.completado",
        duracion_ms=_ms_desde(inicio),
        revision=resultado.revision_final,
        insertadas=dict(resultado.insertadas),
    )
    return resultado
