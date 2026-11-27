"""Esquemas de las herramientas del plan de evaluación (V3-6).

Preparan las actividades evaluables que el sílabo trae: la práctica experimental con su guía de
observación, la ficha del foro con su rúbrica (prompt institucional §5.3), la guía de la tarea autónoma
evaluable (§4), la prueba diagnóstica de prerrequisitos, la guía de la entrega con su lista de cotejo y
el insumo de respaldo de las tareas complementarias (§6.3). Como las demás: el modelo llena el esquema
JSON y el código valida con Pydantic. Lo que no decide el modelo (plazos, tipo de evaluación) lo pone el
código.
"""
from typing import Literal

from pydantic import Field

from app.herramientas.esquemas import _Cerrado, _cerrado, _textos

SIN_INDICADOR = "sin indicador del momento"


def _enum(valores) -> dict:
    return {"type": "string", "enum": list(valores)}


def _indicadores(indicadores: list[str]) -> dict:
    """Indicador de la rúbrica del momento al que se alinea; si el momento no trae rúbrica, uno fijo."""
    return _enum([*indicadores, SIN_INDICADOR] if indicadores else [SIN_INDICADOR])


# --- Guía de la práctica experimental y guía de observación -------------------------------

class CriterioObservacion(_Cerrado):
    criterio: str = Field(min_length=10, max_length=720)
    evidencia: str = Field(min_length=10, max_length=900)


class GuiaPractica(_Cerrado):
    titulo: str = Field(min_length=10, max_length=600)
    objetivo: str = Field(min_length=20)
    ra: str
    materiales: list[str] = Field(min_length=1, max_length=8)
    procedimiento: list[str] = Field(min_length=3, max_length=10)
    registro: list[str] = Field(min_length=2, max_length=6)
    producto: str = Field(min_length=20, max_length=1500)
    condiciones: list[str] = Field(min_length=1, max_length=5)
    observacion: list[CriterioObservacion] = Field(min_length=4, max_length=8)


def esquema_guia_practica(ras: list[str]) -> dict:
    criterio = _cerrado({"criterio": {"type": "string"}, "evidencia": {"type": "string"}})
    return _cerrado({"titulo": {"type": "string"}, "objetivo": {"type": "string"}, "ra": _enum(ras),
                     "materiales": _textos(1, 8), "procedimiento": _textos(3, 10), "registro": _textos(2, 6),
                     "producto": {"type": "string"}, "condiciones": _textos(1, 5),
                     "observacion": {"type": "array", "items": criterio, "minItems": 4, "maxItems": 8}})


# --- Ficha del foro con su rúbrica (§5.3) ---------------------------------------------------

class CriterioRubrica(_Cerrado):
    criterio: str = Field(min_length=5, max_length=600)
    indicador_momento: str
    destacado: str = Field(min_length=10, max_length=1200)
    satisfactorio: str = Field(min_length=10, max_length=1200)
    en_proceso: str = Field(min_length=10, max_length=1200)


class FichaForo(_Cerrado):
    tema: str = Field(min_length=10, max_length=600)
    contenido: str
    pregunta_detonante: str = Field(min_length=30, max_length=1500)
    aporte_inicial: str = Field(min_length=30, max_length=1800)
    replicas: str = Field(min_length=30, max_length=1800)
    uso_ia: str = Field(min_length=20, max_length=1800)
    rubrica: list[CriterioRubrica] = Field(min_length=3, max_length=5)
    # Los pone el código: plazos sugeridos desde la fecha de la sesión y tipo de evaluación (§5.3).
    plazos: list[str] = []
    evaluacion: str = ""


def _rubrica(indicadores: list[str], minimo: int, maximo: int) -> dict:
    criterio = _cerrado({"criterio": {"type": "string"}, "indicador_momento": _indicadores(indicadores),
                         "destacado": {"type": "string"}, "satisfactorio": {"type": "string"},
                         "en_proceso": {"type": "string"}})
    return {"type": "array", "items": criterio, "minItems": minimo, "maxItems": maximo}


def esquema_ficha_foro(contenidos: list[str], indicadores: list[str]) -> dict:
    return _cerrado({"tema": {"type": "string"},
                     "contenido": _enum(contenidos) if contenidos else {"type": "string"},
                     "pregunta_detonante": {"type": "string"}, "aporte_inicial": {"type": "string"},
                     "replicas": {"type": "string"}, "uso_ia": {"type": "string"},
                     "rubrica": _rubrica(indicadores, 3, 5)})


# --- Guía de la tarea autónoma evaluable (§4) ---------------------------------------------------

