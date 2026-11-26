"""Clasificación de las actividades del sílabo según el plan de evaluación del RRA (V3-3).

Cada columna de cada sesión (con el docente, otras actividades con el docente, práctico-experimental y
autónomo) se lee por sus rótulos institucionales («Foro…», «Práctica de aprendizaje experimental…»,
«Prueba acumulativa…», «Portafolio…»). Una actividad evaluable lleva su calificación del RRA, su instrumento
y su tipo de evaluación; las de avance («Práctica guiada…», «Demostración…», «Ajuste…») no se califican.

La calificación del proyecto final depende de la modalidad: en línea y a distancia va a la sumativa (C5);
en presencial, al proyecto integrador (C4). Una columna sin rótulo reconocible queda como avance con
`origen="sin_rotulo"`, para que la IA o el docente la revisen.
"""
import re
import unicodedata
from dataclasses import dataclass

from app.evaluacion.norma import Norma
from app.silabo.modelo import SilaboUTI

COLUMNAS = ("docente", "asincronica", "practico", "autonomo")


@dataclass(frozen=True)
class Actividad:
    sesion: str  # M1-S4
    columna: str  # docente | asincronica | practico | autonomo
    tipo: str
    evaluable: bool
    calificacion: str | None  # C1_contacto … C4_proyecto; None en la diagnóstica y en las de avance
    instrumento: str | None
    finalidad: str | None  # diagnostica | formativa | sumativa
    agente: str | None  # heteroevaluacion | coevaluacion | autoevaluacion | coevaluacion_y_heteroevaluacion
    origen: str  # rotulo | sin_rotulo


