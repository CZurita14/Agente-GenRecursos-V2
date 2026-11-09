from ciencia_datos.origen import es_simulado
from ciencia_datos.separar import cumple_minimo, dejar_fuera, separar, separar_preliminar


def test_ningun_silabo_queda_en_ambos_grupos_y_es_estable():
    d = {f"PF{i}": ("FING" if i < 10 else "FACEAN") for i in range(20)}
    a, b = separar(d), separar(d)
    assert a == b and not set(a.entrenamiento) & set(a.prueba)
    assert len(a.prueba) == 6


def test_facultad_con_un_silabo_va_a_entrenamiento_y_avisa():
    s = separar({"A": "FING"})
    assert s.entrenamiento == ["A"] and s.prueba == [] and s.avisos


def test_facultad_con_dos_silabos_manda_exactamente_uno_a_prueba():
    s = separar({"A": "FING", "B": "FING"})
    assert len(s.prueba) == 1 and len(s.entrenamiento) == 1
    assert sorted(s.prueba + s.entrenamiento) == ["A", "B"]


def test_el_orden_de_entrada_no_cambia_la_separacion():
    d = {f"PF{i}": "FING" for i in range(10)}
    assert separar(d) == separar(dict(reversed(list(d.items()))))


def test_dejar_fuera_y_minimo():
    d = {f"F{f}-{i}": f"F{f}" for f in range(5) for i in range(4)}
    assert cumple_minimo(d) and not cumple_minimo({"A": "FING"})
    assert all(all(c.startswith(fac) for c in s.prueba) for fac, s in dejar_fuera(d).items())


def test_dejar_fuera_pone_todos_los_codigos_de_la_facultad_en_prueba():
    d = {f"F{f}-{i}": f"F{f}" for f in range(3) for i in range(4)}
    fuera = dejar_fuera(d)
    assert set(fuera) == {"F0", "F1", "F2"}
    for fac, s in fuera.items():
        propios = {c for c, f in d.items() if f == fac}
        assert set(s.prueba) == propios
        assert not set(s.entrenamiento) & propios
        assert set(s.entrenamiento) | set(s.prueba) == set(d)


def test_los_reales_van_a_control_y_nunca_entrenan():
    mapa = {f"SIM-A-{i}": "A" for i in range(10)} | {"REAL-1": "A", "REAL-2": "B"}
    s = separar_preliminar(mapa)
    assert s.control == ["REAL-1", "REAL-2"]
    assert not {"REAL-1", "REAL-2"} & (set(s.entrenamiento) | set(s.prueba))
    assert all(es_simulado(c) for c in s.prueba)
    assert len(s.prueba) == 3 and len(s.entrenamiento) == 7


def test_separar_deja_el_control_vacio_por_omision():
    assert separar({"A": "FING", "B": "FING"}).control == []
