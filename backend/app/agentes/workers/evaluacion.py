"""Workers de las herramientas del plan de evaluación (V3-6).

Cada una prepara una actividad evaluable que el sílabo ya trae, sin resolverla: la práctica experimental
y su guía de observación, el foro y su rúbrica, la tarea autónoma evaluable, la prueba diagnóstica, la
entrega de avance y el insumo de respaldo de una tarea complementaria. Son de una sección, como las de
clase de la V2; los datos que no decide el modelo (plazos, tipo de evaluación) los completa el código.
"""
from datetime import timedelta

from app.agentes.mensajes import TareaLote
from app.agentes.workers.base import REGLAS_COMUNES
from app.agentes.workers.momento import NO_RESOLVER, WorkerSeccion, _Seccion
from app.herramientas.esquemas_evaluacion import (
    FichaForo, GuiaEntrega, GuiaPractica, GuiaTarea, InsumoRespaldo, PruebaDiagnostica, esquema_ficha_foro,
    esquema_guia_entrega, esquema_guia_practica, esquema_guia_tarea, esquema_insumo_respaldo,
    esquema_prueba_diagnostica,
)

PLAZO_APORTE_DIAS, PLAZO_REPLICAS_DIAS = 3, 6
EVALUACION_FORO = "Formativa · coevaluación y heteroevaluación, con la rúbrica de esta ficha."

ALINEAR = (" Cada criterio se alinea a un indicador de la rúbrica del momento (elige el más cercano en "
           "«indicador_momento»); si el momento no trae rúbrica, usa el valor fijo que ofrece el esquema.")


def _indicadores(t: TareaLote) -> list[str]:
    return [f.indicador for f in t.contexto.rubrica]


GUIA_PRACTICA = WorkerSeccion(
    "guia_practica",
    REGLAS_COMUNES + " Preparas la guía de la práctica de aprendizaje experimental de la sesión y la guía "
    "de observación con la que el docente valora el desempeño durante la práctica." + NO_RESOLVER,
    _Seccion(GuiaPractica, lambda c: esquema_guia_practica([r.id for r in c.ra]), lambda t: (
        "Guía de la práctica experimental que indica el sílabo en «actividades_practicas» de esta sesión: "
        "en «titulo», el nombre de la práctica como lo trae el sílabo (con su número si lo tiene); el objetivo; "
        "el RA que trabaja; de 1 a 8 materiales o recursos (software, equipos, datos ficticios); de 3 a 10 pasos "
        "del procedimiento que orienten sin dar los resultados; de 2 a 6 datos u observaciones que el estudiante "
        "debe registrar; en «producto», qué entrega al terminar, con tus palabras (máx. 500 caracteres); de 1 a 5 "
        "condiciones (tiempo según las horas prácticas, individual o en equipo, seguridad si aplica). Después, la "
        "guía de observación: de 4 a 8 criterios de desempeño observables durante la práctica (qué hace el "
        "estudiante, no qué sabe), cada uno con la evidencia que verá el docente cuando se logra.")),
)


def _con_plazos(datos: dict, tarea: TareaLote) -> dict:
    fecha = tarea.contexto.fecha
    aporte, replicas = fecha + timedelta(days=PLAZO_APORTE_DIAS), fecha + timedelta(days=PLAZO_REPLICAS_DIAS)
    return {**datos, "plazos": [f"Aporte inicial: hasta el {aporte:%d/%m/%Y} (sugerido; ajústalo en el aula virtual).",
                                f"Réplicas: hasta el {replicas:%d/%m/%Y} (sugerido)."],
            "evaluacion": EVALUACION_FORO}


FICHA_FORO = WorkerSeccion(
    "ficha_foro",
    REGLAS_COMUNES + " Preparas la ficha del foro de la sesión: una pregunta que exige analizar o argumentar "
    "desde el reto del proyecto formativo, no repetir definiciones, y la rúbrica con la que se valora." + NO_RESOLVER,
    _Seccion(FichaForo, lambda c: esquema_ficha_foro(c.contenidos, [f.indicador for f in c.rubrica]), lambda t: (
        "Ficha del foro que indica el sílabo en las actividades con el docente de esta sesión: en «tema», el tema "
        "específico del foro; en «contenido», el contenido de la sesión que usa (tal cual aparece en la lista); "
        "una sola «pregunta_detonante», abierta y ligada al reto del proyecto formativo, que no se pueda responder "
        "copiando una definición; en «aporte_inicial», la extensión (p. ej. 200 a 300 palabras) y que cite al "
        "menos una fuente en APA 7; en «replicas», a cuántos compañeros comenta y qué debe hacer (contrastar, "
        "ampliar o cuestionar con argumentos, no solo felicitar); en «uso_ia», lo que permite la política de IA "
        "del momento y cómo declararlo; y la rúbrica: de 3 a 5 criterios (pertinencia del análisis, "
        "fundamentación, calidad de la réplica…), cada uno con su descripción en los niveles destacado, "
        "satisfactorio y en proceso." + ALINEAR)),
    completar=_con_plazos,
)

