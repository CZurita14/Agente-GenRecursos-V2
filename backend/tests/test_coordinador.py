"""Integración del coordinador con PostgreSQL y revisión simulada."""
import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from app.agentes.coordinador import Coordinador, LeasePerdido
from app.agentes.facultades import cargar_catalogo, cargar_perfiles, estilo_para
from app.agentes.mensajes import Encargo, EntregaLote, PlanRazonado, leer
from app.agentes.orquestador import SolicitudGeneracion, crear_asignatura, crear_trabajos, procesar_uno
from app.agentes.planificador import _casos_libres, planificar
from app.cola.trabajos import Ambito, encolar, tomar_siguiente
from app.llm.cliente import ClienteSimulado
from app.silabo.contexto import contexto_clase

RAIZ = Path(__file__).resolve().parents[2]


def preparar(conn, silabo, herramienta="cuestionario", cantidad=12):
    ctx = contexto_clase(silabo, "M2-S1")
    aid = conn.execute(
        "insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
        "values ('prueba@uti.edu.ec',%s,%s,'ingenierias',%s) returning id",
        (ctx.codigo_pf, ctx.version_silabo, Jsonb(silabo.model_dump(mode="json"))),
    ).fetchone()["id"]
    encolar(conn, asignatura_id=aid, agente="ingenierias", ambito=Ambito("clase", ctx.clase_id),
            herramienta=herramienta, parametros={"cantidad": cantidad})
    t = tomar_siguiente(conn, "w1", 360)
    encargo = Encargo(trabajo_id=t.id, asignatura_id=aid, codigo_pf=ctx.codigo_pf,
                      version_silabo=ctx.version_silabo, carrera=ctx.carrera, nivel=ctx.nivel,
                      ambito=t.ambito, herramienta=herramienta, perfil_dificultad="fundamentacion")
    return t, encargo, ctx


def pregunta(item_id):
    # Preguntas suficientemente diferentes para que el test no dispare duplicados.
    digest = hashlib.sha256(item_id.encode()).hexdigest()
    return "¿Cómo interpreta " + " ".join(digest[i:i+5] for i in range(0, 60, 5)) + "?"


class WorkerPrueba:
    def __init__(self, herramienta="cuestionario", prohibida=False):
        self.herramienta = herramienta
        self.prohibida = prohibida
        self.tareas = []

    def generar(self, tarea, cliente):
        self.tareas.append(tarea)
        if self.herramienta == "ficha_clase":
            contenido = [{"ideas_clave": ["a", "b", "c"], "relacion_ra": "RA1",
                          "errores_frecuentes": ["error"]}] if tarea.lote == 1 else [
                {"ejemplo": {"enunciado": "x", "pasos": ["paso"], "resultado": "y"},
                 "autocomprobacion": ["a", "b", "c"]}]
        else:
            contenido = [{"item_id": p.item_id, "nivel": p.nivel, "foco": p.foco,
                          "ra": tarea.contexto.ra[0].id, "contenido": tarea.contexto.contenidos[0],
                          "contexto": "Una empresa usa datos ficticios para analizar eventos de red "
                                      "durante tres meses y fundamentar una decisión técnica responsable.",
                          "pregunta": pregunta(p.item_id), "correcta": 0,
                          "opciones": [{"texto": ("Todas las anteriores" if self.prohibida and
                                       len(self.tareas) == 1 and k == 3 else
                                       ("VALIDA" if k == 0 else f"Error {k}")),
                                       "justificacion": "j", "error_que_representa": "e"}
                                      for k in range(4)], "razonamiento": ["paso 1", "paso 2"]}
                         for p in tarea.plan]
        return EntregaLote(trabajo_id=tarea.trabajo_id, asignatura_id=tarea.asignatura_id,
                           lote=tarea.lote, ronda=tarea.ronda, contenido=contenido, tokens=(10, 20))


def cliente_revisor(ambiguo=False):
    def responder(mensajes):
        texto = mensajes[-1]["content"]
        opciones = re.findall(r"^(\d)\) (.+)$", texto, re.M)
        return json.dumps({"veredictos": [{"opcion": int(k), "valida": "VALIDA" in v or ambiguo,
                                           "motivo": "revisión"} for k, v in opciones],
                           "resuelve_entregable": False, "motivo": "", "entregable": ""})
    return ClienteSimulado({"revisor": responder})


def coordinador(worker, cliente=None):
    perfil = cargar_perfiles(RAIZ / "agentes")["ingenierias"]
    return Coordinador(perfil, {worker.herramienta: worker}, cliente or cliente_revisor())


