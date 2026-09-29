"""Excepciones de dominio. No conocen HTTP; la API las traduce a problem+json."""


class ExcepcionDominio(Exception):
    """Base de toda excepción de negocio."""


class NoEncontrado(ExcepcionDominio):
    """El recurso solicitado no existe o no es visible para el actor."""


class Conflicto(ExcepcionDominio):
    """La operación choca con el estado actual del recurso."""
