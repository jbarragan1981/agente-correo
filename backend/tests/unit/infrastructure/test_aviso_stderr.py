"""`AvisoStderr`: escribe el bloque una vez en stderr y nada en stdout."""

import pytest

from app.infrastructure.avisos.stderr import AVISO_UNA_VEZ, SEPARADOR, AvisoStderr

CONTRASENA = "contrasena-generada-de-prueba"


def test_aviso_stderr_escribe_una_vez_y_nada_en_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    AvisoStderr().mostrar_contrasena_inicial("a***@ejemplo.com", CONTRASENA)
    salida = capsys.readouterr()
    assert (salida.out, salida.err.count(CONTRASENA)) == ("", 1)


def test_aviso_stderr_bloque_fijo(capsys: pytest.CaptureFixture[str]) -> None:
    AvisoStderr().mostrar_contrasena_inicial("a***@ejemplo.com", CONTRASENA)
    lineas = capsys.readouterr().err.splitlines()
    assert lineas == [
        SEPARADOR,
        f"Contraseña inicial del administrador a***@ejemplo.com: {CONTRASENA}",
        AVISO_UNA_VEZ,
        SEPARADOR,
    ]
