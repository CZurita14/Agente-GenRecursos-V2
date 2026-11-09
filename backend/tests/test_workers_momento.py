"""P3b T5: repaso integrador, guía de la evidencia y estudio de caso (catálogo #9, #14, #10)."""
import json
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from app.agentes.coordinador import Coordinador
from app.agentes.facultades import cargar_perfiles, estilo_para
from app.agentes.mensajes import Encargo, EstiloFacultad, TareaLote
from app.agentes.verificador import verificar_estudio_caso, verificar_guia_evidencia, verificar_repaso
from app.agentes.workers.momento import ESCENARIOS_DE_RESPALDO, ESTUDIO_CASO, GUIA_EVIDENCIA, REPASO, escenario_para
from app.cola.trabajos import Ambito, encolar, tomar_siguiente
from app.herramientas.esquemas import EstudioCaso, GuiaEvidencia, RepasoMomento
from app.llm.cliente import ClienteSimulado
from app.silabo.contexto import contexto_momento
from tests.test_coordinador import RAIZ

PERFIL = cargar_perfiles(RAIZ / "agentes")["ingenierias"]
LARGO = "Una distribuidora ficticia registra los tiempos de entrega de sus pedidos durante seis semanas. " * 4


def _respuestas(ctx):
    ids = [a.split(":", 1)[0] for a in ctx.actividades]
    return {
        "repaso_momento": {"sesiones": [{"clase_id": i, "ideas_clave": ["idea a", "idea b", "idea c"]} for i in ids],
                           "conexion_ra": "Las cuatro sesiones construyen el contraste de hipótesis del RA3 paso a paso.",
                           "preguntas_repaso": ["¿Pregunta uno?", "¿Pregunta dos?", "¿Pregunta tres?"]},
        "guia_evidencia": {"que_se_pide": "Un informe técnico propio que contraste hipótesis con datos del proyecto.",
                           "como_se_valora": [{"indicador": f.indicador, "que_observar": "Que la decisión esté justificada."}
                                              for f in ctx.rubrica],
                           "errores_comunes": ["Error uno", "Error dos", "Error tres"],
                           "autochequeo": ["¿Uno?", "¿Dos?", "¿Tres?"]},
        "estudio_caso": {"caso": "", "ra": ctx.ra[0].id,
                         "preguntas": [{"nivel": n, "pregunta": f"¿Qué concluye en el nivel {n}?",
                                        "respuesta_orientativa": "Una respuesta orientativa suficiente."}
                                       for n in ("receptivo", "resolutivo", "reflexivo")]},
    }


def _revisor(resuelve=False):
    return lambda m: json.dumps({"resuelve_entregable": resuelve, "entregable": "la evidencia",
                                 "motivo": "entrega la solución" if resuelve else ""})


def _ejecutar(conn, silabo, herramienta, worker, revisor=None):
    ctx = contexto_momento(silabo, "M3")
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('p@uti.edu.ec',%s,%s,'ingenierias',%s) returning id",
                       (ctx.codigo_pf, ctx.version_silabo, Jsonb(silabo.model_dump(mode="json")))).fetchone()["id"]
    encolar(conn, asignatura_id=aid, agente="ingenierias", ambito=Ambito("momento", "M3"),
            herramienta=herramienta, parametros={})
    t = tomar_siguiente(conn, "w1", 360)
    e = Encargo(trabajo_id=t.id, asignatura_id=aid, codigo_pf=ctx.codigo_pf, version_silabo=ctx.version_silabo,
                carrera=ctx.carrera, nivel=ctx.nivel, ambito=t.ambito, herramienta=herramienta,
                perfil_dificultad="fundamentacion")
    datos = _respuestas(ctx)[herramienta]

    def worker_responde(mensajes):
        if herramienta == "estudio_caso":
            escenario = mensajes[-1]["content"].split("ambientado en: ")[1].split(". ")[0]
            return json.dumps({**datos, "caso": f"Caso ficticio sobre {escenario}. " + LARGO})
        return json.dumps(datos)

    cliente = ClienteSimulado({"worker": worker_responde, "revisor": revisor or _revisor()})
    cierre = Coordinador(PERFIL, {herramienta: worker}, cliente).ejecutar(conn, t, e, ctx, lambda: True)
    return cierre, conn.execute("select * from recurso").fetchone()


@pytest.mark.parametrize("herramienta, worker, clave", [
    ("repaso_momento", REPASO, "repaso"), ("guia_evidencia", GUIA_EVIDENCIA, "guia"),
    ("estudio_caso", ESTUDIO_CASO, "caso")])
def test_herramientas_de_momento_listas(conn, silabo, herramienta, worker, clave):
    cierre, r = _ejecutar(conn, silabo, herramienta, worker)
    assert cierre.estado == "listo", json.dumps([r["evidencia"]["verificaciones"], r["evidencia"]["veredictos"]], ensure_ascii=True)
    assert set(r["contenido"]) == {clave} and r["evidencia"]["veredictos"] == {clave: "ok"}


