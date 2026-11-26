"""Qué es cada herramienta con IA para el coordinador (P3b): ámbito, forma y controles.

Separado de los workers (que solo generan) para que el coordinador no dependa de su
clase: las pruebas sustituyen workers sin perder esta metadata.
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.agentes.verificador import (
    verificar_herramienta_clase,
    verificar_estudio_caso, verificar_ficha, verificar_guia_evidencia, verificar_guia_producto_final,
    verificar_guia_estudio, verificar_repaso,
    verificar_ficha_foro, verificar_guia_entrega, verificar_guia_practica, verificar_guia_tarea,
    verificar_insumo_respaldo, verificar_prueba_diagnostica,
)
from app.herramientas.esquemas_evaluacion import (
    FichaForo, GuiaEntrega, GuiaPractica, GuiaTarea, InsumoRespaldo, PruebaDiagnostica,
)
from app.herramientas.esquemas import (
    GuiaAutonoma, GuionClase, PracticaGuiada, Presentacion, Tarjetas,
    EstudioCaso, FichaAplicacion, FichaConceptual, GuiaEvidencia, GuiaProductoFinal, RepasoMomento,
    GuiaAplicacion, GuiaDesarrollo, GuiaIntroduccion,
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


def _con_actividad(campo: str, nombre: str) -> Callable[[ContextoClase], str | None]:
    """La herramienta necesita esa actividad de la sesión (JSON de trabajo de la V2)."""
    def comprobar(c: ContextoClase) -> str | None:
        a = getattr(c, campo)
        return None if a is not None and a.texto.strip() else f"El sílabo no trae {nombre} para esta sesión."
    return comprobar


def _todos(*comprobaciones: Callable[[ContextoClase], str | None]) -> Callable[[ContextoClase], str | None]:
    def comprobar(c: ContextoClase) -> str | None:
        return next((m for f in comprobaciones if (m := f(c))), None)
    return comprobar


def _evaluacion(seccion: str, modelo, verificar, requisitos) -> Definicion:
    """Herramienta de clase del plan de evaluación (V3-6): una sección con su verificador propio."""
    return Definicion("clase", secciones=(seccion,), modelos=(modelo,), verificar=verificar, id_revision=seccion,
                      requisitos=requisitos)


def _clase(nombre: str, modelo, requisitos=None) -> Definicion:
    return Definicion("clase", secciones=(nombre,), modelos=(modelo,), verificar=verificar_herramienta_clase(nombre),
                      id_revision=nombre, requisitos=requisitos or _exige("contenidos"))


# Se ofrecen desde el plan de evaluación, junto a la actividad evaluable que preparan (V3-6),
# no en el catálogo general de «Más herramientas».
DEL_PLAN = frozenset({"guia_practica", "ficha_foro", "guia_tarea", "prueba_diagnostica", "guia_entrega",
                      "insumo_respaldo"})

DEFINICIONES: dict[str, Definicion] = {
    "practica_guiada": _clase("practica", PracticaGuiada),
    "tarjetas": _clase("mazo", Tarjetas),
    "guia_autonoma": _clase("guia_autonoma", GuiaAutonoma,
                            _con_actividad("actividad_autonoma", "actividades de trabajo autónomo")),
    "presentacion": _clase("presentacion", Presentacion),
    "guion_clase": _clase("guion", GuionClase, _con_actividad("actividad_docente", "actividades con el docente")),
    "cuestionario": Definicion("clase", es_quiz=True),
    "simulacro": Definicion("momento", es_quiz=True, requisitos=_exige("ra", "contenidos")),
    "ficha_clase": Definicion("clase", secciones=("conceptual", "aplicacion"),
                              modelos=(FichaConceptual, FichaAplicacion)),
    "guia_estudio": Definicion("momento", secciones=("introduccion", "desarrollo_1", "desarrollo_2", "aplicacion"),
                               modelos=(GuiaIntroduccion, GuiaDesarrollo, GuiaDesarrollo, GuiaAplicacion),
                               verificar=verificar_guia_estudio, id_revision="guia_estudio",
                               requisitos=_exige("contenidos", "ra")),
    "repaso_momento": Definicion("momento", secciones=("repaso",), modelos=(RepasoMomento,),
                                 verificar=verificar_repaso, id_revision="repaso", requisitos=_exige("actividades")),
    "guia_evidencia": Definicion("momento", secciones=("guia",), modelos=(GuiaEvidencia,),
                                 verificar=verificar_guia_evidencia, id_revision="guia", requisitos=_exige("rubrica")),
    "estudio_caso": Definicion("momento", secciones=("caso",), modelos=(EstudioCaso,),
                               verificar=verificar_estudio_caso, id_revision="caso", requisitos=_exige("ra")),
    "guia_producto_final": Definicion("asignatura", secciones=("guia_final",), modelos=(GuiaProductoFinal,),
                                      verificar=verificar_guia_producto_final, id_revision="guia_final",
                                      requisitos=_exige("rubrica")),
    # V3-6: preparan las actividades evaluables del plan implícito en el sílabo.
    "guia_practica": _evaluacion("guia_practica", GuiaPractica, verificar_guia_practica, _todos(
        _exige("ra"), _con_actividad("actividad_practica", "actividades práctico-experimentales"))),
    "ficha_foro": _evaluacion("foro", FichaForo, verificar_ficha_foro, _todos(
        _exige("contenidos"), _con_actividad("actividad_docente", "actividades con el docente"))),
    "guia_tarea": _evaluacion("tarea", GuiaTarea, verificar_guia_tarea, _todos(
        _exige("ra"), _con_actividad("actividad_autonoma", "actividades de trabajo autónomo"))),
    "prueba_diagnostica": _evaluacion("diagnostica", PruebaDiagnostica, verificar_prueba_diagnostica,
                                      _exige("contenidos")),
    "guia_entrega": _evaluacion("entrega", GuiaEntrega, verificar_guia_entrega, _exige("contenidos")),
    "insumo_respaldo": _evaluacion("insumo", InsumoRespaldo, verificar_insumo_respaldo, _exige("contenidos")),
}