def _plano(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()


def _r(patron: str) -> re.Pattern:
    return re.compile(patron)


# (tipo, patrón, columnas donde vale o None para todas). El orden importa: el primero que coincide
# en una columna excluye a los que dicen lo mismo (p. ej., una práctica que «se entrega» no es otra entrega).
_REGLAS: tuple[tuple[str, re.Pattern, tuple[str, ...] | None], ...] = (
    ("diagnostica", _r(r"EVALUACION DIAGNOSTICA|PRUEBA DIAGNOSTICA"), None),
    # «Repaso… para la prueba acumulativa» prepara la prueba; no es la prueba.
    ("prueba_sumativa", _r(r"(?<!PARA LA )(?:PRUEBA (?:ACUMULATIVA|PARCIAL)|PRUEBA DEL (?:PRIMER|SEGUNDO) PARCIAL|"
                           r"EXAMEN (?:PARCIAL|FINAL))"), None),
    ("cuestionario_autonomo", _r(r"LECTURA GUIADA[^.]*CUESTIONARIO|CUESTIONARIO DE COMPRENSION"), ("autonomo",)),
    ("cuestionario", _r(r"CUESTIONARIO(?! DE AUTOEVALUACION)"), None),
    ("foro", _r(r"\bFORO\b(?! DE PRESENTACION)"), None),
    ("estudio_caso", _r(r"ESTUDIO DE CASO"), None),
    ("practica_experimental", _r(r"PRACTICA DE APRENDIZAJE EXPERIMENTAL|\bPRACTICA \d+\b(?!, FASE DE DESARROLLO)"),
     ("practico",)),
    ("proyecto_final", _r(r"TRABAJO FINAL|PROYECTO FINAL|PRODUCTO FINAL|TRABAJO ACADEMICO FINAL"), ("autonomo",)),
    ("exposicion_final", _r(r"EXPOSICION ORAL|PRESENTACION DEL PROYECTO FINAL|(?<!PREPARACION DE LA )SUSTENTACION TECNICA"),
     None),
    ("ensayo", _r(r"\bENSAYO\b(?! BREVE POR EQUIPOS)"), ("autonomo",)),
    ("portafolio", _r(r"PORTAFOLIO"), ("autonomo",)),
    ("taller_coevaluacion", _r(r"COEVALUACION|REVISION CRUZADA"), ("docente", "asincronica")),
    ("autoevaluacion", _r(r"AUTOEVALUACION"), ("docente", "asincronica")),
    ("participacion", _r(r"PARTICIPACION EN (?:LA |LAS )?SESION"), ("docente", "asincronica")),
    ("entrega_avance", _r(r"\bENTREGA (?:DE|DEL)\b|INTEGRACION Y ENTREGA|VERSION CORREGIDA"), ("autonomo", "practico")),
)

# Lo que se dice de la misma cosa: si ya hay uno, el otro sobra en esa columna.
_EXCLUYE = {"proyecto_final": {"entrega_avance"}, "practica_experimental": {"entrega_avance"},
            "exposicion_final": {"proyecto_final"}, "cuestionario_autonomo": {"cuestionario"}}


def _plan(tipo: str, texto: str, norma: Norma | None) -> tuple:
    """(calificación, instrumento, finalidad, agente) de un tipo evaluable."""
    final_en_c5 = norma is not None and norma.c5 == "prueba_y_proyecto_final"
    pares = bool(re.search(r"PARES|COLABORATIV|COOPERATIV|COEVALUACION", texto))
    observacion = bool(re.search(r"LABORATORIO|REGISTRO DE RESULTADOS|SIMULA", texto))
    return {
        "diagnostica": (None, "prueba_objetiva", "diagnostica", "heteroevaluacion"),
        "prueba_sumativa": ("C5_sumativa", "prueba_objetiva", "sumativa", "heteroevaluacion"),
        "cuestionario": ("C3_formativa", "prueba_objetiva", "formativa", "heteroevaluacion"),
        "cuestionario_autonomo": ("C1_autonoma", "prueba_objetiva", "formativa", "heteroevaluacion"),
        "foro": ("C1_contacto", "rubrica", "formativa", "coevaluacion"),
        "estudio_caso": ("C1_contacto", "rubrica", "sumativa", "coevaluacion_y_heteroevaluacion"),
        "practica_experimental": ("C2_practicas", "guia_observacion" if observacion else "rubrica",
                                  "formativa" if pares else "sumativa", "coevaluacion" if pares else "heteroevaluacion"),
        "proyecto_final": ("C5_sumativa" if final_en_c5 else "C4_proyecto", "rubrica", "sumativa", "heteroevaluacion"),
        "exposicion_final": ("C5_sumativa" if final_en_c5 else "C4_proyecto", "rubrica", "sumativa",
                             "coevaluacion_y_heteroevaluacion"),
        "ensayo": ("C1_autonoma", "rubrica", "formativa", "heteroevaluacion"),
        "portafolio": ("C1_autonoma", "lista_cotejo", "formativa", "autoevaluacion"),
        "taller_coevaluacion": ("C1_contacto", "rubrica", "formativa", "coevaluacion"),
        "autoevaluacion": ("C1_contacto", "cuestionario_autoevaluacion", "formativa", "autoevaluacion"),
        "participacion": ("C1_contacto", "lista_cotejo", "formativa", "heteroevaluacion"),
        "entrega_avance": ("C4_proyecto", "lista_cotejo", "sumativa", "heteroevaluacion"),
    }[tipo]


def _textos(sesion) -> dict[str, str]:
    asincronica = sesion.docente.asincronica.texto if sesion.docente.asincronica else ""
    return {"docente": sesion.docente.texto, "asincronica": asincronica,
            "practico": sesion.practico.texto, "autonomo": sesion.autonomo.texto}


def clasificar_columna(sesion_id: str, columna: str, texto: str, norma: Norma | None) -> list[Actividad]:
    plano = _plano(texto)
    if not plano:
        return []
    # «Práctica n, fase de desarrollo»: el avance se califica con la entrega posterior, no aquí.
    encontrados = [] if _FASE_DE_DESARROLLO.search(plano) else [
        tipo for tipo, patron, columnas in _REGLAS if (columnas is None or columna in columnas) and patron.search(plano)]
    excluidos = {x for tipo in encontrados for x in _EXCLUYE.get(tipo, ())}
    tipos = [t for t in encontrados if t not in excluidos]
    if not tipos:
        return [Actividad(sesion_id, columna, "avance", False, None, None, None, None,
                          "rotulo" if _AVANCE.search(plano) else "sin_rotulo")]
    return [Actividad(sesion_id, columna, tipo, True, *_plan(tipo, plano, norma), "rotulo") for tipo in tipos]


# Rótulos de avance (no se califican); una columna sin ninguno queda como «sin_rotulo».
_FASE_DE_DESARROLLO = _r(r"FASE DE DESARROLLO")
_AVANCE = _r(r"PRACTICA GUIADA|DEMOSTRACION|AMPLIACION|INCORPORACION|AJUSTE|EXPOSICION DIALOGADA|CLASE INVERTIDA|"
             r"RETROALIMENTACION|ORIENTACIONES|LECTURA GUIADA|RESOLUCION DE EJERCICIOS|FASE DE DESARROLLO|"
             r"ELABORACION|REDACCION|IMPLEMENTACION|PREPARACION|REVISION|EXPLICACION|TALLER|APRENDIZAJE BASADO|"
             r"PROFUNDIZACION|CALCULO|DISENO|DOCUMENTACION|ANALISIS|VERIFICACION|EJECUCION|PROGRAMACION|"
             r"IDENTIFICACION|INTEGRACION|ORGANIZACION|EJERCICIOS|SESION|ENCUENTRO|CARGA|RECORRIDO|GENERACION|"
             r"CORRECCION|REORGANIZACION|INVESTIGACION|LECTURA|REPASO|CONSTRUCCION|CONFIGURACION|INSTALACION|"
             r"SOCIALIZACION|ESTRUCTURACION|DEFINICION")


def clasificar(silabo: SilaboUTI, norma: Norma | None) -> list[Actividad]:
    """Actividades de todas las sesiones, en el orden del sílabo."""
    actividades: list[Actividad] = []
    for momento in silabo.momentos:
        for sesion in momento.sesiones:
            for columna, texto in _textos(sesion).items():
                actividades += clasificar_columna(sesion.id, columna, texto, norma)
    return actividades
