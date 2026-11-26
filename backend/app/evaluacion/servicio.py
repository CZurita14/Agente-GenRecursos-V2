"""Plan de evaluación implícito en el sílabo: reglas + IA (una vez por versión del sílabo) (V3-3).

`plan_actividades` une lo que leen las reglas con lo que la IA clasificó para las columnas sin rótulo.
`solicitar_clasificacion` encola, como máximo una vez por huella del sílabo, el trabajo que hace el worker
(`procesar_clasificacion`). Si no hay columnas sin rótulo, no se llama a la IA.
"""
import hashlib
import logging

from psycopg.types.json import Jsonb

from app.cola.trabajos import Ambito, encolar, renovar_lease, terminar
from app.evaluacion.clasificador import Actividad, actividad_de, clasificar, sin_duplicados, textos_de
from app.evaluacion.ia import clasificar_con_ia
from app.evaluacion.norma import Norma, norma_de
from app.llm.cliente import ServidorNoDisponible
from app.silabo.modelo import SilaboUTI

registro = logging.getLogger(__name__)
HERRAMIENTA = "clasificacion"


def huella(silabo: SilaboUTI) -> str:
    return hashlib.sha256(silabo.model_dump_json().encode("utf-8")).hexdigest()


def sin_rotulo(silabo: SilaboUTI, norma: Norma | None) -> dict[str, str]:
    """Texto de las columnas que las reglas no reconocen, por clave «M1-S4/autonomo»."""
    textos = textos_de(silabo)
    return {f"{a.sesion}/{a.columna}": textos[f"{a.sesion}/{a.columna}"]
            for a in clasificar(silabo, norma) if a.origen == "sin_rotulo"}


def plan_actividades(conn, asignatura_id, silabo: SilaboUTI) -> tuple[list[Actividad], str]:
    """Actividades del sílabo y el estado de la IA: no_necesaria | pendiente | en_curso | lista | error."""
    norma = norma_de(silabo.proyecto_formativo.modalidad)
    actividades = clasificar(silabo, norma)
    if not any(a.origen == "sin_rotulo" for a in actividades):
        return actividades, "no_necesaria"
    fila = conn.execute("select estado, tipos from clasificacion_silabo where asignatura_id=%s and huella=%s",
                        (asignatura_id, huella(silabo))).fetchone()
    if fila is None:
        return actividades, "pendiente"
    if fila["estado"] != "lista":
        return actividades, fila["estado"]
    textos = textos_de(silabo)
    tipos = fila["tipos"]
    resultado = []
    for a in actividades:
        clave = f"{a.sesion}/{a.columna}"
        if a.origen == "sin_rotulo" and clave in tipos:
            resultado.append(actividad_de(a.sesion, a.columna, tipos[clave], textos[clave], norma, "ia"))
        else:
            resultado.append(a)
    return sin_duplicados(resultado), "lista"


def solicitar_clasificacion(conn, asignatura_id, agente: str, silabo: SilaboUTI) -> str:
    """Encola la clasificación con IA si hace falta y no está hecha ni en curso; devuelve el estado."""
    if not sin_rotulo(silabo, norma_de(silabo.proyecto_formativo.modalidad)):
        return "no_necesaria"
    h = huella(silabo)
    with conn.transaction():
        fila = conn.execute("select estado from clasificacion_silabo where asignatura_id=%s and huella=%s for update",
                            (asignatura_id, h)).fetchone()
        if fila is not None and fila["estado"] in ("en_curso", "lista"):
            return fila["estado"]
        trabajo_id = encolar(conn, asignatura_id=asignatura_id, agente=agente, ambito=Ambito("asignatura", "asignatura"),
                             herramienta=HERRAMIENTA, parametros={"silabo": silabo.model_dump(mode="json"), "huella": h},
                             tipo="clasificacion")
        conn.execute(
            "insert into clasificacion_silabo (asignatura_id, huella, estado, trabajo_id) values (%s,%s,'en_curso',%s) "
            "on conflict (asignatura_id, huella) do update set estado='en_curso', trabajo_id=excluded.trabajo_id, "
            "actualizado=now()", (asignatura_id, h, trabajo_id))
    return "en_curso"


def procesar_clasificacion(conn, trabajo, cliente, worker_id: str, lease_s: int) -> None:
    """Trabajo del worker: la IA clasifica las columnas sin rótulo y se guarda su tipo."""
    cerco = dict(worker_id=worker_id, lease_version=trabajo.lease_version)
    silabo = SilaboUTI.model_validate(trabajo.parametros["silabo"])
    h = trabajo.parametros["huella"]
    try:
        norma = norma_de(silabo.proyecto_formativo.modalidad)
        items = sin_rotulo(silabo, norma)
        pf = silabo.proyecto_formativo
        tipos = clasificar_con_ia(
            cliente, pf.nombre, pf.modalidad, items, ya_reconocidas=sum(a.evaluable for a in clasificar(silabo, norma)),
            trabajo_id=trabajo.id, asignatura_id=trabajo.asignatura_id,
            renovar=lambda: renovar_lease(conn, trabajo.id, worker_id, lease_s, lease_version=trabajo.lease_version))
    except ServidorNoDisponible:
        raise  # El orquestador lo pone en espera y se reintenta; sigue «en_curso».
    except Exception as error:
        conn.execute("update clasificacion_silabo set estado='error', actualizado=now() "
                     "where asignatura_id=%s and huella=%s", (trabajo.asignatura_id, h))
        raise error
    with conn.transaction():
        conn.execute("update clasificacion_silabo set estado='lista', tipos=%s, actualizado=now() "
                     "where asignatura_id=%s and huella=%s", (Jsonb(tipos), trabajo.asignatura_id, h))
        terminar(conn, trabajo.id, "listo", **cerco)
