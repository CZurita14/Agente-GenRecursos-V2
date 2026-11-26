"""Clasificación de actividades según el plan de evaluación del RRA (V3-3).

Los textos son los rótulos reales de los sílabos piloto B26. La prueba con el PDF de Electiva 5 compara contra
su plan de evaluación aprobado (13 actividades) y se salta si el PDF no está en el equipo.
"""
import glob
from pathlib import Path

import pytest

from app.evaluacion.clasificador import clasificar, clasificar_columna
from app.evaluacion.norma import norma_de

PRESENCIAL, EN_LINEA, HIBRIDA = norma_de("PRESENCIAL"), norma_de("EN LINEA"), norma_de("HIBRIDA")


def _una(columna, texto, norma=PRESENCIAL):
    [a] = clasificar_columna("M1-S1", columna, texto, norma)
    return a


def _plan(a):
    return (a.tipo, a.calificacion, a.instrumento, a.finalidad, a.agente)


@pytest.mark.parametrize("columna,texto,esperado", [
    ("docente", "Presentación del proyecto. Aplicación de la evaluación diagnóstica sobre HTML, CSS y JavaScript.",
     ("diagnostica", None, "prueba_objetiva", "diagnostica", "heteroevaluacion")),
    ("asincronica", "Foro virtual sobre buenas prácticas: cada estudiante analiza una aplicación y comenta a dos compañeros.",
     ("foro", "C1_contacto", "rubrica", "formativa", "coevaluacion")),
    ("docente", "Exposición dialogada sobre formularios. Aplicación de un cuestionario en plataforma sobre navegación.",
     ("cuestionario", "C3_formativa", "prueba_objetiva", "formativa", "heteroevaluacion")),
    ("asincronica", "Prueba acumulativa del segundo parcial, en línea, sobre gestión de datos.",
     ("prueba_sumativa", "C5_sumativa", "prueba_objetiva", "sumativa", "heteroevaluacion")),
    ("docente", "Estudio de caso: análisis guiado de una aplicación móvil real.",
     ("estudio_caso", "C1_contacto", "rubrica", "sumativa", "coevaluacion_y_heteroevaluacion")),
    ("practico", "Práctica de aprendizaje experimental 1: taller colaborativo de las vistas, con revisión entre pares.",
     ("practica_experimental", "C2_practicas", "rubrica", "formativa", "coevaluacion")),
    ("practico", "Práctica de aprendizaje experimental 2: laboratorio de gestión del estado con registro de resultados.",
     ("practica_experimental", "C2_practicas", "guia_observacion", "sumativa", "heteroevaluacion")),
    ("autonomo", "Ensayo breve: lectura crítica de una guía de diseño de interfaces móviles.",
     ("ensayo", "C1_autonoma", "rubrica", "formativa", "heteroevaluacion")),
    ("autonomo", "Portafolio digital de evidencias con reflexión sobre el propio aprendizaje.",
     ("portafolio", "C1_autonoma", "lista_cotejo", "formativa", "autoevaluacion")),
    ("autonomo", "Trabajo final: entrega de la aplicación compilada y del informe.",
     ("proyecto_final", "C4_proyecto", "rubrica", "sumativa", "heteroevaluacion")),
    ("autonomo", "Exposición oral del trabajo final por videoconferencia: demostración y sustentación.",
     ("exposicion_final", "C4_proyecto", "rubrica", "sumativa", "coevaluacion_y_heteroevaluacion")),
    ("autonomo", "Lectura guiada sobre los fundamentos de Git con cuestionario de comprensión.",
     ("cuestionario_autonomo", "C1_autonoma", "prueba_objetiva", "formativa", "heteroevaluacion")),
    ("autonomo", "Entrega de la versión corregida del prototipo con el registro de pruebas.",
     ("entrega_avance", "C4_proyecto", "lista_cotejo", "sumativa", "heteroevaluacion")),
])
def test_rotulos_del_plan_de_evaluacion(columna, texto, esperado):
    a = _una(columna, texto)
    assert a.evaluable and a.origen == "rotulo"
    assert _plan(a) == esperado


def test_en_linea_el_proyecto_final_va_a_la_sumativa():
    a = _una("autonomo", "Presentación del proyecto final por videoconferencia: demostración del prototipo.", EN_LINEA)
    assert (a.tipo, a.calificacion) == ("exposicion_final", "C5_sumativa")
    assert _una("autonomo", "Proyecto final: repositorio colaborativo documentado.", EN_LINEA).calificacion == "C5_sumativa"
    assert _una("autonomo", "Proyecto final: repositorio colaborativo documentado.", HIBRIDA).calificacion == "C4_proyecto"


