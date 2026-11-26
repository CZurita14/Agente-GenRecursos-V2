"""Qué herramientas preparan cada tipo de actividad del plan de evaluación (V3-5, V3-6).

Cada herramienta lleva su ámbito: las de clase se generan para la sesión de la actividad, las de momento para
su momento y las del proyecto formativo para la asignatura. Las actividades de avance reciben las herramientas
ligeras de clase. El simulacro de una prueba sumativa es acumulativo: cubre los momentos desde la prueba
anterior («M1-M2»), como la prueba del parcial.
"""
import re

CLASE, MOMENTO, ASIGNATURA, ACUMULADO = "clase", "momento", "asignatura", "acumulado"

POR_TIPO: dict[str, tuple[tuple[str, str], ...]] = {
    "diagnostica": (("prueba_diagnostica", CLASE),),
    "prueba_sumativa": (("simulacro", ACUMULADO), ("repaso_momento", MOMENTO)),
    "cuestionario": (("cuestionario", CLASE), ("tarjetas", CLASE)),
    "cuestionario_autonomo": (("guia_tarea", CLASE), ("cuestionario", CLASE)),
    "foro": (("ficha_foro", CLASE),),
    "estudio_caso": (("estudio_caso", MOMENTO), ("rubrica_momento", MOMENTO)),
    "practica_experimental": (("guia_practica", CLASE), ("practica_guiada", CLASE)),
    "proyecto_final": (("guia_producto_final", ASIGNATURA), ("rubrica_final", ASIGNATURA)),
    "exposicion_final": (("guia_producto_final", ASIGNATURA), ("rubrica_final", ASIGNATURA),
                         ("autoevaluacion_final", ASIGNATURA)),
    "ensayo": (("guia_tarea", CLASE), ("rubrica_momento", MOMENTO)),
    "portafolio": (("guia_tarea", CLASE), ("lista_evidencia", MOMENTO)),
    "taller_coevaluacion": (("rubrica_momento", MOMENTO), ("autoevaluacion_rubrica", MOMENTO)),
    "autoevaluacion": (("autoevaluacion_rubrica", MOMENTO),),
    "participacion": (("guion_clase", CLASE),),
    "entrega_avance": (("guia_entrega", CLASE), ("insumo_respaldo", CLASE)),
    "avance": (("practica_guiada", CLASE), ("tarjetas", CLASE), ("guion_clase", CLASE)),
}

NOMBRE_TIPO = {
    "diagnostica": "Evaluación diagnóstica", "prueba_sumativa": "Prueba sumativa", "cuestionario": "Cuestionario",
    "cuestionario_autonomo": "Lectura con cuestionario", "foro": "Foro", "estudio_caso": "Estudio de caso",
    "practica_experimental": "Práctica experimental", "proyecto_final": "Proyecto final",
    "exposicion_final": "Exposición del proyecto final", "ensayo": "Ensayo", "portafolio": "Portafolio",
    "taller_coevaluacion": "Taller con coevaluación", "autoevaluacion": "Autoevaluación",
    "participacion": "Participación", "entrega_avance": "Entrega de avance", "avance": "Actividad de avance",
}


def _orden(sesion: str) -> tuple[int, int]:
    m = re.fullmatch(r"M(\d+)-S(\d+)", sesion)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def rangos_acumulados(sumativas: list[str]) -> dict[str, str]:
    """Momentos que cubre cada prueba sumativa: desde el siguiente a la prueba anterior hasta el suyo.

    «M2-S4» y «M4-S4» → {"M2-S4": "M1-M2", "M4-S4": "M3-M4"}. Un solo momento queda como «M<n>».
    """
    rangos, previo = {}, 0
    for sesion in sorted(set(sumativas), key=_orden):
        momento = _orden(sesion)[0]
        desde = min(previo + 1, momento)
        rangos[sesion] = f"M{momento}" if desde == momento else f"M{desde}-M{momento}"
        previo = momento
    return rangos


def herramientas_de(tipo: str, sesion: str, acumulado: str | None = None) -> list[dict]:
    """[{herramienta, ambito: {tipo, id}}] para una actividad de esa sesión («M3-S4»).

    `acumulado` es el rango de momentos de la prueba («M1-M2»); sin él, el simulacro es del momento.
    """
    momento = sesion.split("-")[0]
    ids = {CLASE: sesion, MOMENTO: momento, ASIGNATURA: "asignatura", ACUMULADO: acumulado or momento}
    tipos = {ACUMULADO: MOMENTO}
    return [{"herramienta": h, "ambito": {"tipo": tipos.get(ambito, ambito), "id": ids[ambito]}}
            for h, ambito in POR_TIPO.get(tipo, ())]
