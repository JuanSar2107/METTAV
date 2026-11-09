"""Tests de los mensajes de error seguros y la validación de correos."""

import time

import pytest

from mi_app.validacion import ErrorValidacion, correo_valido, mensaje_seguro


def test_mensaje_propio_se_muestra():
    assert mensaje_seguro(ErrorValidacion("La fecha no es válida.")) == "La fecha no es válida."


def test_mensaje_de_libreria_no_se_muestra():
    error = ValueError("invalid literal at /app/instance/mi_proyecto.sqlite3")
    assert "sqlite3" not in mensaje_seguro(error)


@pytest.mark.parametrize("correo", ["ana@correo.com", "a.b@sub.dominio.co", "a@b.c"])
def test_correos_validos(correo):
    assert correo_valido(correo)


@pytest.mark.parametrize(
    "correo",
    ["", "ana", "@correo.com", "ana@", "ana@correo", "ana@.com", "ana@correo.", "a@b@c.com", "a na@correo.com"],
)
def test_correos_invalidos(correo):
    assert not correo_valido(correo)


def test_correo_largo_no_es_costoso():
    inicio = time.perf_counter()
    correo_valido("a@" + "." * 200_000 + "\n")
    assert time.perf_counter() - inicio < 0.5
