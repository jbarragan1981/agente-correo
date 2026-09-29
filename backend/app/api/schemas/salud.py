"""Esquemas de salida de las sondas de salud."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SaludOut(BaseModel):
    """Liveness: el proceso responde."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"estado": "vivo"}]})

    estado: Literal["vivo"]


class PreparacionOut(BaseModel):
    """Readiness: todas las dependencias están disponibles."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "estado": "listo",
                    "comprobaciones": {"base_datos": "ok", "migraciones": "ok"},
                }
            ]
        },
    )

    estado: Literal["listo"]
    comprobaciones: dict[str, Literal["ok"]]
