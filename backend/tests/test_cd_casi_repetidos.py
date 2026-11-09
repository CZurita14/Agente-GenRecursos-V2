import numpy as np

from ciencia_datos.casi_repetidos import UMBRAL_CASI_REPETIDO, filtrar


def test_umbral_por_defecto():
    assert UMBRAL_CASI_REPETIDO == 0.95


def test_filtrar_quita_casi_iguales_y_conserva_el_primero():
    v = np.array([[1, 0], [0.999, 0.01], [0, 1]], dtype=float)
    assert filtrar(["a", "b", "c"], v) == (["a", "c"], 1)


def test_filtrar_quita_lo_parecido_a_contra():
    v = np.array([[1, 0], [0, 1]], dtype=float)
    assert filtrar(["a", "b"], v, contra=np.array([[1, 0.001]])) == (["b"], 1)


def test_filtrar_acepta_lista_vacia():
    assert filtrar([], np.empty((0, 2))) == ([], 0)


def test_filtrar_normaliza_la_longitud():
    v = np.array([[1, 0], [50, 0]], dtype=float)
    assert filtrar(["a", "b"], v) == (["a"], 1)


def test_filtrar_respeta_el_umbral():
    v = np.array([[1, 0], [0.9, 0.436]], dtype=float)  # coseno ~0,9
    assert filtrar(["a", "b"], v)[1] == 0
    assert filtrar(["a", "b"], v, umbral=0.85)[1] == 1
