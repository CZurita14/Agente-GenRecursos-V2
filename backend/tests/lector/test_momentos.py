"""Momentos, sesiones y rúbricas con tablas sintéticas (P2, Tarea 3)."""
from datetime import date

from app.silabo.lector.momentos import leer_momentos, leer_rubrica

INICIO = date(2026, 10, 5)
ENCABEZADO = ["Sesión -\nfecha", "Actividades con el\ndocente", None, "Hora\ns", "Actividades práctico-\nexperimentales",
              "Hora\ns", "Trabajo autónomo", "Hora\ns", "Contenidos"]
RUBRICA = [
    ["Rúbrica de evaluación", None, None, None, None, None, None],
    ["Evidencia de desempeño del momento (producto\nesperado)", None, None, "Resultado de aprendizaje", None, None, None],
    ["Dataset…", None, None, "RA1: Comprende…", None, None, None],
    ["Indicador", "Receptivo", "Resolutivo", None, "Reflexivo", "Crítico", "Cocreativo"],
    ["Estructuración", "r1", "s1", None, "f1", "c1", "o1"],
    ["Reporte en\nJASP", "r2", "s2", None, "f2", "c2", "o2"],
    ["Línea base", "r3", "s3", None, "f3", "c3", "o3"],
]


def _cabecera(numero=1, titulo="Momento 1: Sensibilización - Análisis.", ras="RA1"):
    return [
        [f"Momento {numero}", None, titulo, None, None, None, None, None, None],
        ["Fecha", None, "07/10/2026 al 08/10/2026", None, None, None, None, None, None],
        ["Resultados de\naprendizaje", None, ras, None, None, None, None, None, None],
        ["Evidencia de\ndesempeño\n(producto esperado)", None, "Dataset de\nEventos", None, None, None, None, None, None],
        ENCABEZADO,
    ]


def _cierre():
    return [["Total", "", None, "12.0", "", "8.0", "", "4.0", ""],
            ["Recursos para el aprendizaje", None, "Escenarios:\nentorno virtual", None, None, None, None, None, None],
            ["Política de gobernanza crítica y\nética de la IA", None, "Se autoriza la IA\ncon auditoría.",
             None, None, None, None, None, None]]


SESION_1 = ["Sesión 1\n07/10/2026", "Clase virtual\nenseñando JASP", None, "6.0", "Práctica JASP", "4.0",
            "TAREA 1 – infografía", "2.0", "• Datos unidimensionales"]


def test_sesion_basica():
    [m] = leer_momentos([_cabecera() + [SESION_1] + _cierre(), RUBRICA], INICIO)
    assert (m["numero"], m["titulo"]) == (1, "Sensibilización - Análisis.")
    assert (m["fecha_inicio"], m["fecha_fin"], m["ra"]) == (date(2026, 10, 7), date(2026, 10, 8), ["RA1"])
    assert m["evidencia"] == "Dataset de Eventos"
    assert m["recursos"] == "Escenarios: entorno virtual"
    assert m["politica_ia"] == "Se autoriza la IA con auditoría."
    [s] = m["sesiones"]
    assert (s["id"], s["numero"], s["fecha"], s["semana_periodo"]) == ("M1-S1", 1, date(2026, 10, 7), 1)
    assert s["docente"] == {"texto": "Clase virtual enseñando JASP", "horas": 6.0, "asincronica": None}
    assert s["practico"] == {"texto": "Práctica JASP", "horas": 4.0}
    assert s["autonomo"] == {"texto": "TAREA 1 – infografía", "horas": 2.0}
    assert s["contenidos"] == ["Datos unidimensionales"]
    assert s["entregables"] == ["TAREA 1"]


def test_fila_partida_se_une():
    # La fila abierta al pie trae «Sesión 1»; la continuación (página siguiente) no.
    continuacion = ["", "estadística\ndescriptiva.", None, "", "(CSV/Excel)", "", "para el proyecto", "",
                    "Tasas de\nvariación."]
    tablas = [_cabecera() + [SESION_1], [ENCABEZADO, continuacion] + _cierre()]
    [m] = leer_momentos(tablas, INICIO)
    [s] = m["sesiones"]
    assert s["docente"]["texto"] == "Clase virtual enseñando JASP estadística descriptiva."
    assert s["practico"]["texto"] == "Práctica JASP (CSV/Excel)"
    assert s["contenidos"] == ["Datos unidimensionales Tasas de variación."]


def test_columnas_por_palabra_clave():
    otro = ["Sesión -\nfecha", "Actividades con el\ndocente", None, None, "Hora\ns",
            "Actividades práctico-\nexperimentales", "Hora\ns", "Actividades de trabajo autónomo", "Hora\ns", "Contenidos"]
    fila = ["Sesión 1\n07/10/2026", "Clase", None, None, "6.0", "Práctica", "4.0", "Autónomo", "2.0", "• Datos"]
    tablas = [_cabecera()[:-1] + [otro, fila] + _cierre()]
    [s] = leer_momentos(tablas, INICIO)[0]["sesiones"]
    assert (s["docente"]["horas"], s["practico"]["texto"], s["autonomo"]["texto"]) == (6.0, "Práctica", "Autónomo")