def test_camino_feliz(conn, silabo):
    t, e, ctx = preparar(conn, silabo)
    cierre = coordinador(WorkerPrueba()).ejecutar(conn, t, e, ctx, lambda: True)
    r = conn.execute("select * from recurso").fetchone()
    assert cierre.estado == r["estado"] == "listo"
    assert len(r["contenido"]) == 12
    assert r["evidencia"]["tabla_real"] == dict(receptivo=2, resolutivo=5, reflexivo=4, critico=1)
    assert r["evidencia"]["borrador"] is True
    tipos = [type(m).__name__ for m in leer(conn, t.id)]
    assert tipos[:3] == ["Encargo", "TareaLote", "EntregaLote"]
    assert tipos[-2:] == ["Veredicto", "Cierre"]


def test_item_ambiguo_requiere_revision(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    worker = WorkerPrueba()
    cierre = coordinador(worker, cliente_revisor(ambiguo=True)).ejecutar(conn, t, e, ctx, lambda: True)
    assert cierre.estado == "requiere_revision"
    assert sum(any(p.item_id == "i3" for p in x.plan) for x in worker.tareas) == 3
    assert "opciones" in conn.execute("select evidencia from recurso").fetchone()["evidencia"]["veredictos"]["i3"]


def test_reintento_de_lote_por_verificacion(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    worker = WorkerPrueba(prohibida=True)
    cierre = coordinador(worker).ejecutar(conn, t, e, ctx, lambda: True)
    assert cierre.estado == "listo"
    assert "prohibida" in worker.tareas[1].devoluciones[0].motivo


def test_retoma_tras_caida(conn, silabo):
    t, e, ctx = preparar(conn, silabo)
    worker = WorkerPrueba()
    def latido():
        return conn.execute("select lotes_hechos from trabajo where id=%s", (t.id,)).fetchone()["lotes_hechos"] < 2
    with pytest.raises(LeasePerdido):
        coordinador(worker).ejecutar(conn, t, e, ctx, latido)
    assert conn.execute("select count(*) as n from recurso").fetchone()["n"] == 0
    worker2 = WorkerPrueba()
    coordinador(worker2).ejecutar(conn, t, e, ctx, lambda: True)
    assert [x.lote for x in worker2.tareas] == [3]
    r = conn.execute("select contenido from recurso").fetchone()["contenido"]
    assert len({x["item_id"] for x in r}) == 12


def test_ficha_clase(conn, silabo):
    t, e, ctx = preparar(conn, silabo, herramienta="ficha_clase")
    cierre = coordinador(WorkerPrueba("ficha_clase")).ejecutar(conn, t, e, ctx, lambda: True)
    r = conn.execute("select * from recurso").fetchone()
    assert cierre.estado == "listo"
    assert set(r["contenido"]) == {"conceptual", "aplicacion"}
    assert r["evidencia"]["veredictos"] == {"ficha": "ok"}


def test_worker_zombi_no_publica(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    def latido():
        conn.execute("update trabajo set worker_id='otro' where id=%s", (t.id,))
        return True  # Incluso un callback defectuoso no vence el cerco de la BD.
    with pytest.raises(LeasePerdido):
        coordinador(WorkerPrueba()).ejecutar(conn, t, e, ctx, latido)
    assert conn.execute("select count(*) as n from recurso").fetchone()["n"] == 0


def test_fallos_persistentes_no_se_publican_listos(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    class SiempreMal(WorkerPrueba):
        def generar(self, tarea, cliente):
            self.tareas.clear()
            self.prohibida = True
            return super().generar(tarea, cliente)
    assert coordinador(SiempreMal()).ejecutar(conn, t, e, ctx, lambda: True).estado == "requiere_revision"


def test_contexto_de_otra_asignatura_rechazado(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    ajeno = ctx.model_copy(update={"codigo_pf": "OTRA-ASIGNATURA"})
    with pytest.raises(ValueError):
        coordinador(WorkerPrueba()).ejecutar(conn, t, e.model_copy(update={"codigo_pf": ajeno.codigo_pf}), ajeno, lambda: True)
    assert leer(conn, t.id) == []


def test_retomar_mismo_worker_invalida_ejecucion_antigua(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    conn.execute("update trabajo set lease_hasta=now()-interval '1 second' where id=%s", (t.id,))
    assert tomar_siguiente(conn, "w1", 360) is not None
    with pytest.raises(LeasePerdido):
        coordinador(WorkerPrueba()).ejecutar(conn, t, e, ctx, lambda: True)


def test_retoma_ronda_de_revision_incompleta(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=2)
    worker = WorkerPrueba()
    class Caida(Exception):
        pass
    class CaeSegundoItem(WorkerPrueba):
        def generar(self, tarea, cliente):
            if tarea.ronda == 2 and len(tarea.plan) == 1 and tarea.plan[0].item_id == "i2":
                raise Caida()
            return super().generar(tarea, cliente)
    with pytest.raises(Caida):
        coordinador(CaeSegundoItem(), cliente_revisor(True)).ejecutar(conn, t, e, ctx, lambda: True)
    coordinador(worker, cliente_revisor(True)).ejecutar(conn, t, e, ctx, lambda: True)
    assert [(x.ronda, x.plan[0].item_id) for x in worker.tareas] == [(2, "i2")]


def revisor_contado(ambiguos=(), todos=False):
    """Revisor simulado que cuenta llamadas; marca ambiguos los ítems indicados."""
    llamadas = []
    def responder(mensajes):
        texto = mensajes[-1]["content"]
        llamadas.append(texto)
        ambiguo = todos or any(pregunta(i) in texto for i in ambiguos)
        opciones = re.findall(r"^(\d)\) (.+)$", texto, re.M)
        return json.dumps({"veredictos": [{"opcion": int(k), "valida": "VALIDA" in v or ambiguo,
                                           "motivo": "revisión"} for k, v in opciones],
                           "resuelve_entregable": False, "motivo": "", "entregable": ""})
    return ClienteSimulado({"revisor": responder}), llamadas


def test_ronda_revisa_solo_los_devueltos(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    cliente, llamadas = revisor_contado(ambiguos=["i3"])
    cierre = coordinador(WorkerPrueba(), cliente).ejecutar(conn, t, e, ctx, lambda: True)
    assert cierre.estado == "requiere_revision"
    assert len(llamadas) == 4 + 1 + 1  # revisión inicial + i3 en cada una de las 2 rondas
    evidencia = conn.execute("select evidencia from recurso").fetchone()["evidencia"]
    assert set(evidencia["veredictos"]) == {"i1", "i2", "i3", "i4"}
    assert evidencia["veredictos"]["i1"] == "ok"


def test_correccion_que_falla_verificacion_se_reintenta(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    class CorrigeMal(WorkerPrueba):
        """La 1.ª corrección de la ronda 1 trae "Todas las anteriores"."""
        historial = []
        def generar(self, tarea, cliente):
            self.prohibida = tarea.ronda == 1 and not any(x.ronda == 1 for x in self.historial)
            self.historial.append(tarea)
            self.tareas = []  # WorkerPrueba solo siembra la frase cuando hay una tarea.
            return super().generar(tarea, cliente)
    worker = CorrigeMal()
    cliente, _ = revisor_contado(ambiguos=["i3"])
    coordinador(worker, cliente).ejecutar(conn, t, e, ctx, lambda: True)
    ronda1 = [x for x in worker.historial if x.ronda == 1 and x.plan[0].item_id == "i3"]
    assert len(ronda1) == 2
    assert any("prohibida" in d.motivo for d in ronda1[1].devoluciones)


def test_retoma_sin_repetir_revision_guardada(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=2)
    class Caida(Exception):
        pass
    class CaeSegundoItem(WorkerPrueba):
        def generar(self, tarea, cliente):
            if tarea.ronda == 2 and len(tarea.plan) == 1 and tarea.plan[0].item_id == "i2":
                raise Caida()
            return super().generar(tarea, cliente)
    with pytest.raises(Caida):
        coordinador(CaeSegundoItem(), revisor_contado(todos=True)[0]).ejecutar(conn, t, e, ctx, lambda: True)
    cliente, llamadas = revisor_contado(todos=True)
    coordinador(WorkerPrueba(), cliente).ejecutar(conn, t, e, ctx, lambda: True)
    assert len(llamadas) == 2  # solo la revisión de la ronda 2, no la ya guardada


def test_reintentos_de_lote_no_se_reinician(conn, silabo):
    from app.llm.cliente import JsonInvalido
    t, e, ctx = preparar(conn, silabo, cantidad=1)
    class Cae(Exception):
        pass
    class SiempreCae(WorkerPrueba):
        def generar(self, tarea, cliente):
            self.tareas.append(tarea)
            raise Cae()
    w = SiempreCae()
    for _ in range(3):
        with pytest.raises(Cae):
            coordinador(w).ejecutar(conn, t, e, ctx, lambda: True)
    with pytest.raises(JsonInvalido):
        coordinador(w).ejecutar(conn, t, e, ctx, lambda: True)
    assert len(w.tareas) == 3


def test_entrega_incompleta_se_reintenta(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    class Incompleta(WorkerPrueba):
        def generar(self, tarea, cliente):
            entrega = super().generar(tarea, cliente)
            return entrega.model_copy(update={"contenido": entrega.contenido[:3]}) if len(self.tareas) == 1 else entrega
    w = Incompleta()
    assert coordinador(w).ejecutar(conn, t, e, ctx, lambda: True).estado == "listo"
    assert len(w.tareas) == 2


def test_lease_perdido_durante_llamada_no_guarda_recurso(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=1)
    cliente = cliente_revisor()
    completar = cliente.completar
    def perder_lease(mensajes, **kw):
        respuesta = completar(mensajes, **kw)
        conn.execute("update trabajo set worker_id='otro' where id=%s", (t.id,))
        return respuesta
    cliente.completar = perder_lease
    with pytest.raises(LeasePerdido):
        coordinador(WorkerPrueba(), cliente).ejecutar(conn, t, e, ctx, lambda: True)
    assert conn.execute("select count(*) as n from recurso").fetchone()["n"] == 0


# --- Plan razonado -------------------------------------------------------------

class FalsoRazonador:
    """Agrupa los focos de dos en dos y descarta el primer caso."""
    def __init__(self, version="v-prueba"):
        self.version = version

    def temas(self, textos):
        return [g for g in (list(range(i, len(textos), 2)) for i in range(2)) if g]

    def casos_libres(self, casos, entregables):
        return list(casos)[1:]


class RazonadorVetado:
    """Otro modelo instalado al reanudar: si se le consulta, la prueba falla."""
    version = "v-otra"

    def temas(self, textos):
        raise AssertionError("el plan guardado no se recalcula")

    def casos_libres(self, casos, entregables):
        raise AssertionError("el plan guardado no se recalcula")


class RazonadorRoto:
    version = "v-rota"

    def temas(self, textos):
        raise RuntimeError("texto-privado-del-silabo")

    def casos_libres(self, casos, entregables):
        raise RuntimeError("texto-privado-del-silabo")


def coordinador_con(worker, razonador):
    perfil = cargar_perfiles(RAIZ / "agentes")["ingenierias"]
    return Coordinador(perfil, {worker.herramienta: worker}, cliente_revisor(), razonador=razonador)


def cae_tras_lotes(conn, t, lotes):
    return lambda: conn.execute("select lotes_hechos from trabajo where id=%s", (t.id,)).fetchone()["lotes_hechos"] < lotes


def estilo_base(ctx):
    return estilo_para(cargar_perfiles(RAIZ / "agentes")["ingenierias"], ctx.carrera)


def evidencia(conn):
    return conn.execute("select evidencia from recurso").fetchone()["evidencia"]


def test_evidencia_registra_la_version_y_el_plan_usa_los_temas(conn, silabo):
    t, e, ctx = preparar(conn, silabo)
    worker = WorkerPrueba()
    cierre = coordinador_con(worker, FalsoRazonador()).ejecutar(conn, t, e, ctx, lambda: True)
    assert cierre.estado == "listo"
    assert evidencia(conn)["razonador_version"] == "v-prueba"
    guardado = leer(conn, t.id, PlanRazonado)
    assert len(guardado) == 1 and guardado[0].version == "v-prueba"
    assert [x.plan for x in worker.tareas] == guardado[0].planes
    esperados = _casos_libres(estilo_base(ctx).escenarios, ctx.entregables_momento)[1:]
    assert guardado[0].escenarios == esperados == worker.tareas[0].estilo.escenarios
    assert [type(m).__name__ for m in leer(conn, t.id)][:3] == ["Encargo", "PlanRazonado", "TareaLote"]


def test_sin_razonador_no_se_guarda_plan_ni_version(conn, silabo):
    t, e, ctx = preparar(conn, silabo, cantidad=4)
    worker = WorkerPrueba()
    coordinador(worker).ejecutar(conn, t, e, ctx, lambda: True)
    assert leer(conn, t.id, PlanRazonado) == []
    assert evidencia(conn)["razonador_version"] is None
    assert [x.plan for x in worker.tareas] == planificar(ctx, 4, "fundamentacion", escenarios=estilo_base(ctx).escenarios)


def test_reanudar_conserva_el_plan_guardado_con_otro_modelo(conn, silabo):
    t, e, ctx = preparar(conn, silabo)
    with pytest.raises(LeasePerdido):
        coordinador_con(WorkerPrueba(), FalsoRazonador()).ejecutar(conn, t, e, ctx, cae_tras_lotes(conn, t, 2))
    guardado = leer(conn, t.id, PlanRazonado)[0]
    assert guardado.planes != planificar(ctx, 12, "fundamentacion", escenarios=estilo_base(ctx).escenarios)
    worker = WorkerPrueba()
    coordinador_con(worker, RazonadorVetado()).ejecutar(conn, t, e, ctx, lambda: True)
    assert [x.plan for x in worker.tareas] == guardado.planes[2:]
    assert worker.tareas[0].estilo.escenarios == guardado.escenarios
    assert len(leer(conn, t.id, PlanRazonado)) == 1
    assert evidencia(conn)["razonador_version"] == "v-prueba"


def test_reanudar_sin_razonador_usa_el_plan_guardado(conn, silabo):
    t, e, ctx = preparar(conn, silabo)
    with pytest.raises(LeasePerdido):
        coordinador_con(WorkerPrueba(), FalsoRazonador()).ejecutar(conn, t, e, ctx, cae_tras_lotes(conn, t, 2))
    guardado = leer(conn, t.id, PlanRazonado)[0]
    worker = WorkerPrueba()
    cierre = coordinador(worker).ejecutar(conn, t, e, ctx, lambda: True)
    assert cierre.estado == "listo"
    assert [x.plan for x in worker.tareas] == guardado.planes[2:]
    assert evidencia(conn)["razonador_version"] == "v-prueba"


def test_trabajo_empezado_sin_razonador_no_mezcla_planes(conn, silabo):
    # Los lotes ya entregados siguen el plan antiguo: un plan nuevo a medias rompería la verificación.
    t, e, ctx = preparar(conn, silabo)
    with pytest.raises(LeasePerdido):
        coordinador(WorkerPrueba()).ejecutar(conn, t, e, ctx, cae_tras_lotes(conn, t, 2))
    worker = WorkerPrueba()
    cierre = coordinador_con(worker, RazonadorVetado()).ejecutar(conn, t, e, ctx, lambda: True)
    assert cierre.estado == "listo"
    original = planificar(ctx, 12, "fundamentacion", escenarios=estilo_base(ctx).escenarios)
    assert [x.plan for x in worker.tareas] == original[2:]
    assert leer(conn, t.id, PlanRazonado) == []
    assert evidencia(conn)["razonador_version"] is None


def test_herramienta_sin_plan_conserva_los_casos_al_reanudar(conn, silabo):
    t, e, ctx = preparar(conn, silabo, herramienta="ficha_clase")
    primero = WorkerPrueba("ficha_clase")
    with pytest.raises(LeasePerdido):
        coordinador_con(primero, FalsoRazonador()).ejecutar(conn, t, e, ctx, cae_tras_lotes(conn, t, 1))
    guardado = leer(conn, t.id, PlanRazonado)[0]
    assert guardado.planes == [[], []]
    assert guardado.escenarios == primero.tareas[0].estilo.escenarios != estilo_base(ctx).escenarios
    worker = WorkerPrueba("ficha_clase")
    coordinador_con(worker, RazonadorVetado()).ejecutar(conn, t, e, ctx, lambda: True)
    assert [x.lote for x in worker.tareas] == [2]
    assert worker.tareas[0].estilo.escenarios == guardado.escenarios
    assert evidencia(conn)["razonador_version"] == "v-prueba"


def test_razonador_roto_termina_en_error_sin_filtrar_texto(conn, silabo):
    perfiles = cargar_perfiles(RAIZ / "agentes")
    aid = crear_asignatura(conn, dueno="prueba@uti.edu.ec", silabo=silabo,
                           catalogo=cargar_catalogo(RAIZ / "kb/catalogo.yaml"), perfiles=perfiles)
    tid = crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("clase", "M2-S1"), ["cuestionario"], 4))[0]
    assert procesar_uno(conn, cliente_revisor(), perfiles, "w", 360, razonador=RazonadorRoto())
    fila = conn.execute("select estado,error from trabajo where id=%s", (tid,)).fetchone()
    assert fila == dict(estado="error", error="RuntimeError: no se pudo completar el trabajo")
    assert conn.execute("select count(*) as n from recurso").fetchone()["n"] == 0
    assert leer(conn, tid) == []  # Sin plan alternativo silencioso: nada avanzó con el filtro de palabras.