class GuiaTarea(_Cerrado):
    producto: str = Field(min_length=20, max_length=1200)
    proposito: str = Field(min_length=30, max_length=1800)
    ra: str
    modalidad: Literal["individual", "grupal"]
    condiciones: list[str] = Field(min_length=2, max_length=5)
    pasos: list[str] = Field(min_length=3, max_length=8)
    criterios: list[CriterioRubrica] = Field(min_length=3, max_length=6)
    uso_ia: str = Field(min_length=20, max_length=1800)


def esquema_guia_tarea(ras: list[str], indicadores: list[str]) -> dict:
    return _cerrado({"producto": {"type": "string"}, "proposito": {"type": "string"}, "ra": _enum(ras),
                     "modalidad": _enum(["individual", "grupal"]), "condiciones": _textos(2, 5),
                     "pasos": _textos(3, 8), "criterios": _rubrica(indicadores, 3, 6), "uso_ia": {"type": "string"}})


# --- Prueba diagnóstica de prerrequisitos ---------------------------------------------------

class Prerrequisito(_Cerrado):
    nombre: str = Field(min_length=5, max_length=600)
    por_que: str = Field(min_length=20, max_length=1200)


class PreguntaDiagnostica(_Cerrado):
    prerrequisito: int = Field(ge=1, le=5)
    pregunta: str = Field(min_length=20, max_length=1500)
    opciones: list[str] = Field(min_length=4, max_length=4)
    correcta: int = Field(ge=0, le=3)
    explicacion: str = Field(min_length=20, max_length=1500)
    si_fallas: str = Field(min_length=15, max_length=1200)


class PruebaDiagnostica(_Cerrado):
    prerrequisitos: list[Prerrequisito] = Field(min_length=3, max_length=5)
    preguntas: list[PreguntaDiagnostica] = Field(min_length=6, max_length=12)


def esquema_prueba_diagnostica() -> dict:
    pre = _cerrado({"nombre": {"type": "string"}, "por_que": {"type": "string"}})
    pregunta = _cerrado({"prerrequisito": {"type": "integer", "minimum": 1, "maximum": 5},
                         "pregunta": {"type": "string"}, "opciones": _textos(4, 4),
                         "correcta": {"type": "integer", "minimum": 0, "maximum": 3},
                         "explicacion": {"type": "string"}, "si_fallas": {"type": "string"}})
    return _cerrado({"prerrequisitos": {"type": "array", "items": pre, "minItems": 3, "maxItems": 5},
                     "preguntas": {"type": "array", "items": pregunta, "minItems": 6, "maxItems": 12}})


# --- Guía de la entrega de avance con su lista de cotejo (§4, §6.4) -----------------------------

class ItemCotejo(_Cerrado):
    item: str = Field(min_length=10, max_length=720)
    indicador_momento: str


class GuiaEntrega(_Cerrado):
    que_se_entrega: str = Field(min_length=20, max_length=1500)
    insumo_previo: str = Field(min_length=10, max_length=1200)
    avance_nuevo: str = Field(min_length=20, max_length=1500)
    pasos: list[str] = Field(min_length=3, max_length=8)
    lista_cotejo: list[ItemCotejo] = Field(min_length=5, max_length=10)
    errores_comunes: list[str] = Field(min_length=2, max_length=5)


def esquema_guia_entrega(indicadores: list[str]) -> dict:
    item = _cerrado({"item": {"type": "string"}, "indicador_momento": _indicadores(indicadores)})
    return _cerrado({"que_se_entrega": {"type": "string"}, "insumo_previo": {"type": "string"},
                     "avance_nuevo": {"type": "string"}, "pasos": _textos(3, 8),
                     "lista_cotejo": {"type": "array", "items": item, "minItems": 5, "maxItems": 10},
                     "errores_comunes": _textos(2, 5)})


# --- Insumo de respaldo de una tarea complementaria (§6.3) --------------------------------------

TIPOS_INSUMO = ("plantilla", "proyecto_base", "dataset", "version_referencia")


class InsumoRespaldo(_Cerrado):
    tarea: str = Field(min_length=20, max_length=1200)
    insumo_previo: str = Field(min_length=10, max_length=1200)
    tipo: Literal["plantilla", "proyecto_base", "dataset", "version_referencia"]
    descripcion: str = Field(min_length=20, max_length=1500)
    contenido: str = Field(min_length=200, max_length=8000)
    como_usarlo: list[str] = Field(min_length=2, max_length=5)


def esquema_insumo_respaldo() -> dict:
    return _cerrado({"tarea": {"type": "string"}, "insumo_previo": {"type": "string"},
                     "tipo": _enum(TIPOS_INSUMO), "descripcion": {"type": "string"},
                     "contenido": {"type": "string"}, "como_usarlo": _textos(2, 5)})