def test_repaso_m3_cubre_las_sesiones(conn, silabo):
    _, r = _ejecutar(conn, silabo, "repaso_momento", REPASO)
    assert [s["clase_id"] for s in r["contenido"]["repaso"]["sesiones"]] == ["M3-S1", "M3-S2", "M3-S3", "M3-S4"]


def test_revisor_devuelve_guia_que_resuelve(conn, silabo):
    cierre, r = _ejecutar(conn, silabo, "guia_evidencia", GUIA_EVIDENCIA, _revisor(resuelve=True))
    assert cierre.estado == "requiere_revision" and "resuelve" in r["evidencia"]["veredictos"]["guia"]


def test_guia_no_reproduce_la_evidencia(silabo):
    ctx = contexto_momento(silabo, "M3")
    guia = _respuestas(ctx)["guia_evidencia"]
    assert verificar_guia_evidencia(guia, ctx) == []
    copia = " ".join(ctx.entregables_momento[0].split()[:14])
    assert verificar_guia_evidencia({**guia, "que_se_pide": copia}, ctx) == []  # Citarla al explicarla vale.
    assert verificar_guia_evidencia({**guia, "errores_comunes": ["a", "b", copia]}, ctx)
    ajeno = {**guia, "como_se_valora": [{"indicador": "Otro indicador", "que_observar": "x" * 20}]}
    assert "indicador ajeno" in " ".join(verificar_guia_evidencia(ajeno, ctx))


def test_caso_distinto_del_evaluado(silabo):
    ctx = contexto_momento(silabo, "M3")
    base = {"ra": ctx.ra[0].id, "preguntas": _respuestas(ctx)["estudio_caso"]["preguntas"]}
    bueno = {**base, "escenario": "demoras en la entrega de pedidos de una distribuidora",
             "caso": "Una distribuidora registra demoras de pedidos. " + LARGO}
    assert verificar_estudio_caso(bueno, ctx) == []
    evaluado = {**bueno, "escenario": "picos de tráfico normales y ataques"}
    assert "coincide" in " ".join(verificar_estudio_caso(evaluado, ctx))
    otro = {**bueno, "caso": "Un hospital ficticio mide camas ocupadas. " * 10}
    assert "no se ambienta" in " ".join(verificar_estudio_caso(otro, ctx))
    assert "RA ajeno" in " ".join(verificar_estudio_caso({**bueno, "ra": "RA9"}, ctx))


def test_escenario_para_evita_el_entregable(silabo):
    ctx = contexto_momento(silabo, "M3")
    estilo = EstiloFacultad(tipos_de_caso=[], software_habitual=[],
                            escenarios=["picos de tráfico de red", "tiempos de respuesta de una API REST"])
    tarea = TareaLote(trabajo_id=uuid4(), asignatura_id=uuid4(), lote=1, ronda=0, contexto=ctx, estilo=estilo,
                      plan=[], ya_generado=[])
    assert escenario_para(tarea) == "tiempos de respuesta de una API REST"
    sin_libres = tarea.model_copy(update={"estilo": estilo.model_copy(update={"escenarios": ["picos de tráfico"]})})
    assert escenario_para(sin_libres) in ESCENARIOS_DE_RESPALDO
    assert escenario_para(tarea.model_copy(update={"estilo": estilo_para(PERFIL, ctx.carrera)})) != ""


def test_repaso_con_sesion_ajena(silabo):
    ctx = contexto_momento(silabo, "M3")
    malo = _respuestas(ctx)["repaso_momento"] | {"sesiones": [{"clase_id": "M2-S1", "ideas_clave": ["a", "b", "c"]}]}
    assert "ajenas" in " ".join(verificar_repaso(malo, ctx))


@pytest.mark.parametrize("modelo, datos", [
    (RepasoMomento, {"sesiones": [], "conexion_ra": "x" * 40, "preguntas_repaso": ["a", "b", "c"], "extra": 1}),
    (GuiaEvidencia, {"que_se_pide": "x" * 40, "como_se_valora": [], "errores_comunes": [], "autochequeo": [],
                     "respuesta": "la solución"}),
    (EstudioCaso, {"caso": "x" * 300, "preguntas": [], "ra": "RA1", "solucion": "x"})])
def test_esquemas_rechazan_campos_extra(modelo, datos):
    with pytest.raises(ValidationError):
        modelo.model_validate(datos)


# --- T6: guía del producto final (asignatura) ------------------------------------
from app.agentes.verificador import verificar_guia_producto_final  # noqa: E402
from app.agentes.workers.momento import GUIA_PRODUCTO_FINAL  # noqa: E402
from app.silabo.contexto import contexto_asignatura  # noqa: E402
from app.silabo.modelo import SilaboUTI  # noqa: E402


def _guia_final(ctx):
    return {"ruta": [{"momento": a.split(":", 1)[0], "aporte": "Su evidencia aporta una parte verificable del producto."}
                     for a in ctx.actividades],
            "criterios": [{"indicador": f.indicador, "como_prepararse": "Revisar cada momento con su rúbrica."}
                          for f in ctx.rubrica],
            "recomendaciones": ["Planificar", "Validar", "Documentar"]}


