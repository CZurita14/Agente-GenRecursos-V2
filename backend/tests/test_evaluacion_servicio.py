"""Plan de evaluación implícito: reglas + IA una vez por versión del sílabo (V3-3, parte 2)."""
import json
import re

import pytest
from psycopg.types.json import Jsonb

from app.agentes.orquestador import procesar_uno
from app.evaluacion.ia import clasificar_con_ia
from app.evaluacion.norma import norma_de
from app.evaluacion.servicio import huella, plan_actividades, sin_rotulo, solicitar_clasificacion
from app.llm.cliente import ClienteSimulado
from app.silabo.modelo import SilaboUTI

DOCENTE = "docente@uti.edu.ec"


def _asignatura(conn, silabo):
    return conn.execute("insert into asignatura (dueno, codigo_pf, version_silabo, agente, silabo) "
                        "values (%s, 'PF-EVAL', 'v1', 'general', %s) returning id",
                        (DOCENTE, Jsonb(silabo.model_dump(mode="json")))).fetchone()["id"]


def _ids(mensajes):
    return re.findall(r"id=(\S+) \|", mensajes[-2]["content"] if mensajes[-1]["role"] == "system" else mensajes[-1]["content"])


def _responder(tipo_primero="portafolio", inventar=False):
    def responder(mensajes):
        ids = _ids(mensajes)
        actividades = [{"id": i, "tipo": tipo_primero if k == 0 else "avance"} for k, i in enumerate(ids[:-1])]
        if inventar:
            actividades.append({"id": "M9-S9/docente", "tipo": "foro"})
        return json.dumps({"actividades": actividades})  # El último id no vuelve: queda como avance.
    return responder


def _con_sin_rotulo(datos, bitacora="Bitácora reflexiva sobre la experiencia con el dataset del caso."):
    """El sílabo de prueba con dos columnas sin rótulo institucional."""
    sesion = datos["momentos"][0]["sesiones"][0]
    sesion["docente"]["texto"] = "Mesa redonda con invitados del sector productivo."
    sesion["autonomo"]["texto"] = bitacora
    return SilaboUTI.model_validate(datos)


def test_sin_columnas_sin_rotulo_no_se_llama_a_la_ia(conn, datos):
    for m in datos["momentos"]:
        for s in m["sesiones"]:
            s["docente"]["texto"], s["practico"]["texto"], s["autonomo"]["texto"] = (
                "Clase invertida.", "Práctica guiada.", "Ajuste.")
            s["docente"]["asincronica"] = None
    silabo = SilaboUTI.model_validate(datos)
    aid = _asignatura(conn, silabo)
    assert plan_actividades(conn, aid, silabo)[1] == "no_necesaria"
    assert solicitar_clasificacion(conn, aid, "general", silabo) == "no_necesaria"
    assert conn.execute("select count(*) n from trabajo").fetchone()["n"] == 0


def test_flujo_completo_una_vez_por_version_del_silabo(conn, datos):
    silabo = _con_sin_rotulo(datos)
    aid = _asignatura(conn, silabo)
    pendientes = sin_rotulo(silabo, norma_de(silabo.proyecto_formativo.modalidad))
    assert {"M2-S1/docente", "M2-S1/autonomo"} <= set(pendientes)
    assert plan_actividades(conn, aid, silabo)[1] == "pendiente"

    assert solicitar_clasificacion(conn, aid, "general", silabo) == "en_curso"
    assert solicitar_clasificacion(conn, aid, "general", silabo) == "en_curso"  # No duplica el trabajo.
    assert conn.execute("select count(*) n from trabajo where tipo='clasificacion'").fetchone()["n"] == 1

    cliente = ClienteSimulado({"clasificador": _responder()})
    assert procesar_uno(conn, cliente, {}, "w1", 360) is True
    estado = conn.execute("select estado from trabajo").fetchone()["estado"]
    assert estado == "listo"

    actividades, estado_ia = plan_actividades(conn, aid, silabo)
    assert estado_ia == "lista"
    por_ia = [a for a in actividades if a.origen == "ia"]
    assert len(por_ia) == len(pendientes) and not any(a.origen == "sin_rotulo" for a in actividades)
    primera = next(a for a in por_ia if f"{a.sesion}/{a.columna}" == next(iter(pendientes)))
    assert (primera.tipo, primera.evaluable, primera.calificacion, primera.instrumento) == (
        "portafolio", True, "C1_autonoma", "lista_cotejo")
    assert solicitar_clasificacion(conn, aid, "general", silabo) == "lista"  # Ya hecha: no se repite.


def test_un_silabo_nuevo_se_clasifica_de_nuevo(conn, datos):
    silabo = _con_sin_rotulo(datos)
    aid = _asignatura(conn, silabo)
    solicitar_clasificacion(conn, aid, "general", silabo)
    procesar_uno(conn, ClienteSimulado({"clasificador": _responder()}), {}, "w1", 360)
    antes = huella(silabo)
    silabo = _con_sin_rotulo(datos, "Bitácora reflexiva corregida.")
    assert huella(silabo) != antes
    assert plan_actividades(conn, aid, silabo)[1] == "pendiente"


