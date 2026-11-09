"""Workers de cuestionario y ficha de clase (Tarea 10)."""
import json
from uuid import uuid4

from app.agentes.mensajes import Devolucion, EstiloFacultad, TareaLote
from app.agentes.planificador import planificar
from app.agentes.workers.cuestionario import WorkerCuestionario
from app.agentes.workers.ficha_clase import WorkerFichaClase
from app.herramientas.esquemas import FichaAplicacion, FichaConceptual, ItemCuestionario
from app.llm.cliente import ClienteSimulado
from app.silabo.contexto import contexto_clase

ESTILO = EstiloFacultad(tipos_de_caso=["datasets"], software_habitual=["JASP"])


def _tarea(ctx, *, lote=1, devoluciones=(), ya=(), trabajo_id=None, asignatura_id=None):
    plan = planificar(ctx, 4, "fundamentacion")[0]
    trabajo_id = trabajo_id or uuid4()
    asignatura_id = asignatura_id or uuid4()
    return TareaLote(
        trabajo_id=trabajo_id, asignatura_id=asignatura_id, lote=lote, ronda=0,
        contexto=ctx, estilo=ESTILO, plan=plan, ya_generado=list(ya),
        devoluciones=[Devolucion(trabajo_id=trabajo_id, asignatura_id=asignatura_id, **d)
                      for d in devoluciones],
    )


def _lote_json(ctx, n=4):
    """Lote válido como lo devolvería el modelo: la clave siempre en la opción 0."""
    items = []
    for k in range(n):
        items.append({
            "nivel": "resolutivo", "ra": ctx.ra[0].id, "contenido": ctx.contenidos[0],
            "foco": f"foco {k}", "contexto": "Una empresa analiza datos de tráfico de red " * 2,
            "pregunta": f"¿Qué procedimiento corresponde aplicar en la situación {k}?",
            "opciones": [{"texto": f"correcta {k}", "justificacion": "j", "error_que_representa": "ninguno"}]
                        + [{"texto": f"distractor {k}-{d}", "justificacion": "j",
                            "error_que_representa": f"error {d}"} for d in range(1, 4)],
            "correcta": 0, "razonamiento": ["paso 1", "paso 2"],
        })
    return json.dumps({"items": items})


