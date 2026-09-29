"""Metadata de los modelos: tablas exactas, nombres deterministas, CHECK y FK compuesta."""

from typing import Final

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Table, UniqueConstraint

from app.infrastructure.db.modelos import Base

TABLAS_E0_2: Final = {
    "usuarios",
    "roles",
    "usuarios_roles",
    "auditoria",
    "configuracion",
    "proveedores_ia",
    "agentes",
    "versiones_prompt",
    "taxonomias",
    "categorias",
}
CHECKS: Final = {
    "ck_usuarios_email_valido",
    "ck_roles_nombre_valido",
    "ck_auditoria_actor_tipo_valido",
    "ck_auditoria_accion_valida",
    "ck_configuracion_clave_valida",
    "ck_proveedores_ia_nombre_valido",
    "ck_categorias_clave_valida",
    "ck_categorias_umbral_en_rango",
    "ck_categorias_color_hex",
    "ck_agentes_clave_valida",
    "ck_agentes_tipo_valido",
    "ck_agentes_modelo_requerido",
    "ck_versiones_prompt_numero_positivo",
}


def _tabla(nombre: str) -> Table:
    return Base.metadata.tables[nombre]


def _restricciones(tipo: type) -> set[str]:
    return {
        str(r.name)
        for tabla in Base.metadata.tables.values()
        for r in tabla.constraints
        if isinstance(r, tipo)
    }


def test_modelos_metadata_contiene_exactamente_las_tablas_de_e0_2() -> None:
    assert set(Base.metadata.tables) == TABLAS_E0_2


def test_modelos_todas_las_tablas_en_public() -> None:
    assert {tabla.schema for tabla in Base.metadata.tables.values()} == {None}


def test_modelos_checks_presentes_con_nombre_determinista() -> None:
    assert _restricciones(CheckConstraint) == CHECKS


def test_modelos_uniques_con_nombre_determinista() -> None:
    assert _restricciones(UniqueConstraint) == {
        "uq_usuarios_email",
        "uq_roles_nombre",
        "uq_auditoria_secuencia",
        "uq_proveedores_ia_nombre",
        "uq_taxonomias_nombre",
        "uq_categorias_taxonomia_id",
        "uq_agentes_clave",
        "uq_versiones_prompt_agente_id",
        "uq_versiones_prompt_id",
    }


@pytest.mark.parametrize("tabla", sorted(TABLAS_E0_2))
def test_modelos_clave_primaria_con_nombre_pk(tabla: str) -> None:
    assert _tabla(tabla).primary_key.name == f"pk_{tabla}"


def test_modelos_fk_compuesta_de_version_activa() -> None:
    fks = [
        fk
        for fk in _tabla("agentes").constraints
        if isinstance(fk, ForeignKeyConstraint) and len(fk.columns) == 2
    ]
    assert len(fks) == 1
    fk = fks[0]
    assert (
        fk.name,
        [c.name for c in fk.columns],
        [e.target_fullname for e in fk.elements],
        fk.use_alter,
    ) == (
        "fk_agentes_version_prompt_activa_id_versiones_prompt",
        ["version_prompt_activa_id", "id"],
        ["versiones_prompt.id", "versiones_prompt.agente_id"],
        True,
    )


@pytest.mark.parametrize(
    ("tabla", "columna", "accion"),
    [
        ("usuarios_roles", "usuario_id", "CASCADE"),
        ("usuarios_roles", "rol_id", "RESTRICT"),
        ("configuracion", "actualizado_por", "SET NULL"),
        ("categorias", "taxonomia_id", "CASCADE"),
        ("agentes", "proveedor_id", "RESTRICT"),
        ("versiones_prompt", "agente_id", "CASCADE"),
        ("versiones_prompt", "creado_por", "SET NULL"),
    ],
)
def test_modelos_acciones_on_delete(tabla: str, columna: str, accion: str) -> None:
    (fk,) = _tabla(tabla).c[columna].foreign_keys
    assert fk.ondelete == accion


def test_modelos_auditoria_sin_fk_de_actor_ni_marcas_de_tiempo() -> None:
    auditoria = _tabla("auditoria")
    assert (
        auditoria.c.actor_id.foreign_keys,
        "creado_en" in auditoria.c,
        auditoria.c.secuencia.identity is not None,
    ) == (set(), False, True)


@pytest.mark.parametrize("tabla", sorted(TABLAS_E0_2 - {"auditoria", "usuarios_roles"}))
def test_modelos_marcas_de_tiempo_con_default_del_servidor(tabla: str) -> None:
    columnas = _tabla(tabla).c
    assert (
        columnas.creado_en.server_default is not None,
        columnas.actualizado_en.server_default is not None,
        columnas.actualizado_en.onupdate is not None,
    ) == (True, True, True)


def test_modelos_ids_se_generan_como_uuid_v7() -> None:
    default = _tabla("usuarios").c.id.default
    assert default is not None
    assert default.arg(None).version == 7  # type: ignore[union-attr]
