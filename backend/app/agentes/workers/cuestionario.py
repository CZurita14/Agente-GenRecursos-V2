"""Worker del cuestionario autocorregible: un lote de ítems de opción múltiple."""
import random

from app.agentes.mensajes import EntregaLote, TareaLote
from app.agentes.workers.base import REGLAS_COMUNES, bloque_comun, pedir
from app.herramientas.esquemas import ItemCuestionario, LoteCuestionario, esquema_cuestionario
from app.llm.cliente import ClienteLLM, JsonInvalido

# Plantillas por nivel medidas en la ronda de calidad v3 (pruebas/prueba_calidad_v3.py).
PLANTILLAS = """Plantillas por nivel (obligatorias):
- receptivo: una situación breve y una pregunta para RECONOCER el concepto o procedimiento que corresponde. Nunca preguntes por un dato que esté escrito en el contexto.
- resolutivo: APLICAR un procedimiento a la situación (elegir y ejecutar el método adecuado a las condiciones dadas, o leer correctamente un resultado para decidir).
- reflexivo: INTERPRETAR un resultado o relacionar dos hechos de la situación (por qué ocurre, qué implica, qué no se puede concluir).
- critico: presenta la CONCLUSIÓN o DECISIÓN de un profesional ficticio que contiene UN error concreto (sobregeneralizar, confundir no rechazar H0 con aceptarla, inferir causa de una asociación, priorizar sin criterio, ignorar un supuesto o una norma). La pregunta pide evaluarla; la opción correcta identifica exactamente ese error. Las incorrectas aprueban la conclusión o señalan un "error" inexistente.
Distractores: cada opción incorrecta representa un error típico distinto y plausible para un estudiante de este nivel; decláralo en "error_que_representa". La correcta lleva "error_que_representa": "ninguno"."""

INSTRUCCIONES = REGLAS_COMUNES + (
    " Generas ítems de opción múltiple con cuatro opciones y una sola respuesta correcta, "
    "con contexto profesional desde el nivel resolutivo y dos o más pasos de razonamiento "
    "desde el nivel reflexivo."
)


class WorkerCuestionario:
    herramienta = "cuestionario"

    def generar(self, tarea: TareaLote, cliente: ClienteLLM) -> EntregaLote:
        ctx = tarea.contexto
        ras = [r.id for r in ctx.ra]
        if not ras:
            raise ValueError(f"la clase {ctx.clase_id} no tiene resultados de aprendizaje")
        contenidos = ctx.contenidos or [ctx.momento_titulo]
        salida, tokens = pedir(
            tarea, cliente, instrucciones=INSTRUCCIONES, pedido=self._pedido(tarea),
            modelo=LoteCuestionario, esquema=esquema_cuestionario(len(tarea.plan), ras, contenidos),
        )
        if len(salida.items) != len(tarea.plan):
            raise JsonInvalido("cantidad de ítems distinta del plan")
        items = [
            _barajar(ItemCuestionario(item_id=plan.item_id, **item.model_dump()), tarea)
            for plan, item in zip(tarea.plan, salida.items)
        ]
        return EntregaLote(
            trabajo_id=tarea.trabajo_id, asignatura_id=tarea.asignatura_id, lote=tarea.lote,
            ronda=tarea.ronda, contenido=[i.model_dump() for i in items], tokens=tokens,
        )

    @staticmethod
    def _pedido(tarea: TareaLote) -> str:
        lineas = [f"Genera {len(tarea.plan)} ítems, uno por cada fila del plan y en ese orden:"]
        lineas += [f"- {p.item_id} · nivel {p.nivel} · foco: {p.foco}" + (f" · caso: {p.caso}" if p.caso else "")
                   for p in tarea.plan]
        if any(p.caso for p in tarea.plan):
            lineas.append("Cada ítem ambienta su situación en el caso indicado, con datos ficticios propios.")
        lineas += ["", PLANTILLAS]
        comun = bloque_comun(tarea)
        if comun:
            lineas += ["", *comun]
        return "\n".join(lineas)


def _barajar(item: ItemCuestionario, tarea: TareaLote) -> ItemCuestionario:
    """Baraja las opciones con una semilla fija por ítem; la clave sigue a su texto."""
    orden = list(range(len(item.opciones)))
    random.Random(f"{tarea.trabajo_id}-{item.item_id}").shuffle(orden)
    return item.model_copy(update={
        "opciones": [item.opciones[i] for i in orden],
        "correcta": orden.index(item.correcta),
    })


class WorkerSimulacro(WorkerCuestionario):
    """Simulacro del momento (catálogo #11): el mismo flujo de ítems con el contexto del
    momento. El solucionario son la clave, las justificaciones y el razonamiento de cada ítem."""
    herramienta = "simulacro"
