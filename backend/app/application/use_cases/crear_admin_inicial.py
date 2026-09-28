"""Caso de uso: crear el administrador inicial si no hay usuarios (ADR-0008)."""

from dataclasses import dataclass, field
from typing import Final

from app.application.ports.auditoria import AuditoriaPort
from app.application.ports.seguridad import GeneradorContrasenaPort, HasherPasswordPort
from app.application.ports.usuarios import RepositorioUsuariosPort
from app.domain.auditoria import ActorTipo, EntradaAuditoria

EMAIL_ADMIN_DESARROLLO: Final = "admin@agente-correo.local"
NOMBRE_ADMIN: Final = "Administrador"
ROL_ADMIN: Final = "admin"
ACCION_ADMIN_CREADO: Final = "usuario.admin_inicial_creado"


class AdminSinEmail(Exception):
    """En producción, sin usuarios, hace falta `ADMIN_INITIAL_EMAIL`."""


def enmascarar_email(email: str) -> str:
    """`admin@ejemplo.com` → `a***@ejemplo.com`."""
    local, _, dominio = email.partition("@")
    return f"{local[:1]}***@{dominio}"


@dataclass(frozen=True)
class ResultadoAdminInicial:
    """Resultado; la contraseña generada nunca aparece en `repr`."""

    creado: bool
    email_enmascarado: str | None = None
    contrasena_generada: str | None = field(default=None, repr=False)


class CrearAdminInicial:
    """Crea el admin con cambio de contraseña obligatorio y deja auditoría sin secretos."""

    def __init__(
        self,
        usuarios: RepositorioUsuariosPort,
        hasher: HasherPasswordPort,
        generador: GeneradorContrasenaPort,
        auditoria: AuditoriaPort,
    ) -> None:
        self._usuarios = usuarios
        self._hasher = hasher
        self._generador = generador
        self._auditoria = auditoria

    async def ejecutar(
        self, email: str | None, contrasena: str | None, es_produccion: bool
    ) -> ResultadoAdminInicial:
        """Crea el admin si `usuarios` está vacía; si no, no hace nada."""
        if await self._usuarios.hay_usuarios():
            return ResultadoAdminInicial(creado=False)
        email_final = self._email(email, es_produccion)
        generada = contrasena is None
        contrasena_final = self._generador.generar() if contrasena is None else contrasena
        usuario_id = await self._usuarios.crear_con_rol(
            email=email_final,
            nombre=NOMBRE_ADMIN,
            hash_password=self._hasher.hashear(contrasena_final),
            requiere_cambio_password=True,
            rol=ROL_ADMIN,
        )
        await self._auditoria.registrar(
            EntradaAuditoria(
                actor_tipo=ActorTipo.SISTEMA,
                accion=ACCION_ADMIN_CREADO,
                entidad="usuarios",
                entidad_id=str(usuario_id),
                detalle={"origen": "bootstrap", "generada_aleatoriamente": generada},
            )
        )
        return ResultadoAdminInicial(
            creado=True,
            email_enmascarado=enmascarar_email(email_final),
            contrasena_generada=contrasena_final if generada else None,
        )

    @staticmethod
    def _email(email: str | None, es_produccion: bool) -> str:
        """Email configurado; fuera de producción usa uno local evidente."""
        if email is not None:
            return email
        if es_produccion:
            raise AdminSinEmail
        return EMAIL_ADMIN_DESARROLLO