@pytest.mark.parametrize("columna,texto", [
    ("practico", "Práctica guiada de construcción de formularios con validación."),
    ("docente", "Demostración del uso de funciones nativas del dispositivo con Capacitor."),
    ("autonomo", "Ajuste del prototipo navegable con los criterios de accesibilidad."),
    ("autonomo", "Recorrido del dataset con ciclos y acumuladores. Repaso de los contenidos para la prueba acumulativa."),
    ("practico", "Práctica 2, fase de desarrollo. El avance recibe retroalimentación y se califica junto con la entrega del 19-11."),
    ("docente", "Preparación de la sustentación técnica y ensayo breve por equipos, con retroalimentación entre pares."),
    ("asincronica", "Lectura guiada del expediente del caso y participación en el foro de presentación."),
])
def test_actividades_de_avance_no_se_califican(columna, texto):
    a = _una(columna, texto)
    assert (a.tipo, a.evaluable, a.calificacion, a.origen) == ("avance", False, None, "rotulo")


def test_una_columna_puede_traer_dos_evaluaciones_sin_duplicar_la_misma():
    tipos = [a.tipo for a in clasificar_columna(
        "M4-S8", "docente", "Prueba acumulativa del segundo parcial. Autoevaluación del trabajo en equipo.", PRESENCIAL)]
    assert tipos == ["prueba_sumativa", "autoevaluacion"]
    [practica] = clasificar_columna("M2-S6", "practico", "Práctica 2, entrega. Se entregan el diagrama y el archivo .py.",
                                    PRESENCIAL)
    assert practica.tipo == "practica_experimental"


def test_sin_rotulo_queda_como_avance_para_revisar_y_vacio_no_cuenta():
    a = _una("docente", "Mesa redonda con invitados del sector.")
    assert (a.tipo, a.evaluable, a.origen) == ("avance", False, "sin_rotulo")
    assert clasificar_columna("M1-S1", "autonomo", "  ", PRESENCIAL) == []


def test_un_rotulo_fuera_de_su_columna_no_se_califica():
    """«Ensayo» en la columna del docente es el ensayo de una presentación, no el ensayo escrito."""
    assert _una("docente", "Ensayo de la demostración del producto.").evaluable is False


# --- contra el plan aprobado de Electiva 5 (si el PDF está en el equipo) ---------------------------

PLAN_ELECTIVA_5 = {
    ("M1-S1", "diagnostica", "prueba_objetiva"), ("M1-S4", "foro", "rubrica"), ("M2-S2", "cuestionario", "prueba_objetiva"),
    ("M2-S4", "prueba_sumativa", "prueba_objetiva"), ("M3-S1", "estudio_caso", "rubrica"),
    ("M4-S4", "prueba_sumativa", "prueba_objetiva"), ("M2-S1", "practica_experimental", "rubrica"),
    ("M3-S1", "practica_experimental", "guia_observacion"), ("M4-S1", "practica_experimental", "rubrica"),
    ("M1-S4", "ensayo", "rubrica"), ("M3-S3", "portafolio", "lista_cotejo"), ("M4-S3", "proyecto_final", "rubrica"),
    ("M4-S4", "exposicion_final", "rubrica"),
}


def test_electiva_5_coincide_con_su_plan_de_evaluacion():
    pdfs = glob.glob(str(Path.home() / "Desktop" / "SILABOS B26" / "**" / "silabo_B26_Electiva5.pdf"), recursive=True)
    if not pdfs:
        pytest.skip("El PDF piloto de Electiva 5 no está en este equipo")
    pytest.importorskip("pdfplumber")
    from ciencia_datos.lector_pdf.a_v2 import leer_silabo_v2
    from ciencia_datos.migrar_validador import desde_v2
    from app.sga.traductor import a_contrato
    from app.silabo.integridad import cargar_silabo
    silabo = cargar_silabo(a_contrato(desde_v2(leer_silabo_v2(Path(pdfs[0]).read_bytes()))))
    evaluables = {(a.sesion, a.tipo, a.instrumento) for a in clasificar(silabo, norma_de(silabo.proyecto_formativo.modalidad))
                  if a.evaluable}
    assert evaluables == PLAN_ELECTIVA_5
