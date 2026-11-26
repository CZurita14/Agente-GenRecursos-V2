"""Qué herramientas preparan cada tipo de actividad del plan de evaluación (V3-5).

Cada herramienta lleva su ámbito: las de clase se generan para la sesión de la actividad, las de momento para
su momento y las del proyecto formativo para la asignatura. Las actividades de avance reciben las herramientas
ligeras de clase. Las herramientas nuevas de la V3-6 se agregan aquí cuando existan.
"""
CLASE, MOMENTO, ASIGNATURA = "clase", "momento", "asignatura"

POR_TIPO: dict[str, tuple[tuple[str, str], ...]] = {
    "diagnostica": (("cuestionario", CLASE),),
    "prueba_sumativa": (("simulacro", MOMENTO), ("repaso_momento", MOMENTO)),
    "cuestionario": (("cuestionario", CLASE), ("tarjetas", CLASE)),
    "cuestionario_autonomo": (("guia_autonoma", CLASE), ("cuestionario", CLASE)),
    "foro": (("guia_autonoma", CLASE),),
    "estudio_caso": (("estudio_caso", MOMENTO), ("rubrica_momento", MOMENTO)),
    "practica_experimental": (("practica_guiada", CLASE), ("rubrica_momento", MOMENTO)),
    "proyecto_final": (("guia_producto_final", ASIGNATURA), ("rubrica_final", ASIGNATURA)),
    "exposicion_final": (("guia_producto_final", ASIGNATURA), ("rubrica_final", ASIGNATURA),
                         ("autoevaluacion_final", ASIGNATURA)),
    "ensayo": (("guia_autonoma", CLASE), ("rubrica_momento", MOMENTO)),
    "portafolio": (("guia_autonoma", CLASE), ("lista_evidencia", MOMENTO)),
    "taller_coevaluacion": (("rubrica_momento", MOMENTO), ("autoevaluacion_rubrica", MOMENTO)),
    "autoevaluacion": (("autoevaluacion_rubrica", MOMENTO),),
    "participacion": (("guion_clase", CLASE),),
    "entrega_avance": (("guia_evidencia", MOMENTO), ("lista_evidencia", MOMENTO)),
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


def herramientas_de(tipo: str, sesion: str) -> list[dict]:
    """[{herramienta, ambito: {tipo, id}}] para una actividad de esa sesión («M3-S4»)."""
    momento = sesion.split("-")[0]
    ids = {CLASE: sesion, MOMENTO: momento, ASIGNATURA: "asignatura"}
    return [{"herramienta": h, "ambito": {"tipo": ambito, "id": ids[ambito]}} for h, ambito in POR_TIPO.get(tipo, ())]