GUIA_TAREA = WorkerSeccion(
    "guia_tarea",
    REGLAS_COMUNES + " Preparas la guía de la tarea autónoma evaluable de la sesión: el estudiante la hace sin "
    "el docente, así que la guía deja claro qué entrega, para qué, cómo y con qué criterios se califica." + NO_RESOLVER,
    _Seccion(GuiaTarea, lambda c: esquema_guia_tarea([r.id for r in c.ra], [f.indicador for f in c.rubrica]),
             lambda t: (
        "Guía de la tarea autónoma que indica el sílabo en «actividades_autonomas» de esta sesión: en «producto», "
        "el producto concreto que se entrega (ensayo de N palabras, portafolio con X evidencias, informe, video de "
        "N minutos…); en «proposito», para qué sirve, vinculado al reto del proyecto formativo y al RA del momento; "
        "el RA; si es individual o grupal; de 2 a 5 condiciones de entrega (formato, plataforma, fecha según la "
        "sesión); de 3 a 8 pasos para hacerla; de 3 a 6 criterios de calidad, cada uno con su descripción en los "
        "niveles destacado, satisfactorio y en proceso; y en «uso_ia», lo que permite la política de IA del "
        "momento y cómo declararlo." + ALINEAR)),
)

PRUEBA_DIAGNOSTICA = WorkerSeccion(
    "prueba_diagnostica",
    REGLAS_COMUNES + " Preparas la prueba diagnóstica del inicio del proyecto formativo: comprueba los "
    "conocimientos previos que el estudiante necesita para seguir los contenidos del momento. No se califica "
    "(0 %): sirve para que el docente y el estudiante sepan qué reforzar.",
    _Seccion(PruebaDiagnostica, lambda c: esquema_prueba_diagnostica(), lambda t: (
        "Prueba diagnóstica de prerrequisitos: de 3 a 5 conocimientos previos (de niveles anteriores de la "
        "carrera) que se necesitan para los contenidos y el RA de esta sesión y su momento, cada uno con por qué "
        "hace falta; y de 6 a 12 preguntas de opción múltiple, al menos una por prerrequisito (en «prerrequisito», "
        "su número en la lista, desde 1). Cada pregunta con 4 opciones plausibles, la correcta (0 a 3), una "
        "explicación breve y en «si_fallas», qué repasar. Ninguna opción puede ser «todas las anteriores» ni «ninguna de las "
        "anteriores». No preguntes los contenidos nuevos del momento: solo "
        "lo que se necesita saber antes.")),
)

GUIA_ENTREGA = WorkerSeccion(
    "guia_entrega",
    REGLAS_COMUNES + " Preparas la guía de una entrega de avance del producto del momento y la lista de cotejo "
    "con la que se verifica. Se califica solo el avance nuevo, no lo que ya se evaluó antes." + NO_RESOLVER,
    _Seccion(GuiaEntrega, lambda c: esquema_guia_entrega([f.indicador for f in c.rubrica]), lambda t: (
        "Guía de la entrega de avance que indica el sílabo en esta sesión: en «que_se_entrega», qué se entrega, "
        "con tus palabras (máx. 500 caracteres); en «insumo_previo», sobre qué producto o avance anterior se "
        "construye (o «ninguno» si es independiente); en «avance_nuevo», qué parte nueva se califica en esta "
        "entrega; de 3 a 8 pasos para prepararla; la lista de cotejo: de 5 a 10 ítems verificables (sí/no) del "
        "avance nuevo; y de 2 a 5 errores comunes." + ALINEAR)),
)

INSUMO_RESPALDO = WorkerSeccion(
    "insumo_respaldo",
    REGLAS_COMUNES + " Preparas el insumo de respaldo de una tarea complementaria: el material base que el "
    "docente entrega a quien no completó la actividad previa, para que una evaluación no bloquee la siguiente. "
    "Es un punto de partida, no la solución de la tarea de esta sesión.",
    _Seccion(InsumoRespaldo, lambda c: esquema_insumo_respaldo(), lambda t: (
        "Insumo de respaldo de la tarea de esta sesión: en «tarea», la tarea que continúa un producto previo, con "
        "tus palabras; en «insumo_previo», qué producto o avance de una sesión anterior necesita (con su sesión si "
        "el sílabo la indica); en «tipo», plantilla, proyecto_base, dataset o version_referencia; una descripción; "
        "en «contenido», el material listo para usar (estructura de la plantilla, datos ficticios en tabla, código "
        "o versión base), de 200 a 4000 caracteres, sin resolver la tarea de esta sesión; y de 2 a 5 pasos de cómo "
        "usarlo. Indica que se califica solo el avance nuevo.")),
)
