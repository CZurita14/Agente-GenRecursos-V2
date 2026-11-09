"""Worker de la ficha de clase, en dos secciones (spec §5.3: ficha por secciones)."""
from app.agentes.mensajes import EntregaLote, TareaLote
from app.agentes.workers.base import REGLAS_COMUNES, bloque_comun, pedir
from app.herramientas.esquemas import (
    ESQUEMA_FICHA_APLICACION,
    ESQUEMA_FICHA_CONCEPTUAL,
    FichaAplicacion,
    FichaConceptual,
)
from app.llm.cliente import ClienteLLM

INSTRUCCIONES = REGLAS_COMUNES + (
    " Preparas la ficha de estudio de la clase para que el estudiante la repase."
)

SECCIONES = {
    1: (FichaConceptual, ESQUEMA_FICHA_CONCEPTUAL,
        "Sección conceptual de la ficha: de 3 a 6 ideas clave de la clase, la relación de la "
        "clase con su resultado de aprendizaje y los errores frecuentes de los estudiantes."),
    2: (FichaAplicacion, ESQUEMA_FICHA_APLICACION,
        "Sección de aplicación de la ficha: un ejemplo resuelto paso a paso con datos ficticios "
        "(enunciado, pasos y resultado) y de 3 a 5 preguntas de autocomprobación."),
}


class WorkerFichaClase:
    herramienta = "ficha_clase"

    def generar(self, tarea: TareaLote, cliente: ClienteLLM) -> EntregaLote:
        if tarea.lote not in SECCIONES:
            raise ValueError(f"la ficha tiene 2 secciones; lote inválido: {tarea.lote}")
        modelo, esquema, pedido = SECCIONES[tarea.lote]
        comun = bloque_comun(tarea)
        if comun:
            pedido = "\n".join([pedido, "", *comun])
        salida, tokens = pedir(tarea, cliente, instrucciones=INSTRUCCIONES, pedido=pedido,
                               modelo=modelo, esquema=esquema)
        return EntregaLote(
            trabajo_id=tarea.trabajo_id, asignatura_id=tarea.asignatura_id, lote=tarea.lote,
            ronda=tarea.ronda, contenido=[salida.model_dump()], tokens=tokens,
        )
