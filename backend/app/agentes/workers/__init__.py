"""Workers compartidos por herramienta (spec §3.7). Sin estado (regla A2)."""
from app.agentes.workers.base import Worker
from app.agentes.workers.cuestionario import WorkerCuestionario, WorkerSimulacro
from app.agentes.workers.ficha_clase import WorkerFichaClase
from app.agentes.workers.momento import ESTUDIO_CASO, GUIA_EVIDENCIA, GUIA_PRODUCTO_FINAL, REPASO

WORKERS: dict[str, Worker] = {
    "cuestionario": WorkerCuestionario(),
    "ficha_clase": WorkerFichaClase(),
    "simulacro": WorkerSimulacro(),
    "repaso_momento": REPASO,
    "guia_evidencia": GUIA_EVIDENCIA,
    "estudio_caso": ESTUDIO_CASO,
    "guia_producto_final": GUIA_PRODUCTO_FINAL,
}

__all__ = ["WORKERS", "Worker", "WorkerCuestionario", "WorkerFichaClase", "WorkerSimulacro"]
