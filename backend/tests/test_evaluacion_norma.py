"""Norma de evaluación del RRA por modalidad y bloques de calificación por fecha (V3-2)."""
import copy
import json
from datetime import date
from pathlib import Path

import pytest

from app.evaluacion.norma import (
    CALIFICACIONES, NormaInvalida, bloques, cargar_tabla, norma_de,
)
from app.sga.traductor import a_contrato
from app.silabo.integridad import cargar_silabo

RAIZ = Path(__file__).resolve().parents[2]
COMPLETO = json.loads((RAIZ / "docs" / "api-silabo" / "ejemplo-completo.json").read_text(encoding="utf-8"))


def _silabo(modalidad="PRESENCIAL", textos=None):
    """Ejemplo completo (sesiones del 29/09, 01/10 y 27/10) con la modalidad y los textos dados."""
    crudo = copy.deepcopy(COMPLETO)
    crudo["proyecto_formativo"]["modalidad"] = modalidad
    for (m, s), texto in (textos or {}).items():
        crudo["momentos"][m]["sesiones"][s]["docente"]["texto"] = texto
    return cargar_silabo(a_contrato(crudo))


# --- tabla -----------------------------------------------------------------------------------


def test_las_modalidades_definidas_suman_100_y_respetan_el_rra():
    presencial, en_linea = norma_de("PRESENCIAL"), norma_de("EN LINEA")
    assert sum(presencial.pesos.values()) == sum(en_linea.pesos.values()) == 100
    assert presencial.componentes == {"contacto": 45, "practico": 30, "autonomo": 25}
    assert en_linea.componentes == {"contacto": 55, "practico": 20, "autonomo": 25}
    assert (presencial.bloques, presencial.c5) == ("parciales", "prueba_de_cada_parcial")
    assert (en_linea.bloques, en_linea.c5, en_linea.c4) == ("unico", "prueba_y_proyecto_final", "avances_del_proyecto")


def test_distancia_es_igual_que_en_linea_y_semipresencial_queda_pendiente():
    distancia, semi = norma_de("A DISTANCIA"), norma_de("HÍBRIDA")
    assert distancia.modalidad == "distancia" and distancia.estado == "definida"
    assert distancia.pesos == norma_de("en línea").pesos and distancia.bloques == "unico"
    assert (semi.modalidad, semi.estado, semi.bloques) == ("semipresencial", "pendiente", None)
    assert semi.pesos["C5_sumativa"] == 30


@pytest.mark.parametrize("texto,esperada", [
    ("PRESENCIAL", "presencial"), ("Presencial", "presencial"), ("EN LINEA", "en_linea"), ("En línea", "en_linea"),
    ("HIBRIDA", "semipresencial"), ("Semipresencial", "semipresencial"), ("DISTANCIA", "distancia"),
])
def test_alias_de_modalidad(texto, esperada):
    assert norma_de(texto).modalidad == esperada


@pytest.mark.parametrize("texto", ["", "  ", "DUAL", None])
def test_modalidad_desconocida_no_inventa_pesos(texto):
    assert norma_de(texto) is None


def test_calificaciones_en_orden_y_con_su_componente():
    assert [(c.codigo, c.componente) for c in CALIFICACIONES] == [
        ("C1_contacto", "contacto"), ("C3_formativa", "contacto"), ("C5_sumativa", "contacto"),
        ("C2_practicas", "practico"), ("C1_autonoma", "autonomo"), ("C4_proyecto", "autonomo")]


def test_una_tabla_que_no_suma_100_se_rechaza(tmp_path):
    tabla = json.loads((RAIZ / "backend" / "app" / "evaluacion" / "norma_rra.json").read_text(encoding="utf-8"))
    tabla["modalidades"]["presencial"]["pesos"]["C2_practicas"] = 35
    ruta = tmp_path / "norma.json"
    ruta.write_text(json.dumps(tabla), encoding="utf-8")
    with pytest.raises(NormaInvalida, match="presencial"):
        cargar_tabla(ruta)


def test_una_calificacion_desconocida_se_rechaza(tmp_path):
    tabla = json.loads((RAIZ / "backend" / "app" / "evaluacion" / "norma_rra.json").read_text(encoding="utf-8"))
    tabla["modalidades"]["en_linea"]["pesos"]["C9_extra"] = 0
    ruta = tmp_path / "norma.json"
    ruta.write_text(json.dumps(tabla), encoding="utf-8")
    with pytest.raises(NormaInvalida, match="C9_extra"):
        cargar_tabla(ruta)


# --- bloques por fecha -----------------------------------------------------------------------


def test_en_linea_es_un_solo_bloque_con_todas_las_sesiones():
    silabo = _silabo("EN LINEA")
    [b] = bloques(silabo, norma_de("EN LINEA"))
    assert (b.numero, b.nombre, b.sesiones) == (1, "Bloque único", ["M1-S1", "M1-S2", "M2-S4"])
    assert (b.inicio, b.fin) == (date(2026, 9, 29), date(2026, 10, 27))


def test_presencial_cierra_el_primer_parcial_en_su_prueba_acumulativa():
    """Como en PPC: el primer parcial cierra en la sesión de su prueba, aunque no sea el fin de un momento."""
    silabo = _silabo(textos={(0, 0): "Prueba acumulativa del primer parcial sobre fundamentos."})
    p1, p2 = bloques(silabo, norma_de("PRESENCIAL"))
    assert (p1.nombre, p1.sesiones, p1.fin) == ("Parcial 1", ["M1-S1"], date(2026, 9, 29))
    assert (p2.nombre, p2.sesiones, p2.inicio) == ("Parcial 2", ["M1-S2", "M2-S4"], date(2026, 10, 1))


def test_presencial_sin_prueba_reconocible_parte_por_la_mitad_del_periodo():
    p1, p2 = bloques(_silabo(), norma_de("PRESENCIAL"))
    assert p1.sesiones == ["M1-S1", "M1-S2"] and p2.sesiones == ["M2-S4"]


def test_una_prueba_del_primer_parcial_en_la_ultima_sesion_no_deja_vacio_el_segundo():
    silabo = _silabo(textos={(1, 0): "Prueba del primer parcial."})
    p1, p2 = bloques(silabo, norma_de("PRESENCIAL"))
    assert p1.sesiones == ["M1-S1", "M1-S2"] and p2.sesiones == ["M2-S4"]


def test_el_primer_hemiciclo_cierra_el_primer_parcial():
    """En Salud la prueba se llama «examen institucional del primer hemiciclo»."""
    silabo = _silabo(textos={(0, 0): "Examen institucional del primer hemiciclo."})
    p1, _ = bloques(silabo, norma_de("PRESENCIAL"))
    assert p1.sesiones == ["M1-S1"]


def test_sin_nombre_del_parcial_cierra_en_la_primera_prueba_sumativa_clasificada():
    """«Evaluación hemiciclo» no dice cuál: la clasificación (reglas o IA) marca dónde hay prueba sumativa."""
    p1, p2 = bloques(_silabo(), norma_de("PRESENCIAL"), sumativas=["M1-S1", "M2-S4"])
    assert p1.sesiones == ["M1-S1"] and p2.sesiones == ["M1-S2", "M2-S4"]
    # Una sumativa solo en la última sesión no sirve de cierre: se parte a la mitad.
    p1, p2 = bloques(_silabo(), norma_de("PRESENCIAL"), sumativas=["M2-S4"])
    assert p1.sesiones == ["M1-S1", "M1-S2"]


def test_semipresencial_pendiente_no_arma_bloques():
    assert bloques(_silabo("HIBRIDA"), norma_de("HIBRIDA")) == []
