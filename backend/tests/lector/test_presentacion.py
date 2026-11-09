"""Portada, presentación (II) y mapa de formación (III) con tablas sintéticas (P2, Tarea 2)."""
from datetime import date

from app.silabo.lector.presentacion import leer_cabecera

PORTADA = """Facultad:
FACULTAD DE INGENIERIAS
Carrera:
SOFTWARE
Periodo académico:
B26
Inicio: 2026-10-05
Fin: 2027-03-01
Proyecto formativo:
ANALISIS DE DATOS Y ESTADISTICA PARA INGENIERIA
B26-SOFT-3-56146-1727
Versión:
v. 1.0 (APROBADA EL 06/10/2026)
Docente:
NOMBRE FICTICIO DEL DOCENTE
Estructura del sílabo:
I. PERFIL DEL DOCENTE"""

TABLAS_II = [
    [["Nombre", None, None, "ANALISIS DE DATOS Y ESTADISTICA PARA INGENIERIA", None, None, None, None, None],
     ["Unidad de organización curricular", None, None, "TITULACION", None, None, None, None, None],
     ["Créditos", "Horas", "Periodo académico", None, None, "Nivel", "Modalidad", None, "Nivel de formación"],
     ["3.00", "144.0", "B26", None, None, "3RO NIVEL", "EN LINEA", None, "Pregrado"],
     ["Aprendizaje en contacto con el\ndocente", None, None, None, "Aprendizaje autónomo", None, None,
      "Aprendizaje práctico-experimental", None],
     ["72.0", None, None, None, "24.0", None, None, "48.0", None]],
    [["Horario de aprendizaje en contacto con el docente"], ["Miércoles 20:00 a 20:59\nJueves 20:00 a 20:59"],
     ["Horario de aprendizaje práctico-experimental"], ["Sin horario registrado"]],
]

TABLAS_III = [
    [["Competencia específica del perfil de egreso de la carrera"], ["ADMINISTRA BASES DE DATOS,\nPARA GARANTIZAR"]],
    [["Competencia específica del proyecto formativo"], [""]],
    [["Metacompetencia transversal"], ["( ) Gobernanza ética\n(X) Pensamiento sociocrítico y sistémico"]],
    [["Resultados de aprendizaje y evidencias", None, None],
     ["RA", "Resultado de aprendizaje", "Evidencia de desempeño"],
     ["RA1", "Comprende los\nprincipios", "Una base de datos\nsimulada"],
     ["RA2", "Aplica técnicas", "Un esquema de reglas"]],
    [["Problema del territorio", None],
     ["Problema, necesidad u\noportunidad", "En Ecuador, la creciente\nutilización"],
     ["Pregunta o reto", "¿Cómo estructurar\nlos datos?"],
     ["Evidencia de desempeño central\ndel PF (Producto final del PF)", "Portafolio de Análisis"]],
    [["Proyecto interdisciplinario socioformativo"], ["Desarrollo de soluciones"],
     ["Aporte del proyecto formativo al proyecto interdisciplinario socioformativo"], ["Este módulo aporta"]],
    [["Metodología activa"], ["• Clase Invertida\n• Aprendizaje Basado en Problemas (ABP)"]],
]


def test_cabecera_completa():
    c = leer_cabecera(PORTADA, TABLAS_II, TABLAS_III)
    assert (c["facultad"], c["carrera"]) == ("FACULTAD DE INGENIERIAS", "SOFTWARE")
    assert c["periodo"] == {"codigo": "B26", "inicio": date(2026, 10, 5), "fin": date(2027, 3, 1)}
    pf = c["proyecto_formativo"]
    assert (pf["nombre"], pf["codigo"], pf["version"], pf["aprobado"]) == (
        "ANALISIS DE DATOS Y ESTADISTICA PARA INGENIERIA", "B26-SOFT-3-56146-1727", "1.0", date(2026, 10, 6))
    assert (pf["uoc"], pf["nivel"], pf["modalidad"], pf["creditos"]) == ("TITULACION", 3, "EN LINEA", 3.0)
    assert pf["horas"] == {"total": 144.0, "contacto": 72.0, "autonomo": 24.0, "practico": 48.0}
    assert pf["horario"] == [{"dia": "miercoles", "inicio": "20:00", "fin": "20:59"},
                             {"dia": "jueves", "inicio": "20:00", "fin": "20:59"}]
    assert c["competencia_perfil"] == "ADMINISTRA BASES DE DATOS, PARA GARANTIZAR"
    assert c["competencia_pf"] == ""
    assert c["metacompetencia"] == "Pensamiento sociocrítico y sistémico"
    assert c["resultados_aprendizaje"] == [
        {"id": "RA1", "texto": "Comprende los principios", "evidencia": "Una base de datos simulada"},
        {"id": "RA2", "texto": "Aplica técnicas", "evidencia": "Un esquema de reglas"}]
    assert c["problema"] == {"descripcion": "En Ecuador, la creciente utilización",
                             "reto": "¿Cómo estructurar los datos?", "producto_final": "Portafolio de Análisis"}
    assert c["pis"] == {"nombre": "Desarrollo de soluciones", "aporte": "Este módulo aporta"}
    assert c["metodologias"] == ["Clase Invertida", "Aprendizaje Basado en Problemas (ABP)"]


def test_no_lee_el_docente_de_la_portada():
    assert "FICTICIO" not in repr(leer_cabecera(PORTADA, TABLAS_II, TABLAS_III))


def test_tablas_en_otro_orden():
    # Se localizan por rótulo, no por posición.
    c = leer_cabecera(PORTADA, list(reversed(TABLAS_II)), list(reversed(TABLAS_III)))
    assert c["proyecto_formativo"]["nivel"] == 3 and c["pis"]["aporte"] == "Este módulo aporta"


def test_portada_con_otra_grafia_de_docente():
    portada = PORTADA.replace("Docente:", "DOCENTES:")
    assert "FICTICIO" not in repr(leer_cabecera(portada, TABLAS_II, TABLAS_III))
