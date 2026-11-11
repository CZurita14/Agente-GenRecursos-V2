"""P6b T2: HTML autónomo para Canvas (spec §13): escapado, sin recursos externos y con el pie."""
from html import escape
import re

import pytest

from app.exportar.html import PIE, cabecera_descarga, exportar_html, nombre_archivo
from app.herramientas.sin_ia import generar_sin_ia
from app.silabo.contexto import contexto_clase, contexto_por_id
from tests.test_generacion_api import HEADERS, entorno  # noqa: F401

MALICIOSO = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'


def _item(i, pregunta="¿Qué prueba corresponde?"):
    return {"item_id": f"i{i}", "nivel": "resolutivo", "foco": "f", "ra": "RA2", "contenido": "C",
            "contexto": "Una empresa ficticia mide tiempos.", "pregunta": pregunta, "correcta": 1,
            "opciones": [{"texto": f"Opción {k}", "justificacion": f"Porque {k}", "error_que_representa": "e"}
                         for k in range(4)], "razonamiento": ["a", "b"]}


def _recurso(herramienta, contenido, ambito="M2-S1"):
    return {"herramienta": herramienta, "ambito_id": ambito, "contenido": contenido}


def test_html_del_estudiante_no_contiene_respuestas(silabo):
    html = exportar_html(_recurso("cuestionario", [_item(1), _item(2)]), contexto_clase(silabo, "M2-S1"))
    assert html.startswith("<!DOCTYPE html>")
    assert not re.search(r"\b(src|href)\s*=\s*[\"']?https?:", html)  # Sin recursos externos.
    assert "Opción 3" in html and html.count('type="radio"') == 8
    for rastro in ("data-correcta", "data-justificacion", "data-clave", "Porque 2", "data-entregar", "data-puntaje", "<details"):
        assert rastro not in html, rastro


def test_html_escapa_contenido(silabo):
    html = exportar_html(_recurso("cuestionario", [_item(1, pregunta=MALICIOSO)]), contexto_clase(silabo, "M2-S1"))
    assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x" not in html and "onerror=alert(2)>" not in html


