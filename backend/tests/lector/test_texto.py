"""Utilidades de texto del lector (P2, Tarea 2)."""
from datetime import date

import pytest

from app.silabo.lector.texto import entregables_en, fecha_dmy, horas, limpio, normalizar_clave, semana_periodo


def test_normalizar_clave():
    assert normalizar_clave("Aprendizaje en contacto con el\ndocente") == "APRENDIZAJE EN CONTACTO CON EL DOCENTE"


def test_limpio_une_lineas_y_conserva_mayusculas_y_latex():
    assert limpio("DE LA\nINFORMACIÓN,  con $H_0/H_1$ ") == "DE LA INFORMACIÓN, con $H_0/H_1$"
    assert limpio(None) == ""


def test_fecha_dmy():
    assert fecha_dmy("07/10/2026") == date(2026, 10, 7)


@pytest.mark.parametrize("texto, esperado", [(None, 0.0), ("", 0.0), ("0", 0.0), ("5", 5.0), ("1,5", 1.5), ("144.0", 144.0)])
def test_horas(texto, esperado):
    assert horas(texto) == esperado


def test_semana_periodo():
    assert semana_periodo(date(2026, 10, 7), date(2026, 10, 5)) == 1
    assert semana_periodo(date(2026, 11, 11), date(2026, 10, 5)) == 6


def test_entregables_en():
    assert entregables_en("Elaborar TAREA 1 – infografía", "pae 1 y Evaluación cognitiva 1", "TAREA 1 otra vez") == [
        "TAREA 1", "PAE 1", "EVALUACIÓN COGNITIVA 1"]