def test_cuestionario_lote(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    tarea = _tarea(ctx)
    cliente = ClienteSimulado({"worker": [_lote_json(ctx)]})
    entrega = WorkerCuestionario().generar(tarea, cliente)
    assert len(entrega.contenido) == 4
    assert [i["item_id"] for i in entrega.contenido] == [p.item_id for p in tarea.plan]
    assert (entrega.trabajo_id, entrega.asignatura_id, entrega.lote) == (tarea.trabajo_id, tarea.asignatura_id, 1)
    for item in entrega.contenido:
        ItemCuestionario.model_validate(item)
    llamada = cliente.llamadas[-1]
    assert llamada["rol"] == "worker"
    assert llamada["temperatura"] == 0.4 and llamada["pensar"] is False
    assert llamada["esquema"] is not None


def test_cantidad_incorrecta_no_se_oculta_con_zip(silabo):
    import pytest
    from app.llm.cliente import JsonInvalido
    ctx = contexto_clase(silabo, "M2-S1")
    datos = json.loads(_lote_json(ctx))
    datos["items"].append(datos["items"][0])
    cliente = ClienteSimulado({"worker": [json.dumps(datos)]})
    with pytest.raises(JsonInvalido):
        WorkerCuestionario().generar(_tarea(ctx), cliente)


def test_esquema_obliga_ra_y_contenido_de_la_clase(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    cliente = ClienteSimulado({"worker": [_lote_json(ctx)]})
    WorkerCuestionario().generar(_tarea(ctx), cliente)
    item = cliente.llamadas[-1]["esquema"]["properties"]["items"]["items"]["properties"]
    assert item["ra"]["enum"] == [r.id for r in ctx.ra]
    assert item["contenido"]["enum"] == ctx.contenidos


def test_baraja_opciones(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    posiciones = set()
    for _ in range(10):
        cliente = ClienteSimulado({"worker": [_lote_json(ctx)]})
        for item in WorkerCuestionario().generar(_tarea(ctx), cliente).contenido:
            posiciones.add(item["correcta"])
            k = item["pregunta"].split("situación ")[1].rstrip("?")
            assert item["opciones"][item["correcta"]]["texto"] == f"correcta {k}"
    assert len(posiciones) >= 3


def test_barajado_determinista(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    tarea = _tarea(ctx)
    a = WorkerCuestionario().generar(tarea, ClienteSimulado({"worker": [_lote_json(ctx)]}))
    b = WorkerCuestionario().generar(tarea, ClienteSimulado({"worker": [_lote_json(ctx)]}))
    assert a.contenido == b.contenido


def test_devolucion_llega_al_prompt(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    tarea = _tarea(ctx, devoluciones=[{"item_id": "i3", "motivo": "dos respuestas defendibles", "ronda": 1}])
    cliente = ClienteSimulado({"worker": [_lote_json(ctx)]})
    WorkerCuestionario().generar(tarea, cliente)
    assert "dos respuestas defendibles" in cliente.llamadas[-1]["mensajes"][-1]["content"]


def test_sin_estado(silabo):
    ctx1 = contexto_clase(silabo, "M2-S1")
    ctx2 = ctx1.model_copy(update={
        "codigo_pf": "B26-TIC-2-11111-2222", "asignatura": "Tecnologías de la Información",
        "clase_id": "M3-S1", "momento_titulo": "Ciberseguridad", "contenidos": ["Ciberseguridad en ingeniería"],
        "actividades": ["Análisis de un incidente de seguridad"], "competencia_perfil": "Evalúa soluciones TI",
        "problema": ctx1.problema.model_copy(update={"descripcion": "Incidentes en pymes",
                                                     "reto": "¿Cómo proteger?", "producto_final": "Plan"}),
        "rubrica": [], "politica_ia": "Sin IA", "entregables_momento": ["TAREA 3"],
    })
    worker = WorkerCuestionario()
    c1 = ClienteSimulado({"worker": [_lote_json(ctx1)]})
    worker.generar(_tarea(ctx1, ya=["MARCA-PRIMERA-ASIGNATURA"]), c1)
    c2 = ClienteSimulado({"worker": [_lote_json(ctx2)]})
    worker.generar(_tarea(ctx2), c2)
    prompt2 = "\n".join(m["content"] for m in c2.llamadas[-1]["mensajes"])
    for marca in [ctx1.codigo_pf, ctx1.contenidos[0], "MARCA-PRIMERA-ASIGNATURA", *ctx1.actividades]:
        assert marca not in prompt2
    assert vars(worker) == {}


def test_ficha_dos_secciones(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    conceptual = {"ideas_clave": ["a", "b", "c"], "relacion_ra": "r", "errores_frecuentes": ["e"]}
    aplicacion = {"ejemplo": {"enunciado": "x", "pasos": ["1", "2"], "resultado": "y"},
                  "autocomprobacion": ["p1", "p2", "p3"]}
    cliente = ClienteSimulado({"worker": [json.dumps(conceptual), json.dumps(aplicacion)]})
    worker = WorkerFichaClase()
    e1 = worker.generar(_tarea(ctx, lote=1), cliente)
    e2 = worker.generar(_tarea(ctx, lote=2), cliente)
    FichaConceptual.model_validate(e1.contenido[0])
    FichaAplicacion.model_validate(e2.contenido[0])
    assert cliente.llamadas[0]["esquema"] != cliente.llamadas[1]["esquema"]


def test_caso_por_item_llega_al_pedido(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    tarea = _tarea(ctx)
    plan = [p.model_copy(update={"caso": f"escenario {k}"}) for k, p in enumerate(tarea.plan)]
    tarea = tarea.model_copy(update={"plan": plan})
    cliente = ClienteSimulado({"worker": [_lote_json(ctx)]})
    WorkerCuestionario().generar(tarea, cliente)
    pedido = cliente.llamadas[-1]["mensajes"][-1]["content"]
    assert all(f"caso: escenario {k}" in pedido for k in range(4))
