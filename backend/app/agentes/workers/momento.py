"""Workers de momento (P3b): repaso integrador, guía de la evidencia y estudio de caso.

Cada uno es una sola sección con JSON de esquema cerrado. La integridad (§9.4) se
controla tres veces: en el pedido, en el verificador determinista y en el revisor.
"""
import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from app.agentes.mensajes import EntregaLote, TareaLote
from app.agentes.planificador import _casos_libres
from app.agentes.workers.base import REGLAS_COMUNES, bloque_comun, pedir
from app.herramientas.esquemas import (
    EstudioCaso, GuiaEvidencia, GuiaProductoFinal, RepasoMomento, esquema_estudio_caso, esquema_guia_evidencia,
    esquema_guia_producto_final, esquema_repaso,
)
from app.llm.cliente import ClienteLLM
from app.silabo.contexto import ContextoClase

NO_RESOLVER = (
    " Nunca resuelvas ni redactes la evidencia, las tareas, las PAE ni las evaluaciones del "
    "momento: no des respuestas, cálculos, conclusiones ni textos que el estudiante pueda copiar."
)
# Respaldos para cuando ningún escenario del perfil queda libre; también se filtran (C9).
ESCENARIOS_DE_RESPALDO = ("un huerto escolar comunitario", "una panadería de barrio",
                          "un club deportivo juvenil", "una biblioteca municipal")


def escenario_para(tarea: TareaLote) -> str:
    """Escenario del perfil que no se parece a los entregables (C9); fijo por momento."""
    libres = (_casos_libres(list(tarea.estilo.escenarios), tarea.contexto.entregables_momento)
              or _casos_libres(list(ESCENARIOS_DE_RESPALDO), tarea.contexto.entregables_momento)
              or [ESCENARIOS_DE_RESPALDO[0]])
    return libres[int(hashlib.sha256(tarea.contexto.clase_id.encode()).hexdigest(), 16) % len(libres)]


@dataclass(frozen=True)
class _Seccion:
    modelo: type[BaseModel]
    esquema: Callable[[ContextoClase], dict]
    pedido: Callable[[TareaLote], str]


class WorkerSeccion:
    """Una herramienta de una sección: arma el pedido, valida y entrega."""

    def __init__(self, herramienta: str, instrucciones: str, seccion: _Seccion,
                 completar: Callable[[dict, TareaLote], dict] = lambda d, t: d):
        self.herramienta, self.instrucciones = herramienta, instrucciones
        self.seccion, self.completar = seccion, completar

    def generar(self, tarea: TareaLote, cliente: ClienteLLM) -> EntregaLote:
        if tarea.lote != 1:
            raise ValueError(f"{self.herramienta} tiene una sección; lote inválido: {tarea.lote}")
        pedido = self.seccion.pedido(tarea)
        comun = bloque_comun(tarea)
        if comun:
            pedido = "\n".join([pedido, "", *comun])
        salida, tokens = pedir(tarea, cliente, instrucciones=self.instrucciones, pedido=pedido,
                               modelo=self.seccion.modelo, esquema=self.seccion.esquema(tarea.contexto))
        contenido = self.completar(salida.model_dump(), tarea)
        return EntregaLote(trabajo_id=tarea.trabajo_id, asignatura_id=tarea.asignatura_id, lote=1,
                           ronda=tarea.ronda, contenido=[contenido], tokens=tokens)


def _ids_sesiones(c: ContextoClase) -> list[str]:
    return [a.split(":", 1)[0] for a in c.actividades]


REPASO = WorkerSeccion(
    "repaso_momento",
    REGLAS_COMUNES + " Preparas el repaso integrador del momento: conectas sus clases con su "
    "resultado de aprendizaje." + NO_RESOLVER,
    _Seccion(RepasoMomento, lambda c: esquema_repaso(_ids_sesiones(c)), lambda t: (
        "Repaso integrador del momento: para cada sesión (clase_id), de 3 a 5 ideas clave; "
        "un párrafo que conecte las sesiones con el resultado de aprendizaje; y de 3 a 5 preguntas "
        "de repaso que integren varias sesiones.")),
)

GUIA_EVIDENCIA = WorkerSeccion(
    "guia_evidencia",
    REGLAS_COMUNES + " Preparas una guía para entender la evidencia del momento y cómo se valora, "
    "SIN resolverla." + NO_RESOLVER,
    _Seccion(GuiaEvidencia, lambda c: esquema_guia_evidencia([f.indicador for f in c.rubrica]), lambda t: (
        "Guía de la evidencia del momento (el primer entregable de la lista): en «que_se_pide», "
        "explica con tus palabras qué se pide (máx. 600 caracteres, sin copiarlo); en "
        "«como_se_valora», para cada indicador de la rúbrica, qué observará el docente; de 3 a 5 "
        "errores comunes; y de 3 a 5 preguntas de autochequeo para revisar el propio trabajo.")),
)


def _con_escenario(datos: dict, tarea: TareaLote) -> dict:
    return {**datos, "escenario": escenario_para(tarea)}  # El código fija el escenario (C9).


ESTUDIO_CASO = WorkerSeccion(
    "estudio_caso",
    REGLAS_COMUNES + " Preparas un estudio de caso de práctica, distinto del caso que se evalúa, "
    "con preguntas escalonadas." + NO_RESOLVER,
    _Seccion(EstudioCaso, lambda c: esquema_estudio_caso([r.id for r in c.ra]), lambda t: (
        f"Estudio de caso de práctica ambientado en: {escenario_para(t)}. Escribe el caso con datos "
        "ficticios (al menos 300 caracteres) y de 3 a 6 preguntas de menor a mayor nivel (receptivo, "
        "resolutivo, reflexivo, critico), cada una con una respuesta orientativa. Indica el RA que trabaja.")),
    completar=_con_escenario,
)


def _esquema_final(c: ContextoClase) -> dict:
    if not c.rubrica:
        raise ValueError("el sílabo no trae la rúbrica del producto final")
    return esquema_guia_producto_final([a.split(":", 1)[0] for a in c.actividades], [f.indicador for f in c.rubrica])


GUIA_PRODUCTO_FINAL = WorkerSeccion(
    "guia_producto_final",
    REGLAS_COMUNES + " Preparas la guía de preparación del producto final de la asignatura: cómo "
    "aporta cada momento y cómo prepararse para cada criterio de su rúbrica, SIN resolverlo." + NO_RESOLVER,
    _Seccion(GuiaProductoFinal, _esquema_final, lambda t: (
        "Guía del producto final (el primer entregable de la lista; las evidencias de cada momento "
        "le siguen): en «ruta», un paso por momento (M1, M2, …) que diga qué aporta su evidencia al "
        "producto final; en «criterios», para cada indicador de la rúbrica, cómo prepararse; y de 3 a 5 "
        "recomendaciones. No redactes partes del producto.")),
)
