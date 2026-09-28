"""Configuración validada con fallo cerrado en producción (ADR-0007).

Único módulo que lee variables de entorno. Los mensajes de error nombran el campo
y nunca incluyen el valor recibido.
"""

import base64
import binascii
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Entorno = Literal["development", "test", "production"]
NivelLog = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

RAIZ_REPO = Path(__file__).resolve().parents[3]
URL_BD_DESARROLLO = "postgresql+asyncpg://postgres:postgres@localhost:5432/agente_correo"
ESQUEMA_BD = "postgresql+asyncpg://"
BYTES_CLAVE_MAESTRA = 32
BYTES_MINIMOS_JWT = 32
ESQUEMAS_CORS = frozenset({"http", "https"})
OBLIGATORIA_EN_PRODUCCION = "obligatoria con ENV=production"


def _es_produccion(info: ValidationInfo) -> bool:
    """Indica si el campo `env` ya validado vale `production`."""
    return info.data.get("env") == "production"


def _validar_origen(origen: str) -> None:
    """Exige un origen `scheme://host[:puerto]` sin comodines, ruta, query ni credenciales."""
    if "*" in origen:
        raise ValueError("no se admite '*' en los orígenes CORS")
    partes = urlsplit(origen)
    if partes.scheme not in ESQUEMAS_CORS or not partes.hostname:
        raise ValueError("cada origen CORS debe tener la forma http(s)://host[:puerto]")
    if partes.path or partes.query or partes.fragment or partes.username or partes.password:
        raise ValueError("un origen CORS no admite ruta, query, fragmento ni credenciales")


class Settings(BaseSettings):
    """Configuración del backend leída del entorno y del `.env` de la raíz del repo."""

    model_config = SettingsConfigDict(
        env_file=RAIZ_REPO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        case_sensitive=False,
        frozen=True,
    )

    env: Entorno = "development"
    debug: bool = Field(default=False, validate_default=True)
    log_level: NivelLog = "INFO"
    database_url: SecretStr | None = Field(default=None, validate_default=True)
    app_master_key: SecretStr | None = Field(default=None, validate_default=True)
    jwt_secret: SecretStr | None = Field(default=None, validate_default=True)
    cors_origenes: Annotated[list[str], NoDecode] = Field(
        default_factory=list, validate_default=True
    )
    salud_bd_timeout_s: float = Field(default=2.0, gt=0, le=10)

    @field_validator("debug")
    @classmethod
    def _sin_debug_en_produccion(cls, valor: bool, info: ValidationInfo) -> bool:
        """Rechaza `DEBUG=true` en producción."""
        if valor and _es_produccion(info):
            raise ValueError("debe ser false con ENV=production")
        return valor

    @field_validator("database_url")
    @classmethod
    def _validar_database_url(
        cls, valor: SecretStr | None, info: ValidationInfo
    ) -> SecretStr | None:
        """Exige esquema `postgresql+asyncpg://` y presencia en producción."""
        if valor is None:
            if _es_produccion(info):
                raise ValueError(OBLIGATORIA_EN_PRODUCCION)
            return None
        if not valor.get_secret_value().startswith(ESQUEMA_BD):
            raise ValueError(f"debe usar el esquema {ESQUEMA_BD}")
        return valor

    @field_validator("app_master_key")
    @classmethod
    def _validar_clave_maestra(
        cls, valor: SecretStr | None, info: ValidationInfo
    ) -> SecretStr | None:
        """Exige base64 estricto que decodifique a 32 bytes exactos."""
        if valor is None:
            if _es_produccion(info):
                raise ValueError(OBLIGATORIA_EN_PRODUCCION)
            return None
        try:
            decodificada = base64.b64decode(valor.get_secret_value(), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("debe ser base64 válido") from None
        if len(decodificada) != BYTES_CLAVE_MAESTRA:
            raise ValueError(f"debe decodificar a {BYTES_CLAVE_MAESTRA} bytes exactos")
        return valor

    @field_validator("jwt_secret")
    @classmethod
    def _validar_jwt_secret(cls, valor: SecretStr | None, info: ValidationInfo) -> SecretStr | None:
        """Exige al menos 32 bytes UTF-8."""
        if valor is None:
            if _es_produccion(info):
                raise ValueError(OBLIGATORIA_EN_PRODUCCION)
            return None
        if len(valor.get_secret_value().encode("utf-8")) < BYTES_MINIMOS_JWT:
            raise ValueError(f"debe tener al menos {BYTES_MINIMOS_JWT} bytes")
        return valor

    @field_validator("cors_origenes", mode="before")
    @classmethod
    def _separar_origenes(cls, valor: object) -> object:
        """Convierte `"https://a, https://b"` en lista, descartando vacíos."""
        if isinstance(valor, str):
            return [origen.strip() for origen in valor.split(",") if origen.strip()]
        return valor

    @field_validator("cors_origenes")
    @classmethod
    def _validar_origenes(cls, valor: list[str], info: ValidationInfo) -> list[str]:
        """Valida cada origen y, en producción, exige lista no vacía solo con https."""
        for origen in valor:
            _validar_origen(origen)
        if _es_produccion(info):
            if not valor:
                raise ValueError(OBLIGATORIA_EN_PRODUCCION)
            if any(urlsplit(origen).scheme != "https" for origen in valor):
                raise ValueError("solo se admiten orígenes https con ENV=production")
        return valor

    @property
    def es_produccion(self) -> bool:
        """Indica si el entorno es producción."""
        return self.env == "production"

    def url_base_datos(self) -> str:
        """Devuelve la URL de la BD; en desarrollo y pruebas usa un valor local por defecto."""
        if self.database_url is None:
            return URL_BD_DESARROLLO
        return self.database_url.get_secret_value()


class ConfiguracionInvalida(Exception):
    """Configuración rechazada; contiene solo pares (campo, mensaje), nunca valores."""

    def __init__(self, errores: Sequence[tuple[str, str]]) -> None:
        self.errores: tuple[tuple[str, str], ...] = tuple(errores)
        detalle = "; ".join(f"{campo}: {mensaje}" for campo, mensaje in self.errores)
        super().__init__(f"Configuración inválida: {detalle}")


def _errores_sin_valores(error: ValidationError) -> list[tuple[str, str]]:
    """Extrae (VARIABLE, mensaje) de una ValidationError descartando entradas y contexto."""
    detalles = error.errors(include_url=False, include_context=False, include_input=False)
    return [
        (
            ".".join(str(parte) for parte in detalle["loc"]).upper() or "CONFIGURACION",
            detalle["msg"].removeprefix("Value error, "),
        )
        for detalle in detalles
    ]


def cargar_settings() -> Settings:
    """Carga la configuración del entorno o lanza `ConfiguracionInvalida` sin valores."""
    try:
        return Settings()
    except ValidationError as error:
        raise ConfiguracionInvalida(_errores_sin_valores(error)) from None
