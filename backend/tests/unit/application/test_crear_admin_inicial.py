"""`CrearAdminInicial` con dobles, sin E/S (CA12)."""

from uuid import UUID, uuid4

import pytest

from app.application.use_cases.crear_admin_inicial import (
    EMAIL_ADMIN_DESARROLLO,
    AdminSinEmail,
    CrearAdminInicial,
    ResultadoAdminInicial,
    enmascarar_email,
)
from app.domain.auditoria import ActorTipo, EntradaAuditoria

GENERADA = "contrasena-generada-de-prueba"
DEFINIDA = "contrasena-definida-de-prueba"


class UsuariosFalsos:
    def __init__(self, hay: bool = False) -> None:
        self.hay = hay
        self.creados: list[dict[str, object]] = []
        self.id = uuid4()

    async def hay_usuarios(self) -> bool:
        return self.hay

    async def crear_con_rol(
        self,
        email: str,
        nombre: str,
        hash_password: str,
        requiere_cambio_password: bool,
        rol: str,
    ) -> UUID:
        self.creados.append(
            {
                "email": email,
                "nombre": nombre,
                "hash_password": hash_password,
                "requiere_cambio_password": requiere_cambio_password,
                "rol": rol,
            }
        )
        return self.id


class HasherFalso:
    def hashear(self, contrasena: str) -> str:
        return f"hash({len(contrasena)})"


class GeneradorFalso:
    def __init__(self) -> None:
        self.llamadas = 0

    def generar(self) -> str:
        self.llamadas += 1
        return GENERADA


class AuditoriaFalsa:
    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoria] = []

    async def registrar(self, entrada: EntradaAuditoria) -> None:
        self.entradas.append(entrada)


def _caso(
    usuarios: UsuariosFalsos,
) -> tuple[CrearAdminInicial, GeneradorFalso, AuditoriaFalsa]:
    generador, auditoria = GeneradorFalso(), AuditoriaFalsa()
    return CrearAdminInicial(usuarios, HasherFalso(), generador, auditoria), generador, auditoria


async def test_admin_con_usuarios_existentes_no_crea_nada() -> None:
    usuarios = UsuariosFalsos(hay=True)
    caso, generador, auditoria = _caso(usuarios)
    resultado = await caso.ejecutar("admin@ejemplo.com", None, es_produccion=True)
    assert (resultado, usuarios.creados, generador.llamadas, auditoria.entradas) == (
        ResultadoAdminInicial(creado=False),
        [],
        0,
        [],
    )


async def test_admin_sin_contrasena_la_genera_y_obliga_a_cambiarla() -> None:
    usuarios = UsuariosFalsos()
    caso, generador, _ = _caso(usuarios)
    resultado = await caso.ejecutar("admin@ejemplo.com", None, es_produccion=False)
    assert (resultado.creado, resultado.contrasena_generada, generador.llamadas) == (
        True,
        GENERADA,
        1,
    )
    assert usuarios.creados == [
        {
            "email": "admin@ejemplo.com",
            "nombre": "Administrador",
            "hash_password": f"hash({len(GENERADA)})",
            "requiere_cambio_password": True,
            "rol": "admin",
        }
    ]


async def test_admin_auditoria_sin_contrasena_ni_email() -> None:
    usuarios = UsuariosFalsos()
    caso, _, auditoria = _caso(usuarios)
    await caso.ejecutar("admin@ejemplo.com", None, es_produccion=False)
    (entrada,) = auditoria.entradas
    assert (
        entrada.actor_tipo,
        entrada.accion,
        entrada.entidad,
        entrada.entidad_id,
        dict(entrada.detalle),
    ) == (
        ActorTipo.SISTEMA,
        "usuario.admin_inicial_creado",
        "usuarios",
        str(usuarios.id),
        {"origen": "bootstrap", "generada_aleatoriamente": True},
    )
    assert (GENERADA in repr(entrada), "admin@ejemplo.com" in repr(entrada)) == (False, False)


async def test_admin_con_contrasena_definida_no_genera_ni_devuelve() -> None:
    usuarios = UsuariosFalsos()
    caso, generador, auditoria = _caso(usuarios)
    resultado = await caso.ejecutar("admin@ejemplo.com", DEFINIDA, es_produccion=True)
    assert (
        resultado.contrasena_generada,
        generador.llamadas,
        usuarios.creados[0]["requiere_cambio_password"],
        auditoria.entradas[0].detalle["generada_aleatoriamente"],
    ) == (None, 0, True, False)


async def test_admin_produccion_sin_email_falla() -> None:
    caso, _, auditoria = _caso(UsuariosFalsos())
    with pytest.raises(AdminSinEmail):
        await caso.ejecutar(None, None, es_produccion=True)
    assert auditoria.entradas == []


async def test_admin_fuera_de_produccion_sin_email_usa_el_local() -> None:
    usuarios = UsuariosFalsos()
    caso, _, _ = _caso(usuarios)
    resultado = await caso.ejecutar(None, None, es_produccion=False)
    assert (usuarios.creados[0]["email"], resultado.email_enmascarado) == (
        EMAIL_ADMIN_DESARROLLO,
        "a***@agente-correo.local",
    )


async def test_admin_repr_del_resultado_no_muestra_la_contrasena() -> None:
    caso, _, _ = _caso(UsuariosFalsos())
    resultado = await caso.ejecutar("admin@ejemplo.com", None, es_produccion=False)
    assert (GENERADA in repr(resultado), GENERADA in str(resultado)) == (False, False)


@pytest.mark.parametrize(
    ("email", "enmascarado"),
    [("admin@ejemplo.com", "a***@ejemplo.com"), ("x@y.z", "x***@y.z")],
)
def test_admin_enmascarar_email(email: str, enmascarado: str) -> None:
    assert enmascarar_email(email) == enmascarado