def test_un_error_de_la_ia_queda_registrado_y_se_puede_reintentar(conn, datos):
    silabo = _con_sin_rotulo(datos)
    aid = _asignatura(conn, silabo)
    solicitar_clasificacion(conn, aid, "general", silabo)
    procesar_uno(conn, ClienteSimulado({"clasificador": ["no es json"] * 3}), {}, "w1", 360)
    assert conn.execute("select estado from trabajo").fetchone()["estado"] == "error"
    assert plan_actividades(conn, aid, silabo)[1] == "error"
    assert solicitar_clasificacion(conn, aid, "general", silabo) == "en_curso"
    assert conn.execute("select count(*) n from trabajo where estado='en_cola'").fetchone()["n"] == 1


def test_la_ia_no_puede_inventar_columnas_y_lo_que_omite_queda_como_avance():
    items = {"M1-S1/docente": "Mesa redonda.", "M1-S2/autonomo": "Bitácora."}
    tipos = clasificar_con_ia(ClienteSimulado({"clasificador": _responder("foro", inventar=True)}), "PF", "PRESENCIAL", items)
    assert tipos == {"M1-S1/docente": "foro", "M1-S2/autonomo": "avance"}


def test_el_prompt_lleva_solo_el_texto_de_las_actividades():
    cliente = ClienteSimulado({"clasificador": _responder()})
    clasificar_con_ia(cliente, "ANALISIS DE DATOS", "PRESENCIAL", {"M1-S1/docente": "Mesa redonda."})
    [llamada] = cliente.llamadas
    texto = " ".join(m["content"] for m in llamada["mensajes"])
    assert "Mesa redonda." in texto and "ANALISIS DE DATOS" in texto
    assert "@" not in texto  # Ningún correo ni dato de personas.
    assert llamada["temperatura"] == 0.0


@pytest.mark.parametrize("n", [61, 120])
def test_un_silabo_grande_se_pide_en_lotes(n):
    items = {f"M1-S{k}/docente": "Mesa redonda." for k in range(1, n + 1)}
    cliente = ClienteSimulado({"clasificador": _responder("avance")})
    clasificar_con_ia(cliente, "PF", "EN LINEA", items)
    assert len(cliente.llamadas) == 2


def _fija(tipos):
    """Cliente que responde siempre los tipos dados (por id)."""
    return ClienteSimulado({"clasificador": lambda m: json.dumps(
        {"actividades": [{"id": i, "tipo": tipos.get(i, "avance")} for i in _ids(m)]})})


def test_la_misma_actividad_repetida_se_califica_solo_en_su_ultima_sesion():
    items = {"M1-S5/practico": "Valoración respiratoria de un adulto.", "M1-S6/practico": "Valoración respiratoria de un adulto.",
             "M1-S7/practico": "Valoración respiratoria de un adulto."}
    tipos = clasificar_con_ia(_fija({k: "practica_experimental" for k in items}), "PF", "PRESENCIAL", items)
    assert tipos == {"M1-S5/practico": "avance", "M1-S6/practico": "avance", "M1-S7/practico": "practica_experimental"}


def test_la_ia_sugiere_como_maximo_dos_practicas_por_momento():
    items = {f"M{m}-S{s}/practico": f"Práctica distinta {m}-{s}." for m in (1, 2) for s in range(1, 5)}
    items["M2-S9/autonomo"] = "Bitácora final."
    tipos = clasificar_con_ia(_fija({**{k: "practica_experimental" for k in items}, "M2-S9/autonomo": "portafolio"}),
                              "PF", "PRESENCIAL", items)
    practicas = sorted(k for k, v in tipos.items() if v == "practica_experimental")
    assert practicas == ["M1-S3/practico", "M1-S4/practico", "M2-S3/practico", "M2-S4/practico"]
    assert tipos["M2-S9/autonomo"] == "portafolio"


def test_el_pedido_informa_cuantas_ya_reconoce_el_rotulo():
    cliente = _fija({})
    clasificar_con_ia(cliente, "PF", "PRESENCIAL", {"M1-S1/docente": "Mesa redonda."}, ya_reconocidas=9)
    assert "ya reconocidas por su rótulo: 9" in cliente.llamadas[0]["mensajes"][1]["content"]


# --- API: GET /asignaturas/{aid}/plan-evaluacion -------------------------------------------------

from tests.test_generacion_api import entorno  # noqa: E402,F401


