"""Herramientas de clase de la V2: práctica guiada, tarjetas, guía de trabajo autónomo y guion de clase.

Cada una es una sola sección con JSON de esquema cerrado y trabaja con el JSON de trabajo de la
clase: PIS, sesión con fecha, actividades con el docente, prácticas y autónomas, y contenidos.
"""
from app.agentes.mensajes import TareaLote
from app.agentes.workers.base import REGLAS_COMUNES
from app.agentes.workers.momento import NO_RESOLVER, WorkerSeccion, _Seccion
from app.herramientas.esquemas import (
    GuiaAutonoma, GuionClase, PracticaGuiada, Presentacion, Tarjetas, esquema_guia_autonoma, esquema_guion_clase,
    esquema_practica_guiada, esquema_presentacion, esquema_tarjetas,
)

PRACTICA_GUIADA = WorkerSeccion(
    "practica_guiada",
    REGLAS_COMUNES + " Preparas una práctica guiada de la clase: ejercicios resueltos paso a paso "
    "sobre los contenidos de la sesión, con datos ficticios." + NO_RESOLVER,
    _Seccion(PracticaGuiada, lambda c: esquema_practica_guiada(), lambda t: (
        "Práctica guiada de la clase: un objetivo; de 2 a 4 ejercicios sobre los contenidos de la sesión, "
        "cada uno con enunciado (datos ficticios), de 2 a 8 pasos que guíen al estudiante y el resultado "
        "esperado; y de 1 a 5 errores que conviene evitar. Si la sesión tiene actividades prácticas, "
        "los ejercicios las preparan sin resolverlas.")),
)

TARJETAS = WorkerSeccion(
    "tarjetas",
    REGLAS_COMUNES + " Preparas tarjetas de estudio (anverso: pregunta o concepto; reverso: respuesta "
    "breve) para repasar la clase." + NO_RESOLVER,
    _Seccion(Tarjetas, lambda c: esquema_tarjetas(c.contenidos), lambda t: (
        "Tarjetas de estudio de la clase: de 8 a 15 tarjetas. En «frente», una pregunta o un concepto; "
        "en «reverso», la respuesta en no más de 300 caracteres; en «contenido», el contenido de la "
        "sesión que repasa (tal cual aparece en la lista de contenidos).")),
)

GUIA_AUTONOMA = WorkerSeccion(
    "guia_autonoma",
    REGLAS_COMUNES + " Preparas la guía del trabajo autónomo de la sesión: orientas al estudiante para "
    "que haga por su cuenta la actividad autónoma que indica el sílabo." + NO_RESOLVER,
    _Seccion(GuiaAutonoma, lambda c: esquema_guia_autonoma(), lambda t: (
        "Guía del trabajo autónomo de la sesión: el objetivo; la actividad autónoma del sílabo explicada "
        "con tus palabras (máx. 500 caracteres); de 3 a 8 pasos para hacerla; el tiempo estimado según "
        "las horas autónomas del sílabo; qué debe llevar a la siguiente clase; y de 3 a 5 preguntas de "
        "autochequeo. Si hay PIS, indica en «conexion_pis» cómo esta actividad aporta a él (o deja vacío).")),
)

GUION_CLASE = WorkerSeccion(
    "guion_clase",
    REGLAS_COMUNES + " Preparas el guion de la clase para el docente: cómo conducir la sesión a partir de "
    "las actividades con el docente y prácticas del sílabo." + NO_RESOLVER,
    _Seccion(GuionClase, lambda c: esquema_guion_clase(), lambda t: (
        "Guion de clase para el docente: el objetivo de la sesión; de 3 a 6 fases en orden (inicio, "
        "desarrollo, cierre) con los minutos de cada una, qué hace el docente y qué hacen los estudiantes "
        "(sumando aproximadamente las horas con el docente del sílabo); de 2 a 5 preguntas detonantes; "
        "y en «conexion_pis», cómo se vincula la sesión con el PIS (o deja vacío si no hay PIS).")),
)

def _buscador_configurado():
    """Buscador e inserción en la base según la configuración; None si las imágenes están apagadas."""
    from contextlib import closing

    from app.config import ajustes
    from app.db.conexion import conectar
    from app.herramientas.imagenes import crear_buscador, guardar
    from app.llm.cliente import contexto_tls

    config = ajustes()
    if not config.imagenes_activas:
        return None
    def secreto(valor):
        return valor.get_secret_value() if valor else None
    buscar = crear_buscador(pexels_clave=secreto(config.pexels_api_key),
                            unsplash_clave=secreto(config.unsplash_access_key),
                            verificar=contexto_tls(config.llm_tls_estricto))

    def guardar_imagen(imagen) -> None:
        with closing(conectar(config.database_url)) as conn:
            conn.autocommit = True
            guardar(conn, imagen)
    return buscar, guardar_imagen


# Se reemplaza en las pruebas: (buscar(consulta, usadas), guardar(imagen)) o None.
BUSCADOR = _buscador_configurado
# Tiempo máximo buscando imágenes por presentación: las que falten quedan sin imagen.
PRESUPUESTO_IMAGENES_S = 60


def con_imagenes(datos: dict, tarea: TareaLote) -> dict:
    """Una imagen por diapositiva con palabras de búsqueda; sin imagen si no hay resultado o falla la red."""
    import time
    herramientas = BUSCADOR()
    diapositivas = []
    usadas: set[str] = set()
    limite = time.monotonic() + PRESUPUESTO_IMAGENES_S
    for d in datos["diapositivas"]:
        d = {**d, "imagen": None}
        if (herramientas is not None and d.get("imagen_busqueda", "").strip()
                and time.monotonic() < limite):
            buscar, guardar_imagen = herramientas
            imagen = buscar(d["imagen_busqueda"], usadas)
            if imagen is not None:
                try:
                    guardar_imagen(imagen)
                    d["imagen"] = imagen.credito()
                except Exception:  # Sin imagen antes que sin presentación.
                    d["imagen"] = None
        diapositivas.append(d)
    return {**datos, "diapositivas": diapositivas}


PRESENTACION = WorkerSeccion(
    "presentacion",
    REGLAS_COMUNES + " Preparas las diapositivas de la clase (PowerPoint) para que el docente la presente: "
    "pocas ideas por diapositiva, frases breves y notas para el docente." + NO_RESOLVER,
    _Seccion(Presentacion, lambda c: esquema_presentacion(), lambda t: (
        "Presentación de la clase: un título y de 6 a 12 diapositivas en orden: apertura (objetivo y "
        "conexión con el problema o el PIS), una o más por cada contenido de la sesión, una con la "
        "actividad práctica o con el docente (sin resolverla), una con el trabajo autónomo y un cierre. "
        "Cada diapositiva: título (máx. 80 caracteres), de 2 a 6 puntos breves (máx. 160 caracteres cada "
        "uno), «notas» para el docente con lo que debe explicar e «imagen_busqueda»: de 2 a 4 palabras EN "
        "INGLÉS para buscar una foto que ilustre el tema (sin marcas, personas famosas ni texto; vacío si "
        "la diapositiva no necesita imagen).")),
    completar=con_imagenes,
)
