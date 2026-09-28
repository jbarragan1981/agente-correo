"""Errores del bootstrap; su texto nunca contiene URL, usuario ni contraseña."""

from typing import ClassVar


class ErrorBootstrap(Exception):
    """Fallo del bootstrap en un paso concreto (código de salida 2)."""

    evento: ClassVar[str] = "bootstrap.fallido"
    paso_por_defecto: ClassVar[str] = "desconocido"

    def __init__(
        self, paso: str | None = None, tipo_error: str | None = None, sqlstate: str | None = None
    ) -> None:
        self.paso = paso or self.paso_por_defecto
        self.tipo_error = tipo_error or type(self).__name__
        self.sqlstate = sqlstate
        super().__init__(f"{self.evento} en el paso {self.paso}")


class FalloEnPaso(ErrorBootstrap):
    """Excepción inesperada envuelta con el paso donde ocurrió."""


class UrlInvalida(ErrorBootstrap):
    """La URL de la base no se puede interpretar."""

    evento = "bootstrap.url_invalida"
    paso_por_defecto = "configuracion"


class NombreBaseInvalido(ErrorBootstrap):
    """El nombre de la base no cumple `^[A-Za-z_][A-Za-z0-9_]{0,62}$`."""

    evento = "bootstrap.nombre_base_invalido"
    paso_por_defecto = "configuracion"


class FaltaUrlMigrador(ErrorBootstrap):
    """Con roles separados hace falta `DATABASE_URL_MIGRADOR`."""

    evento = "bootstrap.falta_url_migrador"
    paso_por_defecto = "configuracion"


class BdNoDisponible(ErrorBootstrap):
    """PostgreSQL no aceptó conexiones dentro de `DB_ESPERA_MAX_S`."""

    evento = "bootstrap.bd_no_disponible"
    paso_por_defecto = "espera"


class AutenticacionRechazada(ErrorBootstrap):
    """El servidor responde pero rechaza la credencial configurada."""

    evento = "bootstrap.autenticacion_rechazada"
    paso_por_defecto = "espera"


class BaseInexistente(ErrorBootstrap):
    """La base no existe y `DB_AUTO_CREATE=false`."""

    evento = "bootstrap.base_inexistente"
    paso_por_defecto = "creacion"


class LockTimeout(ErrorBootstrap):
    """Otro proceso retuvo el advisory lock más de `DB_BOOTSTRAP_LOCK_TIMEOUT_S`."""

    evento = "bootstrap.lock_timeout"
    paso_por_defecto = "bloqueo"


class PrivilegiosInseguros(ErrorBootstrap):
    """El rol de aplicación o el migrador tienen privilegios excesivos."""

    evento = "bootstrap.privilegios_inseguros"
    paso_por_defecto = "privilegios"

    def __init__(self, comprobaciones: tuple[str, ...]) -> None:
        super().__init__()
        self.comprobaciones = comprobaciones


class AdminSinEmailEnProduccion(ErrorBootstrap):
    """Producción sin usuarios y sin `ADMIN_INITIAL_EMAIL`."""

    evento = "bootstrap.admin_sin_email"
    paso_por_defecto = "semillas"
