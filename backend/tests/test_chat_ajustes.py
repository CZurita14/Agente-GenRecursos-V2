"""Regeneración selectiva con clientes locales simulados, sin BD ni GPU."""
import json
from copy import deepcopy
from uuid import uuid4

import pytest

from app.agentes.facultades import PerfilFacultad
from app.agentes.mensajes import EntregaLote, EstiloFacultad, ResultadoItem
from app.chat import ajustes
from app.llm.cliente import ClienteSimulado, ContextoExcedido
from app.recursos.validacion import EdicionInvalida
from app.silabo.contexto import contexto_clase


@pytest.fixture
def entorno(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    perfil = PerfilFacultad(id="general", facultad=None,
                           estilo=EstiloFacultad(tipos_de_caso=["empresas"], software_habitual=[]),
                           herramientas_recomendadas={})
    return dict(contexto=ctx, perfil=perfil, trabajo_id=uuid4(), asignatura_id=uuid4())


def _item(ctx, numero):
    preguntas = ["¿Qué procedimiento corresponde aplicar a estos datos de ventas?",
                 "¿Cómo interpretar la asociación observada entre ambos indicadores?",
                 "¿Por qué la conclusión del analista requiere comprobar un supuesto?"]
    return {"item_id": f"i{numero}", "nivel": "resolutivo", "ra": ctx.ra[0].id,
            "contenido": ctx.contenidos[0], "foco": f"objetivo {numero}",
            "contexto": "Una empresa local analiza sus datos de producción para elegir un método adecuado "
            "a las condiciones de trabajo observadas durante el mes.",
            "pregunta": preguntas[numero - 1], "opciones": [
                {"texto": f"opción {k}", "justificacion": "Justificación técnica",
                 "error_que_representa": "ninguno" if k == 0 else f"error {k}"} for k in range(4)],
            "correcta": 0, "razonamiento": ["Examinar los datos", "Elegir el procedimiento"]}


def _quiz(entorno, herramienta="cuestionario"):
    return {"herramienta": herramienta, "asignatura_id": entorno["asignatura_id"],
            "ambito_id": entorno["contexto"].clase_id, "version_silabo": entorno["contexto"].version_silabo,
            "contenido": [_item(entorno["contexto"], n) for n in range(1, 4)],
            "estado": "listo", "validado_por": "docente", "revision": 3}


def _ficha():
    return {"herramienta": "ficha_clase", "contenido": {
        "conceptual": {"ideas_clave": ["Primera idea", "Segunda idea", "Tercera idea"],
                       "relacion_ra": "Se relaciona con el resultado de aprendizaje.",
                       "errores_frecuentes": ["Interpretar sin comprobar"]},
        "aplicacion": {"ejemplo": {"enunciado": "Una empresa analiza datos ficticios.",
                                  "pasos": ["Revisar datos", "Interpretar"], "resultado": "Resultado ilustrativo"},
                       "autocomprobacion": ["¿Qué se observa?", "¿Qué se requiere?", "¿Cómo se interpreta?"]}}}


def _accion(*, items=None, rutas=None):
    return {"items": items or [], "rutas": rutas or [], "instrucciones": "Aumenta la dificultad"}


def _worker(monkeypatch, recurso, *, modificar=None):
    tareas = []

    class Worker:
        def generar(self, tarea, cliente):
            tareas.append(tarea)
            anterior = next(i for i in recurso["contenido"] if i["item_id"] == tarea.plan[0].item_id)
            nuevo = deepcopy(anterior)
            nuevo["pregunta"] = "¿Cuál es la decisión más adecuada al contrastar estas condiciones?"
            if modificar:
                modificar(nuevo)
            return EntregaLote(trabajo_id=tarea.trabajo_id, asignatura_id=tarea.asignatura_id,
                               lote=tarea.lote, ronda=tarea.ronda, contenido=[nuevo], tokens=(1, 1))

    monkeypatch.setitem(ajustes.WORKERS, recurso["herramienta"], Worker())
    return tareas


def _revisor(monkeypatch, estado="ok"):
    recibidos = []

    def revisar(items, *args, **kwargs):
        recibidos.extend(items)
        return [ResultadoItem(item_id=i.item_id, fallos_verificacion=[], revisor=estado,
                              motivo="<think>PRIVADO</think><script>dato</script>") for i in items]

    monkeypatch.setattr(ajustes, "revisar_items", revisar)
    return recibidos


@pytest.mark.parametrize("herramienta", ["cuestionario", "simulacro"])
def test_quiz_seleccion_invariantes_y_alcance(entorno, monkeypatch, herramienta):
    recurso = _quiz(entorno, herramienta)
    antes = deepcopy(recurso)
    tareas = _worker(monkeypatch, recurso)
    revisados = _revisor(monkeypatch)
    contenido, fallos, revision = ajustes.regenerar(ClienteSimulado({}), recurso=recurso,
                                                 accion=_accion(items=["i2"]), **entorno)
    assert recurso == antes
    assert contenido[0] == antes["contenido"][0] and contenido[2] == antes["contenido"][2]
    assert contenido[1]["pregunta"] != antes["contenido"][1]["pregunta"]
    for k in ("item_id", "ra", "contenido", "nivel", "foco"):
        assert contenido[1][k] == antes["contenido"][1][k]
    assert len(tareas) == 1 and tareas[0].plan[0].nivel == "resolutivo"
    assert tareas[0].estilo == entorno["perfil"].estilo
    assert "H7" in tareas[0].instrucciones
    assert antes["contenido"][1]["pregunta"] not in tareas[0].instrucciones
    assert [i.item_id for i in revisados] == ["i2"]
    assert set(fallos) == {"i1", "i2", "i3"}
    assert revision["alcance"] == {"tipo": "items", "items": ["i2"], "rutas": []}
    assert set(revision) == {"alcance", "veredictos"}
    assert set(revision["veredictos"][0]) == {"item_id", "revisor", "motivo", "fallos_verificacion"}
    assert "PRIVADO" not in json.dumps(revision)


@pytest.mark.parametrize("campo,valor", [("item_id", "ajeno"), ("ra", "otro"),
                                        ("contenido", "otro"), ("nivel", "critico"), ("foco", "otro")])
def test_quiz_rechaza_cambio_de_identidad_y_h7(entorno, monkeypatch, campo, valor):
    recurso = _quiz(entorno)
    _worker(monkeypatch, recurso, modificar=lambda i: i.update({campo: valor}))
    with pytest.raises(EdicionInvalida):
        ajustes.regenerar(ClienteSimulado({}), recurso=recurso, accion=_accion(items=["i1"]), **entorno)


@pytest.mark.parametrize("accion", [
    _accion(), _accion(items=["ajeno"]), _accion(items=["i1", "i1"]),
    _accion(items=["i1"], rutas=[["x"]]), _accion(rutas=[[True]]),
    _accion(rutas=[[{}]]), _accion(rutas=[["opciones"]]),
    {**_accion(items=["i1"]), "instrucciones": "x" * 2001},
    {**_accion(items=["i1"]), "items": "i1"},
    {**_accion(items=["i1"]), "accion": "generar"},
])
def test_seleccion_invalida_no_invoca_cliente(entorno, accion):
    cliente = ClienteSimulado({})
    with pytest.raises(ValueError):
        ajustes.regenerar(cliente, recurso=_quiz(entorno), accion=accion, **entorno)
    assert cliente.llamadas == []


def test_rutas_hojas_listas_y_tablas():
    rutas = ajustes.rutas_editables(_ficha())
    assert ("conceptual", "ideas_clave", 0) in rutas
    assert ("conceptual", "ideas_clave") not in rutas
    assert ("aplicacion", "ejemplo", "enunciado") in rutas
    guia = {"herramienta": "guia_evidencia", "contenido": {"guia": {
        "que_se_pide": "Descripción", "como_se_valora": [{"indicador": "Fijo", "que_observar": "Editable"}],
        "errores_comunes": ["Error"], "autochequeo": ["Pregunta"]}}}
    rutas = ajustes.rutas_editables(guia)
    assert ("guia", "como_se_valora", 0, "que_observar") in rutas
    assert ("guia", "como_se_valora", 0, "indicador") not in rutas


@pytest.mark.parametrize("ruta", [["conceptual", "ideas_clave"], ["conceptual", "ideas_clave", -1],
                                 ["conceptual", "ideas_clave", True], ["conceptual", "nueva"],
                                 ["aplicacion", "ejemplo"], ["__proto__"]])
def test_ficha_rechaza_rutas_no_editables(entorno, ruta):
    cliente = ClienteSimulado({})
    with pytest.raises(EdicionInvalida):
        ajustes.regenerar(cliente, recurso=_ficha(), accion=_accion(rutas=[ruta]), **entorno)
    assert not cliente.llamadas


def test_ficha_parche_indexado_y_revision_completa(entorno, monkeypatch):
    recurso = _ficha()
    antes = deepcopy(recurso)
    rutas = [["conceptual", "ideas_clave", 1], ["aplicacion", "ejemplo", "enunciado"]]
    cliente = ClienteSimulado({"worker": [json.dumps({"textos": [
        {"indice": 1, "texto": "Una empresa de Ambato analiza datos ficticios."},
        {"indice": 0, "texto": "Segunda idea ampliada"}]})]})
    revisados = []

    def revisar(ficha, *args, **kwargs):
        revisados.append(deepcopy(ficha))
        return ResultadoItem(item_id=kwargs["item_id"], fallos_verificacion=[], revisor="sin_veredicto",
                             motivo="<think>razonamiento privado</think>")

    monkeypatch.setattr(ajustes, "revisar_ficha", revisar)
    contenido, fallos, revision = ajustes.regenerar(cliente, recurso=recurso,
                                                 accion=_accion(rutas=rutas), **entorno)
    esperado = deepcopy(antes["contenido"])
    esperado["conceptual"]["ideas_clave"][1] = "Segunda idea ampliada"
    esperado["aplicacion"]["ejemplo"]["enunciado"] = "Una empresa de Ambato analiza datos ficticios."
    assert contenido == esperado and recurso == antes
    assert revisados == [esperado] and set(fallos) == {"ficha"}
    assert revision["alcance"] == {"tipo": "recurso_completo", "items": [], "rutas": rutas}
    assert revision["veredictos"][0]["revisor"] == "sin_veredicto"
    assert revision["veredictos"][0]["motivo"]
    assert "privado" not in json.dumps(revision)
    llamada = cliente.llamadas[0]
    assert llamada["pensar"] is False and llamada["esquema"]["additionalProperties"] is False
    assert llamada["trabajo_id"] == entorno["trabajo_id"]
    assert "<indicaciones_docente>" in llamada["mensajes"][-1]["content"]


@pytest.mark.parametrize("textos", [
    [{"indice": 1, "texto": "Texto"}], [{"indice": -1, "texto": "Texto"}],
    [{"indice": True, "texto": "Texto"}], [{"indice": 0, "texto": "Texto", "ruta": ["ra"]}],
    [{"indice": 0, "texto": "Uno"}, {"indice": 0, "texto": "Dos"}], [],
])
def test_ficha_respuesta_estricta_sin_escrituras_arbitrarias(entorno, textos):
    recurso = _ficha()
    antes = deepcopy(recurso)
    respuesta = json.dumps({"textos": textos})
    cliente = ClienteSimulado({"worker": [respuesta] * 3})
    with pytest.raises(EdicionInvalida):
        ajustes.regenerar(cliente, recurso=recurso,
                         accion=_accion(rutas=[["conceptual", "relacion_ra"]]), **entorno)
    assert recurso == antes


@pytest.mark.parametrize("estado", ["devuelto", "sin_veredicto"])
def test_candidato_requiere_revision_se_conserva_sin_validar(entorno, monkeypatch, estado):
    recurso = _quiz(entorno)
    _worker(monkeypatch, recurso)
    _revisor(monkeypatch, estado)
    contenido, _, revision = ajustes.regenerar(ClienteSimulado({}), recurso=recurso,
                                              accion=_accion(items=["i1"]), **entorno)
    assert contenido[0]["pregunta"] != recurso["contenido"][0]["pregunta"]
    assert revision["veredictos"][0]["revisor"] == estado
    assert revision["veredictos"][0]["motivo"]
    assert "validado" not in json.dumps(revision)
    assert "<think>" not in json.dumps(revision)


def test_verificador_completo_detecta_duplicado_no_seleccionado(entorno, monkeypatch):
    recurso = _quiz(entorno)
    _worker(monkeypatch, recurso, modificar=lambda i: i.update(pregunta=recurso["contenido"][2]["pregunta"]))
    _revisor(monkeypatch)
    _, fallos, _ = ajustes.regenerar(ClienteSimulado({}), recurso=recurso,
                                    accion=_accion(items=["i1"]), **entorno)
    assert any("duplicado" in f for f in fallos["i1"])
    assert any("duplicado" in f for f in fallos["i3"])


@pytest.mark.parametrize("campo,valor", [("asignatura_id", uuid4()), ("ambito_id", "M3"),
                                       ("version_silabo", "otra"), ("herramienta", "hoja_ruta")])
def test_revalida_contexto_y_herramienta(entorno, campo, valor):
    recurso = _quiz(entorno)
    recurso[campo] = valor
    cliente = ClienteSimulado({})
    with pytest.raises(EdicionInvalida):
        ajustes.regenerar(cliente, recurso=recurso, accion=_accion(items=["i1"]), **entorno)
    assert not cliente.llamadas


def test_politica_prohibe_ajuste(entorno):
    entorno["contexto"] = entorno["contexto"].model_copy(update={"politica_ia": "Sin IA"})
    with pytest.raises(EdicionInvalida):
        ajustes.regenerar(ClienteSimulado({}), recurso=_quiz(entorno),
                         accion=_accion(items=["i1"]), **entorno)


def test_presupuesto_mide_esquema_y_limita_revisor():
    class Cliente:
        def contar_tokens(self, mensajes):
            return 2000 + (1200 if len(mensajes) > 2 else 0)

        def completar(self, mensajes, **kw):
            assert 3200 + kw["max_tokens"] + 300 <= 8192
            assert kw["trabajo_id"] == trabajo
            return "respuesta"

    trabajo = uuid4()
    cliente = ajustes._Presupuestado(Cliente())
    assert cliente.completar([{}, {}], esquema={"type": "object"}, max_tokens=7000,
                            trabajo_id=trabajo) == "respuesta"


def test_contexto_excesivo_no_llama_modelo(entorno):
    class Cliente:
        def contar_tokens(self, mensajes):
            return 8192

        def completar(self, *args, **kwargs):
            pytest.fail("No debe invocar el modelo")

    with pytest.raises(ContextoExcedido):
        ajustes.regenerar(Cliente(), recurso=_ficha(),
                         accion=_accion(rutas=[["conceptual", "relacion_ra"]]), **entorno)


def test_revisor_real_es_ciego_y_presupuestado(entorno, monkeypatch):
    recurso = _quiz(entorno)
    _worker(monkeypatch, recurso)
    veredicto = {"veredictos": [{"opcion": n, "valida": n == 0, "motivo": "privado"} for n in range(4)],
                 "resuelve_entregable": False, "motivo": ""}
    cliente = ClienteSimulado({"revisor": [json.dumps(veredicto)]})
    _, _, revision = ajustes.regenerar(cliente, recurso=recurso, accion=_accion(items=["i1"]), **entorno)
    llamada = cliente.llamadas[0]
    prompt = "\n".join(m["content"] for m in llamada["mensajes"])
    assert "Justificación técnica" not in prompt
    assert "Examinar los datos" not in prompt
    assert "error_que_representa" not in prompt
    assert revision["veredictos"][0]["revisor"] == "ok"
    assert cliente.contar_tokens(llamada["mensajes"]) + llamada["max_tokens"] + 300 <= 8192


def test_worker_existente_usa_cliente_inyectado_y_estilo_de_carrera(entorno, monkeypatch):
    recurso = _quiz(entorno)
    _revisor(monkeypatch)
    salida = deepcopy(recurso["contenido"][1])
    del salida["item_id"]
    salida["pregunta"] = "¿Cuál de los métodos permite contrastar las condiciones del nuevo caso?"
    cliente = ClienteSimulado({"worker": [json.dumps({"items": [salida]})]})
    contenido, _, revision = ajustes.regenerar(cliente, recurso=recurso,
                                              accion=_accion(items=["i2"]), **entorno)
    assert contenido[1]["pregunta"] == salida["pregunta"]
    assert revision["veredictos"][0]["item_id"] == "i2"
    llamada = cliente.llamadas[0]
    assert llamada["pensar"] is False
    assert llamada["trabajo_id"] == entorno["trabajo_id"]
    medidos = [*llamada["mensajes"], {"role": "user", "content": json.dumps(llamada["esquema"], ensure_ascii=False)}]
    assert cliente.contar_tokens(medidos) + llamada["max_tokens"] + 300 <= 8192


def test_ficha_revision_real_detecta_entregable_y_oculta_motivo_libre(entorno):
    cliente = ClienteSimulado({
        "worker": [json.dumps({"textos": [{"indice": 0, "texto": "Texto de prueba."}]})],
        "revisor": [json.dumps({"resuelve_entregable": True, "entregable": "PRIVADO",
                                "motivo": "<script>PRIVADO</script>"})],
    })
    _, _, revision = ajustes.regenerar(cliente, recurso=_ficha(),
                                      accion=_accion(rutas=[["conceptual", "relacion_ra"]]), **entorno)
    assert revision["veredictos"][0]["revisor"] == "devuelto"
    assert revision["veredictos"][0]["motivo"]
    assert "PRIVADO" not in json.dumps(revision)


def test_multiples_items_revisa_solo_seleccion_y_fallo_determinista(entorno, monkeypatch):
    recurso = _quiz(entorno)
    tareas = _worker(monkeypatch, recurso)
    revisados = _revisor(monkeypatch)
    _, fallos, revision = ajustes.regenerar(ClienteSimulado({}), recurso=recurso,
                                          accion=_accion(items=["i1", "i3"]), **entorno)
    assert [t.plan[0].item_id for t in tareas] == ["i1", "i3"]
    assert [i.item_id for i in revisados] == ["i1", "i3"]
    assert revision["veredictos"][1]["fallos_verificacion"] == fallos["i3"]
    assert fallos["i3"]  # El worker simulado produjo la misma pregunta para ambos.


def _con_casos(entorno):
    perfil = entorno["perfil"].model_copy(update={"estilo": entorno["perfil"].estilo.model_copy(
        update={"escenarios": ["una biblioteca municipal", "un huerto escolar comunitario"]})})
    return {**entorno, "perfil": perfil}


def test_el_ajuste_no_tiene_entrada_para_el_razonador():
    import inspect

    from app.chat.ejecutor import procesar_chat

    for funcion in (ajustes.regenerar, procesar_chat):
        assert "razonador" not in inspect.signature(funcion).parameters


def test_el_ajuste_conserva_el_estilo_de_la_carrera(entorno, monkeypatch):
    entorno = _con_casos(entorno)
    recurso = _quiz(entorno)
    tareas = _worker(monkeypatch, recurso)
    _revisor(monkeypatch)
    ajustes.regenerar(ClienteSimulado({}), recurso=recurso, accion=_accion(items=["i2"]), **entorno)
    assert tareas[0].estilo == entorno["perfil"].estilo
