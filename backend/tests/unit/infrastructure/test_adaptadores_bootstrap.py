"""Adaptadores sin E/S: Argon2id, generador, lectura de prompts y comprobaciones de privilegios."""

from argon2 import PasswordHasher

from app.core.ids import nuevo_id
from app.domain.catalogo_inicial import CLAUSULA_DATOS_NO_CONFIABLES
from app.infrastructure.db.bootstrap.privilegios import (
    COMPROBACIONES_APP,
    COMPROBACIONES_MIGRADOR,
    comprobaciones_fallidas,
    comprobaciones_fallidas_migrador,
)
from app.infrastructure.db.privilegios_migracion import (
    CREAR_FUNCION,
    CREAR_FUNCION_V2,
    CREAR_FUNCION_V3,
    REVOCAR_ALEMBIC_VERSION,
    REVOCAR_CHECKPOINT_MIGRATIONS,
)
from app.infrastructure.db.semillas import leer_prompt
from app.infrastructure.seguridad.argon2 import GeneradorContrasenaSecrets, HasherArgon2

PREFIJO_ARGON2ID = "$argon2id$v=19$m=65536,t=3,p=4$"


def test_argon2_hash_con_parametros_de_docs_07() -> None:
    hash_ = HasherArgon2().hashear("contrasena-de-prueba")
    assert (
        hash_.startswith(PREFIJO_ARGON2ID),
        PasswordHasher().verify(hash_, "contrasena-de-prueba"),
    ) == (
        True,
        True,
    )


def test_argon2_hash_con_sal_distinta() -> None:
    hasher = HasherArgon2()
    assert hasher.hashear("igual-de-prueba") != hasher.hashear("igual-de-prueba")


def test_generador_contrasena_24_caracteres_urlsafe_y_distintas() -> None:
    generador = GeneradorContrasenaSecrets()
    contrasenas = {generador.generar() for _ in range(20)}
    assert (len(contrasenas), {len(c) for c in contrasenas}) == (20, {24})


def test_ids_uuid_v7_ordenables() -> None:
    ids = [nuevo_id() for _ in range(50)]
    assert ({i.version for i in ids}, ids == sorted(ids)) == ({7}, True)


def test_semillas_leer_prompt_empaquetado() -> None:
    assert CLAUSULA_DATOS_NO_CONFIABLES in leer_prompt("guardian_v1.md")


def test_privilegios_rol_app_correcto_sin_fallos() -> None:
    fila: dict[str, object] = {**dict.fromkeys(COMPROBACIONES_APP, False), "rol": "agente_app"}
    assert comprobaciones_fallidas(fila, "agente_migrador") == ()


def test_privilegios_lista_todas_las_comprobaciones_fallidas() -> None:
    fila: dict[str, object] = {
        **dict.fromkeys(COMPROBACIONES_APP, True),
        "rol": "agente_migrador",
    }
    fallidas = comprobaciones_fallidas(fila, "agente_migrador")
    assert fallidas == (
        *(f"app.{nombre}" for nombre in COMPROBACIONES_APP),
        "app.mismo_rol_que_migrador",
    )


def test_funcion_privilegios_v2_extiende_la_v1_con_alembic_version() -> None:
    assert (
        CREAR_FUNCION_V2.replace(REVOCAR_ALEMBIC_VERSION, ""),
        REVOCAR_ALEMBIC_VERSION in CREAR_FUNCION,
        "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.alembic_version" in CREAR_FUNCION_V2,
    ) == (CREAR_FUNCION, False, True)


def test_funcion_privilegios_v3_extiende_la_v2_con_checkpoint_migrations() -> None:
    assert (
        CREAR_FUNCION_V3.replace(REVOCAR_CHECKPOINT_MIGRATIONS, ""),
        REVOCAR_CHECKPOINT_MIGRATIONS in CREAR_FUNCION_V2,
        "ON langgraph.checkpoint_migrations FROM agente_app" in CREAR_FUNCION_V3,
    ) == (CREAR_FUNCION_V2, False, True)


def test_privilegios_app_incluye_las_comprobaciones_de_s_m1_y_s_b1() -> None:
    assert {
        "miembro_del_migrador",
        "rol_de_servidor",
        "modifica_checkpoint_migrations",
    } <= set(COMPROBACIONES_APP)


def test_privilegios_migrador_correcto_sin_fallos() -> None:
    fila: dict[str, object] = {**dict.fromkeys(COMPROBACIONES_MIGRADOR, False), "rol": "m"}
    assert comprobaciones_fallidas_migrador(fila) == ()


def test_privilegios_migrador_lista_todas_las_comprobaciones_fallidas() -> None:
    fila: dict[str, object] = {**dict.fromkeys(COMPROBACIONES_MIGRADOR, True), "rol": "m"}
    assert comprobaciones_fallidas_migrador(fila) == (
        "migrador.superusuario",
        "migrador.crea_roles",
        "migrador.crea_bases",
        "migrador.salta_rls",
        "migrador.rol_de_servidor",
    )
