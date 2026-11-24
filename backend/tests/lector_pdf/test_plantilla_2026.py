"""Apartados de la plantilla 2026 y sílabo en JSON 2.0 desde el PDF, con tablas sintéticas."""
import os
from datetime import date
from pathlib import Path

import pytest

from ciencia_datos.migrar_v2 import migrar
from ciencia_datos.lector_pdf.momentos import leer_momentos
from ciencia_datos.lector_pdf.plantilla_2026 import leer_apartados_2026
from ciencia_datos.lector_pdf.presentacion import leer_cabecera
from app.sga import contrato_v2
from tests.lector_pdf.test_momentos import ENCABEZADO, INICIO, _cabecera, _cierre
from tests.lector_pdf.test_presentacion import PORTADA, TABLAS_II, TABLAS_III

REQUISITOS = [[["Proyectos formativos previos requeridos (prerrequisitos)"], ["Ninguno"],
               ["Proyectos formativos que se deben cursar paralelamente (correquisitos)"],
               ["METODOS NUMERICOS\nPROGRAMACION ESTRUCTURADA"]]]
NUEVAS_III = [
    [["Habilidades blandas"], ["• resolución de problemas\n• comunicación efectiva"]],
    [["Ejes transversales", ""], ["Eje", "Cómo se evidencia en las actividades del PF"],
     ["Interdisciplinariedad", "Integra estadística y\nprogramación"],
     ["Sostenibilidad - ODS", "Aporta al ODS 9 y al ODS 11"],
     ["", "continuación de la fila"],
     ["Internacionalización", "Clase espejo con una universidad"]],
    [["Inclusión y atención a las barreras para el aprendizaje y la participación"], ["Ajustes de tiempo"]],
    [["Contribución del proyecto formativo al perfil de la carrera"], ["Aporta al análisis de datos"]],
]


def test_requisitos():
    a = leer_apartados_2026(TABLAS_II + REQUISITOS, TABLAS_III + NUEVAS_III)
    assert a["prerrequisitos"] == []
    assert a["correquisitos"] == ["METODOS NUMERICOS", "PROGRAMACION ESTRUCTURADA"]
    assert a["formacion"] == "Pregrado"


def test_habilidades_inclusion_y_contribucion():
    a = leer_apartados_2026(TABLAS_II, TABLAS_III + NUEVAS_III)
    assert a["habilidades_blandas"] == ["resolución de problemas", "comunicación efectiva"]
    assert a["inclusion"] == "Ajustes de tiempo"
    assert a["contribucion_perfil"] == "Aporta al análisis de datos"


def test_ejes_por_fila_con_continuacion():
    e = leer_apartados_2026(TABLAS_II, TABLAS_III + NUEVAS_III)["ejes"]
    assert set(e) == {"interdisciplinariedad", "sostenibilidad_ods", "internacionalizacion"}
    assert e["interdisciplinariedad"]["descripcion"] == "Integra estadística y programación"
    assert e["sostenibilidad_ods"]["descripcion"] == "Aporta al ODS 9 y al ODS 11 continuación de la fila"
    assert e["sostenibilidad_ods"]["ods"] == [9, 11]
    assert e["internacionalizacion"]["tipo"] == "clase_espejo"


def test_sin_apartados_nuevos_queda_vacio():
    a = leer_apartados_2026(TABLAS_II, TABLAS_III)
    assert a == {"prerrequisitos": [], "correquisitos": [], "formacion": "Pregrado", "habilidades_blandas": [],
                 "ejes": {}, "inclusion": "", "contribucion_perfil": ""}


def test_contribucion_por_texto_si_la_tabla_mezcla_el_rotulo():
    mezclada = [[["Resultados de aprendizaje y evidencias", None, None],
                 ["Contribución el proyecto organizar", "x", "y"]]]
    texto = "\n".join(["Contribución del proyecto formativo al perfil de la carrera", "Aporta al análisis",
                       "de datos", "Problema del territorio", "Otra cosa"])
    a = leer_apartados_2026(TABLAS_II, TABLAS_III + mezclada, texto)
    assert a["contribucion_perfil"] == "Aporta al análisis de datos"


