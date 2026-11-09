"""Esqueleto determinista del sílabo simulado: perfil estructural, fechas e ids."""
from pathlib import Path

from ciencia_datos.sim_esqueleto import crear_esqueleto
from ciencia_datos.sim_plan import cupos

CATALOGO = Path(__file__).resolve().parents[2] / "kb" / "catalogo.yaml"


def test_respeta_el_perfil_en_todos_los_cupos():
    for cupo in cupos(CATALOGO):
        e = crear_esqueleto(cupo)
        por_momento = [len(m.sesiones) for m in e.momentos]
        assert len(e.momentos) == 4
        assert all(1 <= n <= 4 for n in por_momento)
        assert 6 <= sum(por_momento) <= 11
        assert 3 <= e.n_resultados <= 4
        assert 3 <= e.n_metodologias <= 4
        assert 3 <= e.n_filas_rubrica <= 6
        assert 4 <= e.n_filas_rubrica_pf <= 5
        assert 1 <= e.contenidos_por_sesion <= 3
        assert e.horas_total in (96, 144)


def test_es_determinista_y_varia_entre_cupos():
    lista = cupos(CATALOGO)
    assert crear_esqueleto(lista[0]) == crear_esqueleto(lista[0])
    assert crear_esqueleto(lista[0], semilla=1) != crear_esqueleto(lista[0], semilla=2)
    assert len({tuple(len(m.sesiones) for m in crear_esqueleto(c).momentos) for c in lista}) > 5


def test_fechas_dentro_del_periodo_y_en_orden():
    for cupo in cupos(CATALOGO):
        e = crear_esqueleto(cupo)
        fechas = [s.fecha for m in e.momentos for s in m.sesiones]
        assert fechas == sorted(fechas)
        assert e.periodo.inicio <= fechas[0] and fechas[-1] <= e.periodo.fin
        assert e.periodo.codigo == "SIM-2026"


def test_momentos_contienen_sus_sesiones_y_no_se_solapan():
    e = crear_esqueleto(cupos(CATALOGO)[3])
    for m in e.momentos:
        assert all(m.fecha_inicio <= s.fecha <= m.fecha_fin for s in m.sesiones)
    for a, b in zip(e.momentos, e.momentos[1:]):
        assert a.fecha_fin < b.fecha_inicio
    assert e.momentos[0].fecha_inicio >= e.periodo.inicio
    assert e.momentos[-1].fecha_fin <= e.periodo.fin


def test_ids_de_sesion_unicos_y_semanas_validas():
    for cupo in cupos(CATALOGO):
        e = crear_esqueleto(cupo)
        sesiones = [s for m in e.momentos for s in m.sesiones]
        ids = [s.id for s in sesiones]
        assert len(set(ids)) == len(ids)
        for m in e.momentos:
            assert [s.id for s in m.sesiones] == [f"M{m.numero}-S{i}" for i in range(1, len(m.sesiones) + 1)]
        assert all(1 <= s.semana_periodo <= 16 for s in sesiones)
        assert all(s.horas_docente > 0 and s.horas_practico > 0 and s.horas_autonomo > 0 for s in sesiones)
