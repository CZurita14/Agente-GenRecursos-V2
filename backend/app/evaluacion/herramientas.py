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
    # El insumo de respaldo no va por tipo: se ofrece en cualquier tarea evaluable complementaria (V4-2, §6.3).
    "entrega_avance": (("guia_entrega", CLASE),),
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


def herramientas_de(tipo: str, sesion: str, acumulado: str | None = None, dependencia=None) -> list[dict]:
    """[{herramienta, ambito: {tipo, id}}] para una actividad de esa sesión («M3-S4»).

    `acumulado` es el rango de momentos de la prueba («M1-M2»); sin él, el simulacro es del momento.
    `dependencia` (de `app.evaluacion.dependencias`): si la tarea es complementaria se agrega el insumo de respaldo,
    con el insumo previo detectado como indicación para la IA (§6.3).
    """
    momento = sesion.split("-")[0]
    ids = {CLASE: sesion, MOMENTO: momento, ASIGNATURA: "asignatura", ACUMULADO: acumulado or momento}
    tipos = {ACUMULADO: MOMENTO}
    salida = [{"herramienta": h, "ambito": {"tipo": tipos.get(ambito, ambito), "id": ids[ambito]}}
              for h, ambito in POR_TIPO.get(tipo, ())]
    if dependencia is not None and dependencia.tipo == "complementaria" and tipo in EVALUABLES_CON_TAREA:
        salida.append({"herramienta": "insumo_respaldo", "ambito": {"tipo": CLASE, "id": sesion},
                       "instrucciones": indicacion_insumo(dependencia)})
    return salida


# Tipos evaluables que son tareas (producen un producto); en ellos el insumo de respaldo tiene sentido.
EVALUABLES_CON_TAREA = {"entrega_avance", "practica_experimental", "ensayo", "portafolio", "cuestionario_autonomo",
                        "proyecto_final", "estudio_caso"}


def indicacion_insumo(d) -> str:
    """Lo que el sistema sabe del insumo previo, como indicación para el insumo de respaldo."""
    from app.evaluacion.dependencias import legible
    if d.origen:
        return (f"La tarea continúa «{d.insumo}», que se produce en {legible(d.origen)}. El insumo de respaldo "
                "es una versión base de ese producto para quien no lo completó.")
    if d.insumo:
        return f"La tarea continúa «{d.insumo}» de una sesión anterior; el insumo de respaldo es una versión base de él."
    return "La tarea continúa un producto de una sesión anterior; identifícalo en el sílabo y prepara su versión base."


def disponibles(silabo, ofrecidas: list[dict], cache: dict | None = None) -> list[dict]:
    """Solo las herramientas que se pueden encolar con este sílabo: ámbito existente y lo que su esquema necesita.

    Así el plan no ofrece, por ejemplo, la guía del producto final si el sílabo no trae la rúbrica final, ni
    herramientas con IA en un momento cuya política excluye la IA en una evaluación (§9.4).
    """
    from app.agentes.workers.definiciones import DEFINICIONES
    from app.cola.trabajos import Ambito
    from app.herramientas.sin_ia import HERRAMIENTAS_SIN_IA, generar_sin_ia
    from app.recursos.servicio import _restriccion
    from app.silabo.contexto import contexto_ambito

    cache = {} if cache is None else cache  # (herramienta, ámbito) → se puede; compartido entre actividades

    def se_puede(h: dict) -> bool:
        nombre, ambito = h["herramienta"], h["ambito"]
        try:
            if nombre in HERRAMIENTAS_SIN_IA:
                generar_sin_ia(nombre, silabo, ambito["id"])
                return True
            if _restriccion(silabo, ambito["tipo"], ambito["id"]):
                return False
            return DEFINICIONES[nombre].requisitos(contexto_ambito(silabo, Ambito(ambito["tipo"], ambito["id"]))) is None
        except (KeyError, ValueError):
            return False

    salida = []
    for h in ofrecidas:
        clave = (h["herramienta"], h["ambito"]["id"])
        if clave not in cache:
            cache[clave] = se_puede(h)
        if cache[clave]:
            salida.append(h)
    return salida