def test_plan_de_evaluacion_por_api(entorno, conn):
    _, cliente, d, aid, _ = entorno
    r = d.get(f"/asignaturas/{aid}/plan-evaluacion")
    assert r.status_code == 200
    plan = r.json()
    assert plan["rol"] == "dueno" and set(plan) >= {"norma", "bloques", "actividades", "alertas", "avisos", "por_momento", "ia_restringida",
                                                    "clasificacion_ia"}
    fila = plan["actividades"][0]
    assert set(fila) >= {"sesion", "columna", "texto", "tipo", "evaluable", "calificacion", "peso_final", "herramientas"}
    assert all({"herramienta", "ambito"} <= set(h) for a in plan["actividades"] for h in a["herramientas"])
    # Cada herramienta ofrecida se puede encolar tal cual (ámbito válido, incluido el rango del simulacro).
    from app.silabo.contexto import contexto_ambito
    from app.silabo.modelo import SilaboUTI
    from app.cola.trabajos import Ambito
    silabo = SilaboUTI.model_validate(conn.execute("select silabo from asignatura where id=%s", (aid,)).fetchone()["silabo"])
    for h in {(h["ambito"]["tipo"], h["ambito"]["id"]) for a in plan["actividades"] for h in a["herramientas"]}:
        contexto_ambito(silabo, Ambito(*h))
    # Si hay columnas sin rótulo, el dueño encola la clasificación una sola vez.
    if plan["clasificacion_ia"] == "en_curso":
        d.get(f"/asignaturas/{aid}/plan-evaluacion")
        assert conn.execute("select count(*) n from trabajo where tipo='clasificacion'").fetchone()["n"] == 1
    assert cliente("intruso@uti.edu.ec").get(f"/asignaturas/{aid}/plan-evaluacion").status_code == 403


# --- V4-4: el docente confirma o ajusta los pesos ------------------------------------------------

from tests.test_generacion_api import HEADERS  # noqa: E402

def _sin_ia_pendiente(conn, d, aid):
    """La clasificación con IA queda lista (sin cambios) para poder confirmar los pesos."""
    d.get(f"/asignaturas/{aid}/plan-evaluacion")
    conn.execute("update clasificacion_silabo set estado='lista', tipos='{}'::jsonb where asignatura_id=%s", (aid,))
    return d.get(f"/asignaturas/{aid}/plan-evaluacion").json()


def _ajuste(plan, calificacion, primero):
    """Pesos actuales con la calificación repartida dando `primero` a su primera actividad."""
    pesos = {a["clave"]: a["peso_bloque"] for a in plan["actividades"] if a["evaluable"] and a["calificacion"]}
    g = next(g for g in plan["grupos"] if g["calificacion"] == calificacion)
    pesos[g["claves"][0]], pesos[g["claves"][1]] = primero, round(g["peso"] - primero, 2)
    return pesos, g["claves"][0]


def test_el_docente_ajusta_dentro_de_la_calificacion_y_puede_restaurar(entorno, conn):
    _, cliente, d, aid, _ = entorno
    plan = _sin_ia_pendiente(conn, d, aid)
    assert plan["pesos"]["origen"] == "sugeridos" and plan["grupos"]
    pesos, k = _ajuste(plan, "C3_formativa", 7.5)
    r = d.put(f"/asignaturas/{aid}/plan-evaluacion/pesos", json={"pesos": pesos}, headers=HEADERS)
    assert r.status_code == 200, r.text
    nuevo = r.json()
    assert nuevo["pesos"]["origen"] == "docente" and nuevo["pesos"]["confirmado_por"] == "dueno@uti.edu.ec"
    assert next(a for a in nuevo["actividades"] if a["clave"] == k)["peso_bloque"] == 7.5
    assert nuevo["por_bloque"] == plan["por_bloque"]  # Cada calificación conserva su % de la norma.
    # Un reparto que cambia el total de la calificación se rechaza con el motivo.
    malo, _ = _ajuste(plan, "C3_formativa", 9.0)
    malo[k] = 9.5
    r = d.put(f"/asignaturas/{aid}/plan-evaluacion/pesos", json={"pesos": malo}, headers=HEADERS)
    assert r.status_code == 422 and "la norma pide" in r.text
    # El lector no confirma; el dueño vuelve a los sugeridos.
    from tests.acceso import dar_acceso
    dar_acceso(conn, aid, "lector@uti.edu.ec", "lector")
    assert cliente("lector@uti.edu.ec").put(f"/asignaturas/{aid}/plan-evaluacion/pesos",
                                            json={"pesos": pesos}, headers=HEADERS).status_code == 403
    r = d.delete(f"/asignaturas/{aid}/plan-evaluacion/pesos", headers=HEADERS)
    assert r.status_code == 200 and r.json()["pesos"]["origen"] == "sugeridos"


def test_si_cambia_el_silabo_los_pesos_vuelven_a_sugeridos_y_se_avisa(entorno, conn, datos):
    from app.silabo.modelo import SilaboUTI
    app, _, d, aid, _ = entorno
    plan = _sin_ia_pendiente(conn, d, aid)
    pesos, _ = _ajuste(plan, "C3_formativa", 7.5)
    assert d.put(f"/asignaturas/{aid}/plan-evaluacion/pesos", json={"pesos": pesos}, headers=HEADERS).status_code == 200
    datos["momentos"][0]["evidencia"] += " Versión revisada."
    app.state.asignaturas.guardar("dueno@uti.edu.ec", SilaboUTI.model_validate(datos))
    plan = d.get(f"/asignaturas/{aid}/plan-evaluacion").json()
    assert plan["pesos"]["origen"] == "sugeridos" and plan["pesos"]["desactualizados"] is True