def test_html_pie_y_politica(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    html = exportar_html(_recurso("cuestionario", [_item(1)]), ctx)
    assert PIE == "Recurso generado con asistencia de IA y revisado por el docente"
    assert PIE in html and ctx.asignatura in html and "Momento 2, sesión 1" in html
    assert ctx.politica_ia[:40] in html and f"Resultado de aprendizaje {ctx.ra[0].id[2:]}" in html


def test_html_secciones(silabo):
    ficha = {"conceptual": {"ideas_clave": ["Idea A", "Idea B"], "relacion_ra": "Se relaciona", "errores_frecuentes": ["E1"]},
             "aplicacion": {"ejemplo": {"enunciado": "Enun", "pasos": ["P1"], "resultado": "R"}, "autocomprobacion": ["Q1"]}}
    html = exportar_html(_recurso("ficha_clase", ficha), contexto_clase(silabo, "M2-S1"))
    assert "Ideas clave" in html and "<li>Idea A</li>" in html and "Autocomprobación" in html
    assert html.index("Ideas clave") < html.index("Ejemplo resuelto") < html.index("Autocomprobación")
    assert "<ol><li>P1</li></ol>" in html
    hoja = generar_sin_ia("hoja_ruta", silabo, "asignatura")
    html = exportar_html(_recurso("hoja_ruta", hoja, "asignatura"), contexto_por_id(silabo, "asignatura"))
    assert "Calendario de clases" in html and "<table style=\"border-collapse: collapse;" in html and "numero_clase" not in html.lower() and silabo.problema.producto_final[:30] in html


def _producir_validado(entorno):
    _, _, d, aid, producir = entorno
    recurso = producir()
    r = d.post(f"/asignaturas/{aid}/recursos/{recurso['id']}/validar", json={"revision": recurso["revision"]}, headers=HEADERS)
    assert r.status_code == 200
    return d, aid, recurso


def test_exportar_sin_validar_409(entorno):
    _, _, d, aid, producir = entorno
    recurso = producir()
    assert d.get(f"/asignaturas/{aid}/recursos/{recurso['id']}/exportar?formato=html").status_code == 409


def test_exportar_validado_200_attachment(entorno):
    d, aid, recurso = _producir_validado(entorno)
    r = d.get(f"/asignaturas/{aid}/recursos/{recurso['id']}/exportar?formato=html")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    disposicion = r.headers["content-disposition"]
    assert disposicion.startswith("attachment") and "filename*=UTF-8''Cuestionario%20-%20Momento%202%2C%20sesi%C3%B3n%201%20-%20" in disposicion
    assert 'filename="Cuestionario - Momento 2, sesion 1 - ' in disposicion and "M2-S1" not in disposicion
    assert PIE in r.text


def test_formato_no_soportado_422(entorno):
    d, aid, recurso = _producir_validado(entorno)
    assert d.get(f"/asignaturas/{aid}/recursos/{recurso['id']}/exportar?formato=qti").status_code == 422


# --- Herramientas interactivas: lo que el estudiante usa, no solo lee ---

def test_autoevaluacion_interactiva(silabo):
    c = generar_sin_ia("autoevaluacion_rubrica", silabo, "M2")
    html = exportar_html(_recurso("autoevaluacion_rubrica", c, "M2"), contexto_por_id(silabo, "M2"))
    assert html.count(" data-autoev>") == len(c["indicadores"])
    assert 'type="radio"' in html and "data-subir=" in html and "data-resumen" in html
    # El descriptor del siguiente nivel viaja escapado para mostrarlo al marcar.
    f = c["indicadores"][0]
    assert escape(f["para_subir"]["receptivo"], quote=True) in html


def test_lista_evidencia_con_casillas(silabo):
    c = generar_sin_ia("lista_evidencia", silabo, "M3")
    html = exportar_html(_recurso("lista_evidencia", c, "M3"), contexto_por_id(silabo, "M3"))
    assert html.count('type="checkbox"') == len(c["entregables"]) + len(c["items"])
    assert "data-lista" in html and "data-avance" in html


def test_estudio_caso_sin_respuesta_ni_escenario(silabo):
    c = {"caso": {"escenario": "ESCENARIO-INTERNO", "caso": "Un caso", "ra": "RA2",
                  "preguntas": [{"nivel": "critico", "pregunta": "¿Por qué?", "respuesta_orientativa": "Porque sí"}]}}
    html = exportar_html(_recurso("estudio_caso", c, "M2"), contexto_por_id(silabo, "M2"))
    assert "<textarea" in html and "Porque sí" not in html and "Respuesta orientativa" not in html
    assert "ESCENARIO-INTERNO" not in html


def test_interactivas_escapan_contenido(silabo):
    c = {"caso": {"caso": MALICIOSO, "ra": "RA2", "preguntas": [
        {"nivel": "critico", "pregunta": MALICIOSO, "respuesta_orientativa": MALICIOSO}]}}
    html = exportar_html(_recurso("estudio_caso", c, "M2"), contexto_por_id(silabo, "M2"))
    assert "<script>alert(1)" not in html and "<img src=x" not in html
    a = generar_sin_ia("autoevaluacion_rubrica", silabo, "M2")
    a["indicadores"][0]["para_subir"]["receptivo"] = MALICIOSO
    html = exportar_html(_recurso("autoevaluacion_rubrica", a, "M2"), contexto_por_id(silabo, "M2"))
    assert "<script>alert(1)" not in html and "onerror=alert(2)>" not in html


def test_forma_anterior_se_muestra_sin_interaccion(silabo):
    html = exportar_html(_recurso("estudio_caso", {"otra": "Texto del docente"}, "M2"), contexto_por_id(silabo, "M2"))
    assert "Texto del docente" in html


def test_simulacro_del_estudiante_sin_solucionario(silabo):
    html = exportar_html(_recurso("simulacro", [_item(1), _item(2)], "M2"), contexto_por_id(silabo, "M2"))
    assert "Ver solucionario" not in html and "Porque 1" not in html and "data-entregar" not in html


def test_marcables_y_resultado_ocultable(silabo):
    ficha = {"conceptual": {"ideas_clave": ["A"], "relacion_ra": "R", "errores_frecuentes": ["E"]},
             "aplicacion": {"ejemplo": {"enunciado": "En", "pasos": ["P"], "resultado": "Res"}, "autocomprobacion": ["Q1", "Q2"]}}
    html = exportar_html(_recurso("ficha_clase", ficha), contexto_clase(silabo, "M2-S1"))
    assert html.count('type="checkbox"') == 2 and "<summary>Ver el resultado</summary><p>Res</p>" in html


def test_html_sin_codigos_internos(silabo):
    item = _item(1, pregunta="Según RA2, ¿qué se aplica en M2-S1 y en M3 para los RA del curso?")
    html = exportar_html(_recurso("cuestionario", [item]), contexto_clase(silabo, "M2-S1"))
    assert "Según Resultado de aprendizaje 2" in html and "Momento 2, sesión 1 y en Momento 3" in html
    assert "los resultados de aprendizaje del curso" in html
    assert not re.search(r"\\b(M\\d+-S\\d+|M\\d+|RA\\d*)\\b", html.split("<main>")[1].split("<script>")[0])


def test_asignatura_no_repite_el_titulo(silabo):
    ctx = contexto_por_id(silabo, "asignatura")
    html = exportar_html(_recurso("rubrica_final", generar_sin_ia("rubrica_final", silabo, "asignatura"), "asignatura"), ctx)
    assert f"{ctx.asignatura} · {ctx.asignatura}" not in html


@pytest.mark.parametrize("herramienta,ambito", [("rubrica_momento", "M2"), ("rubrica_final", "asignatura")])
def test_rubrica_es_la_del_silabo(silabo, herramienta, ambito):
    c = generar_sin_ia(herramienta, silabo, ambito)
    fuente = silabo.rubrica_producto_final if ambito == "asignatura" else next(m for m in silabo.momentos if m.numero == 2).rubrica
    assert [f["indicador"] for f in c["indicadores"]] == [f.indicador for f in fuente]
    assert all(f["descriptores"]["resolutivo"] == g.niveles.get("resolutivo", "") for f, g in zip(c["indicadores"], fuente))
    html = exportar_html(_recurso(herramienta, c, ambito), contexto_por_id(silabo, ambito))
    assert "<table style=\"border-collapse: collapse;" in html and "Resolutivo" in html and "data-imprimir" in html


def test_generar_no_duplica_lo_que_esta_en_curso(entorno):
    _, _, d, aid, _ = entorno
    cuerpo = {"ambito": {"tipo": "clase", "id": "M2-S1"}, "herramientas": ["ficha_clase"]}
    r1 = d.post(f"/asignaturas/{aid}/generar", json=cuerpo, headers=HEADERS).json()["trabajos"][0]
    r2 = d.post(f"/asignaturas/{aid}/generar", json=cuerpo, headers=HEADERS).json()["trabajos"][0]
    assert r1["id"] == r2["id"]
    otro = d.post(f"/asignaturas/{aid}/generar", json={**cuerpo, "herramientas": ["cuestionario", "ficha_clase"]}, headers=HEADERS).json()["trabajos"]
    assert otro[0]["id"] != r1["id"] and otro[1]["id"] == r1["id"]


@pytest.mark.parametrize("herramienta,ambito,formato,esperado", [
    ("ficha_clase", "M2-S1", "pdf", "Ficha de clase - Momento 2, sesión 1 - Analisis de datos.pdf"),
    ("rubrica_final", "asignatura", "docx", "Rúbrica del producto final - Analisis de datos.docx"),
    ("cuestionario", "M1-S1", "html", "Cuestionario - Momento 1, sesión 1 - Analisis de datos.html"),
])
def test_nombre_de_archivo_claro(herramienta, ambito, formato, esperado):
    assert nombre_archivo(herramienta, ambito, "ANALISIS DE DATOS", formato) == esperado


def test_nombre_de_archivo_seguro():
    malo = nombre_archivo("ficha_clase", "M1-S1", 'A/../b"\r\nX-Mala: 1<>|', "pdf")
    assert not re.search(r'[/\\:*?"<>|\r\n]', malo)
    cabecera = cabecera_descarga(malo)
    assert "\r" not in cabecera and "\n" not in cabecera and cabecera.isascii()


def test_cabecera_no_se_rompe_al_normalizar():
    """Caracteres de ancho completo pasan el primer filtro y NFKD los vuelve comillas o barras."""
    nombre = nombre_archivo("ficha_clase", "M1-S1", "A\uff02; filename=\uff02mala.exe\uff3c\uff0f", "pdf")
    cabecera = cabecera_descarga(nombre)
    assert cabecera.count('"') == 2 and "\\" not in cabecera
    valor = cabecera.split('filename="')[1].split('"')[0]
    assert ";" not in valor and "/" not in valor
    assert cabecera.count("; filename=") == 1 and cabecera.count("; filename*=") == 1  # Lo demás queda dentro de las comillas.


def test_archivo_del_docente_se_distingue():
    assert nombre_archivo("cuestionario", "M1-S1", "DATOS", "pdf", docente=True) == "Respuestas - Cuestionario - Momento 1, sesión 1 - Datos.pdf"


def test_html_usa_la_plantilla_institucional(silabo):
    """Tabla institucional con estilos en línea (Canvas quita <style>), sus filas y el botón al inicio del curso."""
    ctx = contexto_clase(silabo, "M2-S1")
    html = exportar_html(_recurso("cuestionario", [_item(1)]), ctx)
    assert "linear-gradient(135deg, #3A1467 0%, #230C3E 100%)" in html and "border-bottom: 5px solid #F37121" in html
    filas = ["RESULTADO DE APRENDIZAJE RELACIONADO", "¿Para qué realizas esta actividad?",
             "Caso, problema o reto del territorio", "Instrucciones", "Cuestionario", "Recurso que debes utilizar",
             "Evidencia o producto", "Evaluación", "Condiciones de entrega"]
    cuerpo = html.split("<main>")[1]
    posiciones = [cuerpo.index(f"color: #3a1467;\">{f}</span>") for f in filas]
    assert posiciones == sorted(posiciones)
    assert 'href="../pages/inicio">Inicio del curso</a>' in html and "Rúbrica de evaluación Acceder" in html
    assert ctx.problema.reto[:30] in html
