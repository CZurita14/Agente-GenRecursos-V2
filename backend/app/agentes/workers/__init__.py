"""Workers compartidos por herramienta (spec §3.7). Sin estado (regla A2)."""
from app.agentes.workers.base import Worker
from app.agentes.workers.evaluacion import (
    FICHA_FORO, GUIA_ENTREGA, GUIA_PRACTICA, GUIA_TAREA, INSUMO_RESPALDO, PRUEBA_DIAGNOSTICA,
)
from app.agentes.workers.cuestionario import WorkerCuestionario, WorkerSimulacro
from app.agentes.workers.clase import GUIA_AUTONOMA, GUION_CLASE, PRACTICA_GUIADA, PRESENTACION, TARJETAS
from app.agentes.workers.ficha_clase import WorkerFichaClase
from app.agentes.workers.guia_estudio import WorkerGuiaEstudio
from app.agentes.workers.momento import ESTUDIO_CASO, GUIA_EVIDENCIA, GUIA_PRODUCTO_FINAL, REPASO

WORKERS: dict[str, Worker] = {
    "cuestionario": WorkerCuestionario(),
    "ficha_clase": WorkerFichaClase(),
    "simulacro": WorkerSimulacro(),
    "guia_estudio": WorkerGuiaEstudio(),
    "repaso_momento": REPASO,
    "guia_evidencia": GUIA_EVIDENCIA,
    "estudio_caso": ESTUDIO_CASO,
    "guia_producto_final": GUIA_PRODUCTO_FINAL,
    "practica_guiada": PRACTICA_GUIADA,
    "tarjetas": TARJETAS,
    "guia_autonoma": GUIA_AUTONOMA,
    "guion_clase": GUION_CLASE,
    "presentacion": PRESENTACION,
    "guia_practica": GUIA_PRACTICA,
    "ficha_foro": FICHA_FORO,
    "guia_tarea": GUIA_TAREA,
    "prueba_diagnostica": PRUEBA_DIAGNOSTICA,
    "guia_entrega": GUIA_ENTREGA,
    "insumo_respaldo": INSUMO_RESPALDO,
}

__all__ = ["WORKERS", "Worker", "WorkerCuestionario", "WorkerFichaClase", "WorkerSimulacro"]
