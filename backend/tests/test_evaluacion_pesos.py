"""Pesos sugeridos y auditoría del plan de evaluación implícito en el sílabo (V3-4)."""
from datetime import date

from app.evaluacion.clasificador import Actividad, actividad_de
from app.evaluacion.norma import Bloque, norma_de
from app.evaluacion.pesos import calcular

PRESENCIAL, EN_LINEA, HIBRIDA = norma_de("PRESENCIAL"), norma_de("EN LINEA"), norma_de("HIBRIDA")
D = date(2026, 10, 5)


def _a(sesion, tipo, norma=EN_LINEA, columna="docente", texto="x"):
    return actividad_de(sesion, columna, tipo, texto, norma, "rotulo")


def _bloque(numero, nombre, sesiones):
    return Bloque(numero, nombre, D, D, sesiones)


def _completo_en_linea():
    return [_a("M1-S1", "diagnostica"), _a("M1-S2", "foro"), _a("M2-S1", "cuestionario"),
            _a("M2-S2", "practica_experimental", columna="practico", texto="Práctica de aprendizaje experimental 1: taller"),
            _a("M3-S1", "practica_experimental", columna="practico", texto="Práctica de aprendizaje experimental 2: lab"),
            _a("M2-S3", "portafolio", columna="autonomo"), _a("M3-S2", "prueba_sumativa"),
            _a("M3-S3", "entrega_avance", columna="autonomo"), _a("M4-S1", "exposicion_final", columna="autonomo")]


def test_en_linea_reparte_cada_calificacion_y_suma_100():
    actividades = _completo_en_linea()
    sesiones = sorted({a.sesion for a in actividades})
    plan = calcular(actividades, EN_LINEA, [_bloque(1, "Bloque único", sesiones)])
    pesos = {(p.actividad.sesion, p.actividad.tipo): p.peso_final for p in plan.actividades}
    assert pesos[("M1-S1", "diagnostica")] == 0
    assert pesos[("M3-S2", "prueba_sumativa")] == pesos[("M4-S1", "exposicion_final")] == 20  # C5 = prueba + proyecto.
    assert pesos[("M2-S2", "practica_experimental")] == pesos[("M3-S1", "practica_experimental")] == 10
    assert pesos[("M3-S3", "entrega_avance")] == 20 and pesos[("M2-S1", "cuestionario")] == 10
    assert plan.por_bloque == {1: 100.0} and round(sum(plan.por_momento.values()), 2) == 100
    assert plan.por_momento == {1: 5.0, 2: 25.0, 3: 50.0, 4: 20.0}
    assert plan.alertas == []


def test_presencial_cada_parcial_suma_100_y_vale_la_mitad_de_la_nota():
    p1 = [actividad_de("M1-S1", "docente", "diagnostica", "x", PRESENCIAL, "rotulo")] + [
        actividad_de(f"M1-S{k}", c, t, "Práctica 1", PRESENCIAL, "rotulo") for k, (c, t) in enumerate(
            [("docente", "foro"), ("docente", "cuestionario"), ("docente", "prueba_sumativa"),
             ("practico", "practica_experimental"), ("autonomo", "portafolio"), ("autonomo", "entrega_avance")], start=2)]
    p2 = [actividad_de(a.sesion.replace("M1", "M2"), a.columna, a.tipo, "Práctica 2", PRESENCIAL, "rotulo") for a in p1[1:]]
    bloques = [_bloque(1, "Parcial 1", sorted({a.sesion for a in p1})), _bloque(2, "Parcial 2", sorted({a.sesion for a in p2}))]
    plan = calcular(p1 + p2, PRESENCIAL, bloques)
    assert plan.por_bloque == {1: 100.0, 2: 100.0}
    prueba = next(p for p in plan.actividades if p.actividad.tipo == "prueba_sumativa")
    assert (prueba.peso_bloque, prueba.peso_final) == (20, 10)
    assert plan.por_momento == {1: 50.0, 2: 50.0} and plan.alertas == []


def test_una_calificacion_sin_actividades_se_avisa_y_no_se_reparte():
    actividades = [a for a in _completo_en_linea() if a.tipo != "entrega_avance"]
    plan = calcular(actividades, EN_LINEA, [_bloque(1, "Bloque único", sorted({a.sesion for a in actividades}))])
    assert plan.por_bloque == {1: 80.0}
    assert "Bloque único: falta una actividad de «Proyecto integrador» (20 %)." in plan.alertas


def test_los_pesos_iguales_suman_exacto_con_dos_decimales():
    foros = [_a(f"M1-S{k}", "foro") for k in range(1, 4)]
    plan = calcular(foros, EN_LINEA, [_bloque(1, "Bloque único", [a.sesion for a in foros])])
    assert [p.peso_final for p in plan.actividades] == [1.67, 1.67, 1.66]


def test_norma_pendiente_o_desconocida_no_sugiere_pesos():
    actividades = _completo_en_linea()
    for norma, aviso in [(HIBRIDA, "semipresencial está pendiente"), (None, "no se reconoce")]:
        plan = calcular(actividades, norma, [])
        assert all(p.peso_final == 0 for p in plan.actividades)
        assert any(aviso in a for a in plan.alertas)


def test_alertas_de_forma_sin_texto_del_silabo():
    actividades = [_a("M1-S1", "diagnostica"),
                   _a("M2-S2", "practica_experimental", columna="practico", texto="Práctica de aprendizaje experimental: taller"),
                   _a("M2-S2", "estudio_caso"), _a("M2-S2", "prueba_sumativa"), _a("M2-S2", "proyecto_final", columna="autonomo")]
    plan = calcular(actividades, EN_LINEA, [_bloque(1, "Bloque único", ["M1-S1", "M2-S2"])],
                    {"M2-S2/practico": "Práctica de aprendizaje experimental: taller"})
    assert "Prácticas experimentales sin numerar: M2-S2." in plan.alertas
    assert "M2-S2 concentra 4 evaluaciones en una sola sesión." in plan.alertas
    assert not any("taller" in a for a in plan.alertas)


def test_sin_diagnostica_se_avisa():
    actividades = [a for a in _completo_en_linea() if a.tipo != "diagnostica"]
    plan = calcular(actividades, EN_LINEA, [_bloque(1, "Bloque único", sorted({a.sesion for a in actividades}))])
    assert "No hay evaluación diagnóstica al inicio del proyecto formativo." in plan.alertas
