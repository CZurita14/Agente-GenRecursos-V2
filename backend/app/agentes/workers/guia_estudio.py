"""Guía de estudio del momento: la parte teórica (10 a 15 páginas), en 4 secciones.

Es la base de las demás herramientas: una vez validada por el docente, su contenido entra
como material del momento en los pedidos de las herramientas de ese momento y de sus clases.
"""
from app.agentes.mensajes import EntregaLote, TareaLote
from app.agentes.workers.base import REGLAS_COMUNES, SALIDA_WORKER, bloque_comun, pedir
from app.agentes.workers.momento import NO_RESOLVER
from app.herramientas.esquemas import (
    GuiaAplicacion, GuiaDesarrollo, GuiaIntroduccion, esquema_guia_aplicacion, esquema_guia_desarrollo,
    esquema_guia_introduccion,
)
from app.agentes.verificador import MIN_PALABRAS_GUIA
from app.llm.cliente import ClienteLLM
from app.fuentes.searchapi import texto_fuentes
from app.llm.prompts import CONTEXTO_MAX, limite_contexto

# Una sección de desarrollo (1 600 a 2 000 palabras en JSON) no cabe en 3 500 tokens de salida.
SALIDA_GUIA = 9000
from app.momentos.trazabilidad import fase, numero_momento

CITAS = ("Cita las fuentes de <fuentes> por su identificador entre corchetes ([B1], [F2]) cada vez que uses "
         "sus ideas, dando prioridad a la bibliografía del sílabo (B…). No cites otras fuentes, no inventes "
         "autores, títulos ni años, y no escribas enlaces: la bibliografía con los enlaces la agrega el sistema.")

SECCIONES = ("introduccion", "desarrollo_1", "desarrollo_2", "aplicacion")

INSTRUCCIONES = REGLAS_COMUNES + (
    " Redactas la guía de estudio teórica completa de un momento del Proyecto Formativo: un texto "
    "universitario detallado, con explicaciones en párrafos completos, ejemplos y definiciones, que el "
    "estudiante lee para dominar la teoría del momento antes de trabajar sus herramientas. Escribe con "
    "rigor y claridad; no dejes ideas en viñetas sin explicar."
) + NO_RESOLVER


def _mitades(contenidos: list[str]) -> tuple[list[str], list[str]]:
    if len(contenidos) <= 1:
        return list(contenidos), list(contenidos)
    medio = (len(contenidos) + 1) // 2
    return contenidos[:medio], contenidos[medio:]


def _fase(tarea: TareaLote) -> str:
    n = numero_momento(tarea.contexto.clase_id) or 1
    nombre, proposito = fase(n)
    return f"Este es el momento {n} de la cadena de trazabilidad ({nombre}): el momento {proposito}."


def pedido(tarea: TareaLote) -> str:
    c = tarea.contexto
    primera, segunda = _mitades(list(c.contenidos))
    minimo = MIN_PALABRAS_GUIA[SECCIONES[tarea.lote - 1]]
    extension = f" Extensión de esta sección: al menos {minimo} palabras."
    if tarea.lote == 1:
        texto = ("Sección 1 de 4 de la guía de estudio (introducción): en «presentacion», de 3 a 5 párrafos "
                 "que presenten el momento, su propósito en el proyecto y su resultado de aprendizaje; en "
                 "«objetivos», de 3 a 6 objetivos de aprendizaje alineados con el RA; en «ruta_del_momento», "
                 "un paso por sesión o bloque que explique qué se estudia en cada uno y cómo se encadena; y "
                 "en «glosario», de 8 a 15 términos del momento con su definición.")
    elif tarea.lote in (2, 3):
        temas = primera if tarea.lote == 2 else segunda
        texto = (f"Sección {tarea.lote} de 4 de la guía de estudio (desarrollo teórico): en «apartados», un "
                 "apartado por tema (de 2 a 5), cada uno con un título, un «desarrollo» de 400 a 700 "
                 "palabras en párrafos (conceptos, fundamentos, procedimientos y un ejemplo breve con datos "
                 "ficticios) y de 2 a 6 puntos clave. Temas de esta sección: " + "; ".join(temas) + ".")
    else:
        texto = ("Sección 4 de 4 de la guía de estudio (aplicación): en «vinculacion_practica», de 3 a 5 "
                 "párrafos que vinculen la teoría con la práctica del momento y con el problema del proyecto; "
                 "en «ejemplos», 2 o 3 ejemplos desarrollados con datos ficticios (distintos del entregable), "
                 "cada uno con la situación y su desarrollo explicado; en «sintesis», de 2 a 4 párrafos de "
                 "cierre; y en «autoevaluacion», de 5 a 8 preguntas abiertas para que el estudiante compruebe "
                 "su comprensión.")
    citas = f" {CITAS}" if tarea.fuentes.get("silabo") or tarea.fuentes.get("web") else ""
    return f"{_fase(tarea)} {texto}{extension}{citas}"


MODELOS = {1: (GuiaIntroduccion, esquema_guia_introduccion), 2: (GuiaDesarrollo, esquema_guia_desarrollo),
           3: (GuiaDesarrollo, esquema_guia_desarrollo), 4: (GuiaAplicacion, esquema_guia_aplicacion)}


class WorkerGuiaEstudio:
    herramienta = "guia_estudio"

    def generar(self, tarea: TareaLote, cliente: ClienteLLM) -> EntregaLote:
        if tarea.lote not in MODELOS:
            raise ValueError(f"la guía de estudio tiene 4 secciones; lote inválido: {tarea.lote}")
        modelo, esquema = MODELOS[tarea.lote]
        texto = pedido(tarea)
        comun = bloque_comun(tarea)
        if comun:
            texto = "\n".join([texto, "", *comun])
        salida, tokens = pedir(tarea, cliente, instrucciones=INSTRUCCIONES, pedido=texto,
                               modelo=modelo, esquema=esquema(), fuentes=texto_fuentes(tarea.fuentes),
                               salida_max=SALIDA_GUIA if limite_contexto(cliente) > CONTEXTO_MAX else SALIDA_WORKER)
        contenido = salida.model_dump(exclude_none=True)
        if tarea.lote == 4:
            # La bibliografía la pone el código: enlaces reales de SearchAPI y la del sílabo, tal cual.
            contenido["bibliografia"] = {"silabo": list(tarea.fuentes.get("silabo", [])),
                                         "web": list(tarea.fuentes.get("web", []))}
        return EntregaLote(trabajo_id=tarea.trabajo_id, asignatura_id=tarea.asignatura_id, lote=tarea.lote,
                           ronda=tarea.ronda, contenido=[contenido], tokens=tokens)
