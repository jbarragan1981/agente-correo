"""Siembra idempotente del catálogo inicial (`INSERT ... ON CONFLICT DO NOTHING`)."""

import uuid
from collections.abc import Mapping, Sequence
from importlib import resources
from typing import Any, Final

from sqlalchemy import Table, and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.ids import nuevo_id
from app.domain.agentes.preguntas import preguntas_como_json
from app.domain.catalogo_inicial import AgenteInicial, CatalogoInicial
from app.infrastructure.db.modelos.agentes import Agente, VersionPrompt
from app.infrastructure.db.modelos.configuracion import Configuracion
from app.infrastructure.db.modelos.identidad import Rol
from app.infrastructure.db.modelos.proveedores import ProveedorIa
from app.infrastructure.db.modelos.taxonomia import Categoria, Taxonomia

PAQUETE_PROMPTS: Final = "app.agents.prompts"
NUMERO_VERSION_INICIAL: Final = 1


def leer_prompt(archivo: str) -> str:
    """Texto del prompt empaquetado en `app/agents/prompts/`."""
    return resources.files(PAQUETE_PROMPTS).joinpath(archivo).read_text(encoding="utf-8")


async def _insertar(
    conexion: AsyncConnection,
    tabla: Table,
    filas: Sequence[Mapping[str, Any]],
    conflicto: Sequence[str],
) -> int:
    """Inserta ignorando conflictos y devuelve cuántas filas entraron."""
    if not filas:
        return 0
    sentencia = (
        insert(tabla)
        .values([dict(fila) for fila in filas])
        .on_conflict_do_nothing(index_elements=list(conflicto))
        .returning(tabla.c[conflicto[0]])
    )
    return len((await conexion.execute(sentencia)).all())


async def _ids_por(
    conexion: AsyncConnection, columna_id: Any, columna_clave: Any
) -> dict[str, uuid.UUID]:
    """Mapa clave → id de una tabla."""
    filas = (await conexion.execute(select(columna_clave, columna_id))).all()
    return {str(clave): identificador for clave, identificador in filas}


def _tabla(modelo: Any) -> Table:
    """Tabla de un modelo declarativo."""
    tabla: Table = modelo.__table__
    return tabla


async def _sembrar_taxonomia(
    conexion: AsyncConnection, catalogo: CatalogoInicial
) -> dict[str, int]:
    """Taxonomía base y sus categorías."""
    taxonomia = catalogo.taxonomia
    insertadas = {
        "taxonomias": await _insertar(
            conexion,
            _tabla(Taxonomia),
            [{"id": nuevo_id(), "nombre": taxonomia.nombre, "descripcion": taxonomia.descripcion}],
            ["nombre"],
        )
    }
    taxonomia_id = (
        await conexion.execute(select(Taxonomia.id).where(Taxonomia.nombre == taxonomia.nombre))
    ).scalar_one()
    filas = [
        {
            "id": nuevo_id(),
            "taxonomia_id": taxonomia_id,
            "clave": c.clave,
            "nombre": c.nombre,
            "descripcion_para_modelo": c.descripcion_para_modelo,
            "umbral_confianza": c.umbral_confianza,
            "prioridad": c.prioridad,
            "color": c.color,
        }
        for c in taxonomia.categorias
    ]
    insertadas["categorias"] = await _insertar(
        conexion, _tabla(Categoria), filas, ["taxonomia_id", "clave"]
    )
    return insertadas


def _fila_agente(agente: AgenteInicial, proveedores: Mapping[str, uuid.UUID]) -> dict[str, Any]:
    """Fila de `agentes` para un agente del catálogo."""
    return {
        "id": nuevo_id(),
        "clave": agente.clave,
        "nombre": agente.nombre,
        "descripcion": agente.descripcion,
        "tipo": agente.tipo,
        "proveedor_id": proveedores[agente.proveedor] if agente.proveedor else None,
        "modelo": agente.modelo,
        "modelo_respaldo": agente.modelo_respaldo,
        "parametros": dict(agente.parametros),
        "herramientas": list(agente.herramientas),
        "habilitado": agente.habilitado,
    }


def _fila_version(agente: AgenteInicial, agente_id: uuid.UUID) -> dict[str, Any]:
    """Fila de la versión v1 publicada."""
    preguntas = preguntas_como_json(agente.preguntas) if agente.preguntas else None
    return {
        "id": nuevo_id(),
        "agente_id": agente_id,
        "numero": NUMERO_VERSION_INICIAL,
        "prompt_sistema": leer_prompt(agente.archivo_prompt),
        "preguntas_jev": preguntas,
        "notas": "Versión inicial sembrada por el bootstrap.",
        "publicado_en": func.now(),
    }


async def _activar_versiones_iniciales(conexion: AsyncConnection) -> None:
    """Apunta la versión activa a la v1 solo si no hay ninguna (no pisa cambios del admin)."""
    await conexion.execute(
        update(Agente)
        .where(
            and_(
                Agente.version_prompt_activa_id.is_(None),
                VersionPrompt.agente_id == Agente.id,
                VersionPrompt.numero == NUMERO_VERSION_INICIAL,
                VersionPrompt.publicado_en.is_not(None),
            )
        )
        .values(version_prompt_activa_id=VersionPrompt.id)
    )


async def _sembrar_agentes(conexion: AsyncConnection, catalogo: CatalogoInicial) -> dict[str, int]:
    """Agentes, sus versiones v1 y la versión activa."""
    proveedores = await _ids_por(conexion, ProveedorIa.id, ProveedorIa.nombre)
    filas = [_fila_agente(agente, proveedores) for agente in catalogo.agentes]
    insertadas = {"agentes": await _insertar(conexion, _tabla(Agente), filas, ["clave"])}
    agentes = await _ids_por(conexion, Agente.id, Agente.clave)
    versiones = [_fila_version(agente, agentes[agente.clave]) for agente in catalogo.agentes]
    insertadas["versiones_prompt"] = await _insertar(
        conexion, _tabla(VersionPrompt), versiones, ["agente_id", "numero"]
    )
    await _activar_versiones_iniciales(conexion)
    return insertadas


async def sembrar_catalogo(conexion: AsyncConnection, catalogo: CatalogoInicial) -> dict[str, int]:
    """Siembra todo el catálogo en la transacción del llamador; devuelve filas nuevas por tabla."""
    insertadas = {
        "roles": await _insertar(
            conexion,
            _tabla(Rol),
            [
                {"id": nuevo_id(), "nombre": r.nombre, "descripcion": r.descripcion}
                for r in catalogo.roles
            ],
            ["nombre"],
        ),
        "proveedores_ia": await _insertar(
            conexion,
            _tabla(ProveedorIa),
            [
                {
                    "id": nuevo_id(),
                    "nombre": p.nombre,
                    "habilitado": False,
                    "config": dict(p.config),
                }
                for p in catalogo.proveedores
            ],
            ["nombre"],
        ),
    }
    insertadas |= await _sembrar_taxonomia(conexion, catalogo)
    insertadas |= await _sembrar_agentes(conexion, catalogo)
    insertadas["configuracion"] = await _insertar(
        conexion,
        _tabla(Configuracion),
        [
            {"clave": c.clave, "valor": c.valor, "descripcion": c.descripcion}
            for c in catalogo.configuracion
        ],
        ["clave"],
    )
    return insertadas