def test_guia_producto_final(conn, silabo):
    ctx = contexto_asignatura(silabo)
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('p@uti.edu.ec',%s,%s,'ingenierias',%s) returning id",
                       (ctx.codigo_pf, ctx.version_silabo, Jsonb(silabo.model_dump(mode="json")))).fetchone()["id"]
    encolar(conn, asignatura_id=aid, agente="ingenierias", ambito=Ambito("asignatura", "asignatura"),
            herramienta="guia_producto_final", parametros={})
    t = tomar_siguiente(conn, "w1", 360)
    e = Encargo(trabajo_id=t.id, asignatura_id=aid, codigo_pf=ctx.codigo_pf, version_silabo=ctx.version_silabo,
                carrera=ctx.carrera, nivel=ctx.nivel, ambito=t.ambito, herramienta="guia_producto_final",
                perfil_dificultad="fundamentacion")
    cliente = ClienteSimulado({"worker": lambda m: json.dumps(_guia_final(ctx)), "revisor": _revisor()})
    cierre = Coordinador(PERFIL, {"guia_producto_final": GUIA_PRODUCTO_FINAL}, cliente).ejecutar(
        conn, t, e, ctx, lambda: True)
    r = conn.execute("select * from recurso").fetchone()
    assert cierre.estado == "listo", json.dumps(r["evidencia"]["verificaciones"])
    assert [p["momento"] for p in r["contenido"]["guia_final"]["ruta"]] == ["M2", "M3"]


def test_guia_final_verificacion(silabo):
    ctx = contexto_asignatura(silabo)
    bueno = _guia_final(ctx)
    assert verificar_guia_producto_final(bueno, ctx) == []
    assert "un paso" in " ".join(verificar_guia_producto_final({**bueno, "ruta": bueno["ruta"][:1]}, ctx))
    copia = " ".join(ctx.entregables_momento[0].split()[:13])
    assert "copia" in " ".join(verificar_guia_producto_final({**bueno, "recomendaciones": ["a", "b", copia]}, ctx))


def test_sin_rubrica_final_no_genera(silabo):
    sin_final = SilaboUTI.model_validate({**silabo.model_dump(), "rubrica_producto_final": []})
    tarea = TareaLote(trabajo_id=uuid4(), asignatura_id=uuid4(), lote=1, ronda=0,
                      contexto=contexto_asignatura(sin_final),
                      estilo=EstiloFacultad(tipos_de_caso=[], software_habitual=[]), plan=[], ya_generado=[])
    with pytest.raises(ValueError):
        GUIA_PRODUCTO_FINAL.generar(tarea, ClienteSimulado({"worker": ["{}"]}))


# --- Revisión final P3b -----------------------------------------------------------

def _con_evidencia(ctx, evidencia, otros=()):
    return ctx.model_copy(update={"entregables_momento": [evidencia, *otros]})


def test_copia_de_evidencia_corta_o_con_puntuacion(silabo):
    ctx = _con_evidencia(contexto_momento(silabo, "M3"), "Informe técnico del análisis exploratorio de datos")
    guia = _respuestas(ctx)["guia_evidencia"]
    corta = {**guia, "autochequeo": ["a", "b", "Informe técnico del análisis exploratorio de datos"]}
    assert "copia" in " ".join(verificar_guia_evidencia(corta, ctx))
    larga = contexto_momento(silabo, "M3")
    palabras = larga.entregables_momento[0].split()[:14]
    con_coma = " ".join(palabras[:6]) + ", " + " ".join(palabras[6:])
    assert "copia" in " ".join(verificar_guia_evidencia({**guia, "autochequeo": ["a", "b", con_coma]}, larga))


def test_copia_de_otro_entregable_del_momento(silabo):
    ctx = _con_evidencia(contexto_momento(silabo, "M3"), "Evidencia principal del momento tres",
                         ["Matriz de comparación de soluciones tecnológicas del caso asignado"])
    guia = _respuestas(ctx)["guia_evidencia"]
    copia = {**guia, "errores_comunes": ["a", "b", "Matriz de comparación de soluciones tecnológicas del caso asignado"]}
    assert "copia" in " ".join(verificar_guia_evidencia(copia, ctx))


def test_escenario_de_respaldo_no_choca_con_los_entregables(silabo):
    ctx = _con_evidencia(contexto_momento(silabo, "M3"),
                         "Informe de la organización ficticia de otro sector con sus entregables")
    tarea = TareaLote(trabajo_id=uuid4(), asignatura_id=uuid4(), lote=1, ronda=0, contexto=ctx,
                      estilo=EstiloFacultad(tipos_de_caso=[], software_habitual=[], escenarios=[]),
                      plan=[], ya_generado=[])
    escenario = escenario_para(tarea)
    caso = {"escenario": escenario, "ra": ctx.ra[0].id, "preguntas": _respuestas(ctx)["estudio_caso"]["preguntas"],
            "caso": f"Caso ficticio sobre {escenario}. " + LARGO}
    assert verificar_estudio_caso(caso, ctx) == []
