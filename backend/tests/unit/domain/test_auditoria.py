"""`EntradaAuditoria`: acción con formato `dominio.verbo` y detalle inmutable."""

import pytest

from app.domain.auditoria import AccionAuditoriaInvalida, ActorTipo, EntradaAuditoria


@pytest.mark.parametrize("accion", ["bd.migrada", "usuario.admin_inicial_creado", "a.b.c"])
def test_auditoria_acciones_validas(accion: str) -> None:
    assert EntradaAuditoria(ActorTipo.SISTEMA, accion).accion == accion


@pytest.mark.parametrize(
    "accion", ["", "sinpunto", "Bd.migrada", "bd.", ".migrada", "bd.migrada\n", "bd.mi grada"]
)
def test_auditoria_acciones_invalidas(accion: str) -> None:
    with pytest.raises(AccionAuditoriaInvalida):
        EntradaAuditoria(ActorTipo.SISTEMA, accion)


def test_auditoria_detalle_es_una_copia_inmutable() -> None:
    original: dict[str, object] = {"a": 1}
    entrada = EntradaAuditoria(ActorTipo.SISTEMA, "bd.migrada", detalle=original)
    original["a"] = 2
    with pytest.raises(TypeError):
        entrada.detalle["a"] = 3  # type: ignore[index]
    assert entrada.detalle == {"a": 1}


def test_auditoria_actor_tipo_valores() -> None:
    assert [str(t) for t in ActorTipo] == ["usuario", "sistema", "agente"]
