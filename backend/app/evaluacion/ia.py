"""La IA clasifica las columnas del sílabo que no traen un rótulo institucional (V3-3).

Solo elige el tipo de la actividad de una lista cerrada; la calificación del RRA, el instrumento y el
tipo de evaluación los pone después el mismo mapa que usan las reglas, así no hay dos criterios. El prompt
lleva solo el texto de las actividades y datos del PF (nunca datos de personas).
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.evaluacion.clasificador import TIPOS
from app.llm.cliente import ClienteLLM
from app.llm.json import pedir_json

LOTE = 60  # Columnas por llamada; un sílabo con más se pide en varias.

INSTRUCCIONES = """Eres un diseñador curricular del modelo de Proyectos Formativos de la Universidad Indoamérica.
El plan de evaluación del proyecto formativo está implícito en el sílabo: copia literalmente ciertas actividades
y les agrega instrumento, tipo de evaluación y ponderación. Tu tarea es decir, para cada actividad que te doy,
qué tipo de actividad es. Usa SOLO estos tipos:

- diagnostica: evaluación diagnóstica de saberes previos (no se pondera).
- prueba_sumativa: prueba acumulativa, prueba parcial o examen que certifica el resultado de aprendizaje.
- cuestionario: cuestionario o prueba corta formativa en clase o en plataforma.
- cuestionario_autonomo: lectura o tarea autónoma que se comprueba con un cuestionario.
- foro: foro o debate argumentado entre estudiantes, con réplicas a compañeros.
- estudio_caso: análisis de un caso que el estudiante entrega o expone y se califica.
- practica_experimental: práctica, laboratorio, simulación o taller práctico calificado con producto verificable.
- proyecto_final: entrega del producto final o del trabajo final del proyecto formativo.
- exposicion_final: exposición, presentación o sustentación del producto final.
- ensayo: ensayo, informe crítico o escrito argumentativo individual que se califica.
- portafolio: portafolio o bitácora de evidencias con reflexión.
- taller_coevaluacion: trabajo colaborativo en clase calificado por los pares (coevaluación).
- autoevaluacion: autoevaluación o reflexión metacognitiva con criterios.
- participacion: participación calificada en sesiones sincrónicas o debates en clase.
- entrega_avance: entrega calificada de un avance del producto o de la evidencia del momento.
- avance: todo lo que NO se califica: clases expositivas, demostraciones, prácticas guiadas, lecturas,
  ejercicios de preparación, ajustes, revisiones y trabajo autónomo que prepara la evidencia.

Reglas:
- Una actividad se califica solo si produce una evidencia concreta que alguien evalúa y que pasaría al plan de
  evaluación. Prácticas de rotación, talleres de ejercitación, lecturas, cuadros y tablas de estudio son avance,
  salvo que el texto diga que se entregan, se califican o se evalúan.
- Un proyecto formativo completo tiene entre 10 y 20 actividades calificadas en total, contando las que ya se
  reconocieron por su rótulo; en un periodo hay de 2 a 6 prácticas calificadas. Sé selectivo.
- Si la misma actividad se repite en varias sesiones, se califica solo donde se entrega o se cierra.
- Si dudas, responde «avance». No cambies los identificadores. Responde con un elemento por cada actividad."""

TipoActividad = Literal[TIPOS]  # type: ignore[valid-type]


class _Clasificada(BaseModel):
    id: str = Field(max_length=40)
    tipo: TipoActividad


class _Respuesta(BaseModel):
    actividades: list[_Clasificada]


ESQUEMA = {
    "type": "object", "required": ["actividades"], "additionalProperties": False,
    "properties": {"actividades": {"type": "array", "items": {
        "type": "object", "required": ["id", "tipo"], "additionalProperties": False,
        "properties": {"id": {"type": "string"}, "tipo": {"type": "string", "enum": list(TIPOS)}}}}},
}

_COLUMNA = {"docente": "actividad con el docente", "asincronica": "otras actividades con el docente",
            "practico": "actividad práctico-experimental", "autonomo": "trabajo autónomo"}


def _pedido(pf: str, modalidad: str, items: dict[str, str], ya_reconocidas: int) -> str:
    lineas = [f"Proyecto formativo: {pf}. Modalidad: {modalidad or 'sin dato'}.",
              f"Actividades calificadas ya reconocidas por su rótulo: {ya_reconocidas}.", "", "Actividades:"]
    for clave, texto in items.items():
        sesion, columna = clave.split("/")
        lineas.append(f"- id={clave} | {sesion} | {_COLUMNA.get(columna, columna)} | {texto}")
    return "\n".join(lineas)


def _plano(texto: str) -> str:
    return re.sub(r"\W+", " ", texto.lower()).strip()


def _solo_la_ultima_repeticion(items: dict[str, str], tipos: dict[str, str]) -> dict[str, str]:
    """La misma actividad repetida en la misma columna de varias sesiones se califica una vez: en la última."""
    ultima: dict[tuple[str, str], str] = {}
    for clave in items:  # `items` viene en el orden del sílabo.
        if tipos[clave] != "avance":
            ultima[(clave.split("/")[1], _plano(items[clave]))] = clave
    return {k: v if v == "avance" or ultima[(k.split("/")[1], _plano(items[k]))] == k else "avance"
            for k, v in tipos.items()}


PRACTICAS_POR_MOMENTO = 2


def _acotar_practicas(tipos: dict[str, str]) -> dict[str, str]:
    """De las prácticas que sugiere la IA, quedan las últimas de cada momento (C2 tiene pocas prácticas calificadas).

    El docente puede marcar otras en la pantalla; aquí solo se evita repartir el 20–30 % de C2 entre decenas.
    """
    por_momento: dict[str, list[str]] = {}
    for clave, tipo in tipos.items():  # En el orden del sílabo.
        if tipo == "practica_experimental":
            por_momento.setdefault(clave.split("-")[0], []).append(clave)
    quedan = {c for claves in por_momento.values() for c in claves[-PRACTICAS_POR_MOMENTO:]}
    return {k: "avance" if v == "practica_experimental" and k not in quedan else v for k, v in tipos.items()}


def clasificar_con_ia(cliente: ClienteLLM, pf: str, modalidad: str, items: dict[str, str], *, ya_reconocidas: int = 0,
                      trabajo_id=None, asignatura_id=None, renovar=lambda: None) -> dict[str, str]:
    """Tipo de cada columna sin rótulo; lo que la IA no devuelva o invente queda como «avance»."""
    tipos: dict[str, str] = {}
    claves = list(items)
    for inicio in range(0, len(claves), LOTE):
        lote = {k: items[k] for k in claves[inicio:inicio + LOTE]}
        mensajes = [{"role": "system", "content": INSTRUCCIONES},
                    {"role": "user", "content": _pedido(pf, modalidad, lote, ya_reconocidas)}]
        salida, _ = pedir_json(cliente, mensajes, _Respuesta, ESQUEMA, rol="clasificador", temperatura=0.0,
                               max_tokens=40 * len(lote) + 400, trabajo_id=trabajo_id, asignatura_id=asignatura_id)
        tipos.update({a.id: a.tipo for a in salida.actividades if a.id in lote})
        renovar()
    return _acotar_practicas(_solo_la_ultima_repeticion(items, {k: tipos.get(k, "avance") for k in claves}))
