"""Qué es cada herramienta con IA para el coordinador (P3b): ámbito, forma y controles.

Separado de los workers (que solo generan) para que el coordinador no dependa de su
clase: las pruebas sustituyen workers sin perder esta metadata.
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.agentes.verificador import (
    verificar_estudio_caso, verificar_ficha, verificar_guia_evidencia, verificar_guia_producto_final,
    verificar_repaso,
)
from app.herramientas.esquemas import (
    EstudioCaso, FichaAplicacion, FichaConceptual, GuiaEvidencia, GuiaProductoFinal, RepasoMomento,
)
from app.silabo.contexto import ContextoClase


@dataclass(frozen=True)
class Definicion:
    ambito: str                                   # clase, momento o asignatura
    es_quiz: bool = False                         # ítems planificados (cuestionario, simulacro)
    secciones: tuple[str, ...] = ()               # lote k → secciones[k - 1]
    modelos: tuple[type[BaseModel], ...] = ()     # esquema de cada sección
    verificar: Callable[[dict, ContextoClase], list[str]] = field(default=verificar_ficha)
    id_revision: str = "ficha"                    # clave del veredicto de integridad
    # Lo que el sílabo debe traer para que el esquema sea posible (None = cumple).
    requisitos: Callable[[ContextoClase], str | None] = field(default=lambda c: None)


def _exige(*campos: str) -> Callable[[ContextoClase], str | None]:
    nombres = {"rubrica": "rúbrica", "actividades": "sesiones", "ra": "resultados de aprendizaje",
               "contenidos": "contenidos"}

    def comprobar(c: ContextoClase) -> str | None:
        faltan = [nombres[x] for x in campos if not getattr(c, x)]
        return f"El sílabo no trae {', '.join(faltan)} para esta herramienta." if faltan else None
    return comprobar


DEFINICIONES: dict[str, Definicion] = {
    "cuestionario": Definicion("clase", es_quiz=True),
    "simulacro": Definicion("momento", es_quiz=True, requisitos=_exige("ra", "contenidos")),
    "ficha_clase": Definicion("clase", secciones=("conceptual", "aplicacion"),
                              modelos=(FichaConceptual, FichaAplicacion)),
    "repaso_momento": Definicion("momento", secciones=("repaso",), modelos=(RepasoMomento,),
                                 verificar=verificar_repaso, id_revision="repaso", requisitos=_exige("actividades")),
    "guia_evidencia": Definicion("momento", secciones=("guia",), modelos=(GuiaEvidencia,),
                                 verificar=verificar_guia_evidencia, id_revision="guia", requisitos=_exige("rubrica")),
    "estudio_caso": Definicion("momento", secciones=("caso",), modelos=(EstudioCaso,),
                               verificar=verificar_estudio_caso, id_revision="caso", requisitos=_exige("ra")),
    "guia_producto_final": Definicion("asignatura", secciones=("guia_final",), modelos=(GuiaProductoFinal,),
                                      verificar=verificar_guia_producto_final, id_revision="guia_final",
                                      requisitos=_exige("rubrica")),
}