def test_asincronica_separada():
    fila = list(SESION_1)
    fila[1] = "sobre el uso de Numiqo\nOtras actividades con el\ndocente (5.0 h):\nasincrónicas en\nplataforma."
    [s] = leer_momentos([_cabecera() + [fila] + _cierre()], INICIO)[0]["sesiones"]
    assert s["docente"] == {"texto": "sobre el uso de Numiqo", "horas": 6.0,
                            "asincronica": {"texto": "asincrónicas en plataforma.", "horas": 5.0}}


def test_rubrica_cinco_niveles():
    [m] = leer_momentos([_cabecera() + [SESION_1] + _cierre(), RUBRICA], INICIO)
    assert [f["indicador"] for f in m["rubrica"]] == ["Estructuración", "Reporte en JASP", "Línea base"]
    assert m["rubrica"][1]["niveles"] == {"receptivo": "r2", "resolutivo": "s2", "reflexivo": "f2",
                                          "critico": "c2", "cocreativo": "o2"}


def test_rubrica_partida_entre_paginas():
    filas = RUBRICA[3:5] + [["", "más r1", "", None, "", "", ""]]
    assert leer_rubrica(filas)[0]["niveles"]["receptivo"] == "r1 más r1"


def test_latex_intacto():
    fila = list(SESION_1)
    fila[8] = "• HIPÓTESIS con\n$H_0/H_1$"
    [s] = leer_momentos([_cabecera() + [fila] + _cierre()], INICIO)[0]["sesiones"]
    assert s["contenidos"] == ["HIPÓTESIS con $H_0/H_1$"]


def test_fila_total_se_ignora_y_varios_momentos():
    segundo = _cabecera(2, "Momento 2: Planeación.", "RA2, RA3")
    fila2 = ["Sesión 1\n14/10/2026", "Clase", None, "6.0", "", "0", "", "", "• Distribuciones\n• Bayes"]
    [m1, m2] = leer_momentos([_cabecera() + [SESION_1] + _cierre(), RUBRICA, segundo + [fila2] + _cierre()], INICIO)
    assert len(m1["sesiones"]) == 1 and m2["ra"] == ["RA2", "RA3"]
    s = m2["sesiones"][0]
    assert (s["id"], s["semana_periodo"], s["practico"], s["contenidos"]) == (
        "M2-S1", 2, {"texto": "", "horas": 0.0}, ["Distribuciones", "Bayes"])
    assert m2["rubrica"] == []


# --- Revisión final: robustez ---------------------------------------------------
import pytest  # noqa: E402

from app.silabo.lector import SilaboIlegible  # noqa: E402


def test_encabezado_horas_docente_no_roba_el_rol():
    enc = ["Sesión -\nfecha", "Actividades con el\ndocente", "Horas docente", "Actividades práctico-\nexperimentales",
           "Horas", "Trabajo autónomo", "Horas", "Contenido de la sesión"]
    fila = ["Sesión 1\n07/10/2026", "Clase", "6.0", "Práctica", "4.0", "Autónomo", "2.0", "• Datos"]
    [s] = leer_momentos([_cabecera()[:-1] + [enc, fila] + _cierre()], INICIO)[0]["sesiones"]
    assert s["docente"] == {"texto": "Clase", "horas": 6.0, "asincronica": None}
    assert s["contenidos"] == ["Datos"]


def test_columnas_irreconocibles_dan_silabo_ilegible():
    enc = ["Sesión -\nfecha", "Actividad", "Hora", "Otra", "Hora", "Contenidos"]
    with pytest.raises(SilaboIlegible):
        leer_momentos([_cabecera()[:-1] + [enc, ["Sesión 1\n07/10/2026", "a", "1", "b", "2", "c"]]], INICIO)


def test_rubrica_no_absorbe_tablas_ajenas():
    ajena = [["Observaciones generales del docente", "texto libre"]]
    [m] = leer_momentos([_cabecera() + [SESION_1] + _cierre(), RUBRICA, ajena], INICIO)
    assert [f["indicador"] for f in m["rubrica"]] == ["Estructuración", "Reporte en JASP", "Línea base"]


def test_sesion_con_celda_partida_no_se_pierde_en_silencio():
    partida = ["Sesión 2", "Clase", None, "6.0", "", "", "", "", "• X"]
    with pytest.raises(SilaboIlegible):
        leer_momentos([_cabecera() + [SESION_1, partida] + _cierre()], INICIO)


def test_politica_partida_entre_paginas_se_une():
    # TIC M3: la fila de la política empieza al pie y sigue en la página siguiente.
    cierre = _cierre()[:2] + [["Política de gobernanza crítica y\nética de la IA", None,
                               "SE PERMITE LA IA COMO APOYO", None, None, None, None, None, None]]
    continuacion = [["", None, "PARA IDENTIFICAR RIESGOS.", None, None, None, None, None, None]]
    [m] = leer_momentos([_cabecera() + [SESION_1] + cierre, continuacion, RUBRICA], INICIO)
    assert m["politica_ia"] == "SE PERMITE LA IA COMO APOYO PARA IDENTIFICAR RIESGOS."
    assert m["recursos"] == "Escenarios: entorno virtual"