def test_problema_en_pagina_nueva_sin_rotulo():
    tablas = [t for t in TABLAS_III if not str(t[0][0]).startswith("Problema")] + [
        [[None, "En Ecuador, la creciente\nutilización"], ["Pregunta o reto", "¿Cómo estructurar?"],
         ["Evidencia de desempeño central\ndel PF (Producto final del PF)", "Portafolio"]]]
    p = leer_cabecera(PORTADA, TABLAS_II, tablas)["problema"]
    assert p == {"descripcion": "En Ecuador, la creciente utilización", "reto": "¿Cómo estructurar?",
                 "producto_final": "Portafolio"}


def test_ra_partido_entre_paginas():
    tablas = TABLAS_III + [[["Resultados de aprendizaje y evidencias", None, None],
                            ["RA", "Resultado de aprendizaje", "Evidencia de desempeño"],
                            ["", "sigue el RA2", "sigue la evidencia"]]]
    ras = leer_cabecera(PORTADA, TABLAS_II, tablas)["resultados_aprendizaje"]
    assert ras[1] == {"id": "RA2", "texto": "Aplica técnicas sigue el RA2", "evidencia": "Un esquema de reglas sigue la evidencia"}


def test_momento_y_sesion_sin_fecha():
    cab = _cabecera()
    cab[1] = ["Fecha", None, "Por definir", None, None, None, None, None, None]
    sesion = ["Sesión 1\nPor definir", "Clase", None, "2.0", "Práctica", "1.0", "Tarea", "1.0", "• Tema"]
    m = leer_momentos([cab + [sesion] + _cierre()], INICIO)[0]
    assert (m["fecha_inicio"], m["fecha_fin"]) == (None, None)
    assert m["sesiones"][0]["fecha"] is None and m["sesiones"][0]["semana_periodo"] is None


def test_migrar_con_apartados_cumple_reglas_2():
    base = leer_cabecera(PORTADA, TABLAS_II, TABLAS_III)
    base |= {"momentos": [], "rubrica_producto_final": [], "bibliografia": {"basica": [], "complementaria": []},
             # La tabla sintética recorta la opción; en un sílabo real viene completa (una de las 5 del catálogo).
             "metacompetencia": "Pensamiento sociocrítico y sistémico para la toma de decisiones estratégicas"}
    a = leer_apartados_2026(TABLAS_II + REQUISITOS, TABLAS_III + NUEVAS_III)
    v2 = migrar(base, apartados=a)
    assert contrato_v2.reglas(v2) == []
    assert v2["habilidades_blandas"] == a["habilidades_blandas"]
    assert v2["proyecto_formativo"]["correquisitos"] == a["correquisitos"]
    assert v2["inclusion"] == "Ajustes de tiempo"
    assert v2["ejes_transversales"]["sostenibilidad_ods"]["ods"] == [9, 11]
    assert v2["ejes_transversales"]["emprendimiento"] == {"aplica": True, "descripcion": "", "justificacion_na": ""}
    assert [c["tipo"] for c in v2["metodologias"]["complementarias"]] == ["aprendizaje_basado_problemas"]


CARPETA_2026 = os.environ.get("SILABOS_2026_DIR")


@pytest.mark.skipif(not CARPETA_2026, reason="SILABOS_2026_DIR no apunta a los PDF de la plantilla 2026")
def test_pdf_reales_2026_salen_en_contrato_2():
    from ciencia_datos.lector_pdf.a_v2 import leer_silabo_v2
    pdfs = sorted(Path(CARPETA_2026).glob("*.pdf"))
    assert pdfs
    for pdf in pdfs:
        v2 = leer_silabo_v2(pdf.read_bytes())
        assert v2["contrato"] == "2.0"
        # Solo sí/no en los mensajes: nunca texto del sílabo.
        leidos = {"habilidades": bool(v2["habilidades_blandas"]), "contribucion": bool(v2["contribucion_perfil"]),
                  "ejes": any(e["descripcion"] for e in v2["ejes_transversales"].values())}
        assert all(leidos.values()), (pdf.name, leidos)
