"""Herramientas de clase de la V2: práctica guiada, tarjetas, guía de trabajo autónomo y guion de clase.

Cada una es una sola sección con JSON de esquema cerrado y trabaja con el JSON de trabajo de la
clase: PIS, sesión con fecha, actividades con el docente, prácticas y autónomas, y contenidos.
"""
from app.agentes.workers.base import REGLAS_COMUNES
from app.agentes.workers.momento import NO_RESOLVER, WorkerSeccion, _Seccion
from app.herramientas.esquemas import (
    GuiaAutonoma, GuionClase, PracticaGuiada, Tarjetas, esquema_guia_autonoma, esquema_guion_clase,
    esquema_practica_guiada, esquema_tarjetas,
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
