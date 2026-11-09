"""Contrato común de los workers y piezas compartidas para armar su pedido."""
from typing import Protocol

from pydantic import BaseModel

from app.agentes.mensajes import EntregaLote, TareaLote
from app.llm.cliente import ClienteLLM
from app.llm.json import pedir_json
from app.llm.prompts import Sello, construir_prompt

SALIDA_WORKER = 3500  # tokens máximos de salida por lote (spec §5.3)
TEMPERATURA_WORKER = 0.4  # spec §5.2

REGLAS_COMUNES = (
    "Eres un docente universitario que prepara herramientas de estudio para estudiantes "
    "a partir del sílabo de la clase. Usa solo los contenidos, actividades y resultados "
    "de aprendizaje del sílabo; no inventes temas ni cites fuentes que no estén en él. "
    "Los datos de los casos son ficticios y se declaran como tales. Escribe en español. "
    "Nunca uses las opciones \"todas las anteriores\" ni \"ninguna de las anteriores\"."
)


class Worker(Protocol):
    herramienta: str

    def generar(self, tarea: TareaLote, cliente: ClienteLLM) -> EntregaLote: ...


def sello_de(tarea: TareaLote) -> Sello:
    c = tarea.contexto
    return Sello(codigo_pf=c.codigo_pf, clase_id=c.clase_id, fecha=c.fecha)


def bloque_comun(tarea: TareaLote) -> list[str]:
    """Resultados calculados y devoluciones del revisor, comunes a todos los pedidos."""
    lineas: list[str] = []
    if tarea.resultados_calculados:
        lineas.append("Resultados calculados por el sistema (úsalos tal cual, no los recalcules):")
        lineas += [f"- {r}" for r in tarea.resultados_calculados]
    if tarea.devoluciones:
        lineas.append("Correcciones pedidas por el control de calidad (corrígelas en esta entrega):")
        lineas += [f"- {d.item_id}: {d.motivo}" for d in tarea.devoluciones]
    return lineas


def pedir(tarea: TareaLote, cliente: ClienteLLM, *, instrucciones: str, pedido: str,
          modelo: type[BaseModel], esquema: dict) -> tuple[BaseModel, tuple[int, int]]:
    """Arma el prompt con el constructor único y pide la salida guiada por esquema."""
    mensajes = construir_prompt(
        sello=sello_de(tarea), instrucciones=instrucciones, contexto=tarea.contexto,
        estilo=tarea.estilo, ya_generado=tarea.ya_generado, pedido=pedido,
        indicaciones_docente=tarea.instrucciones,
        salida_max=SALIDA_WORKER, contar=cliente.contar_tokens,
    )
    salida, respuesta = pedir_json(
        cliente, mensajes, modelo, esquema, rol="worker", temperatura=TEMPERATURA_WORKER,
        max_tokens=SALIDA_WORKER, pensar=False,
        trabajo_id=tarea.trabajo_id, asignatura_id=tarea.asignatura_id,
    )
    return salida, (respuesta.tokens_entrada, respuesta.tokens_salida)
