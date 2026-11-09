"""Revisor a ciegas y de integridad (Tarea 12)."""
import json
from dataclasses import replace
from uuid import uuid4

import pytest

from app.agentes.revisor import revisar_ficha, revisar_items
from app.herramientas.esquemas import ItemCuestionario, Opcion
from app.llm.cliente import ClienteSimulado
from app.silabo.contexto import contexto_clase

T, A = uuid4(), uuid4()


@pytest.fixture
def ctx(silabo):
    return contexto_clase(silabo, "M2-S1").model_copy(update={"entregables_momento": ["PAE 1"]})


def _item(ctx, item_id="i1", correcta=2):
    return ItemCuestionario(
        item_id=item_id, nivel="reflexivo", ra=ctx.ra[0].id, contenido=ctx.contenidos[0], foco="f",
        contexto="Una empresa analiza el tráfico de su red durante un mes.",
        pregunta="¿Qué se puede concluir del comportamiento observado en el tráfico?",
        opciones=[Opcion(texto=f"Opción {k}", justificacion=f"JUSTIF-SECRETA-{k}",
                         error_que_representa=f"ERROR-SECRETO-{k}") for k in range(4)],
        correcta=correcta, razonamiento=["RAZON-SECRETA-1", "RAZON-SECRETA-2"],
    )


def _veredicto(validas, resuelve=False, entregable=""):
    return ("Thinking about it... " + json.dumps({
        "veredictos": [{"opcion": k, "valida": k in validas, "motivo": "explicación"} for k in range(4)],
        "resuelve_entregable": resuelve, "entregable": entregable,
        "motivo": "La herramienta reproduce la PAE." if resuelve else "",
    }))


def _revisar(ctx, cliente, items):
    return revisar_items(items, ctx, cliente, trabajo_id=T, asignatura_id=A)


def test_prompt_a_ciegas(ctx):
    cliente = ClienteSimulado({"revisor": [_veredicto([2])]})
    _revisar(ctx, cliente, [_item(ctx)])
    texto = "\n".join(m["content"] for m in cliente.llamadas[0]["mensajes"])
    assert '"correcta"' not in texto
    for secreto in ["JUSTIF-SECRETA", "ERROR-SECRETO", "RAZON-SECRETA"]:
        assert secreto not in texto
    assert "Opción 0" in texto and "Opción 3" in texto


def test_parametros_de_la_llamada(ctx):
    cliente = ClienteSimulado({"revisor": [_veredicto([2])]})
    _revisar(ctx, cliente, [_item(ctx)])
    ll = cliente.llamadas[0]
    assert (ll["rol"], ll["pensar"], ll["temperatura"], ll["esquema"]) == ("revisor", True, 0, None)
    assert (ll["trabajo_id"], ll["asignatura_id"]) == (T, A)
    assert ll["max_tokens"] > 3500


def test_ok_si_coincide(ctx):
    [r] = _revisar(ctx, ClienteSimulado({"revisor": [_veredicto([2])]}), [_item(ctx, correcta=2)])
    assert (r.item_id, r.revisor) == ("i1", "ok")


def test_devuelto_dos_respuestas(ctx):
    [r] = _revisar(ctx, ClienteSimulado({"revisor": [_veredicto([1, 3])]}), [_item(ctx, correcta=1)])
    assert r.revisor == "devuelto"
    assert "opciones 2 y 4" in r.motivo


def test_devuelto_clave_distinta(ctx):
    [r] = _revisar(ctx, ClienteSimulado({"revisor": [_veredicto([0])]}), [_item(ctx, correcta=2)])
    assert r.revisor == "devuelto" and "opción 1" in r.motivo


def test_devuelto_resuelve_entregable(ctx):
    cliente = ClienteSimulado({"revisor": [_veredicto([2], resuelve=True, entregable="PAE 1")]})
    [r] = _revisar(ctx, cliente, [_item(ctx, correcta=2)])
    assert r.revisor == "devuelto" and "PAE 1" in r.motivo


def test_integridad_conserva_el_veredicto_de_la_clave(ctx):
    cliente = ClienteSimulado({"revisor": [_veredicto([0, 2], resuelve=True, entregable="PAE 1")]})
    [r] = _revisar(ctx, cliente, [_item(ctx, correcta=2)])
    assert r.revisor == "devuelto" and "PAE 1" in r.motivo and "1 y 3" in r.motivo


def test_integridad_admite_mismos_contenidos_con_otros_casos(ctx):
    # §9.4 regla 1: practicar el contenido del entregable con otro caso no lo resuelve.
    cliente = ClienteSimulado({"revisor": [_veredicto([2])]})
    _revisar(ctx, cliente, [_item(ctx)])
    pedido = cliente.llamadas[0]["mensajes"][-1]["content"]
    assert "otros casos y datos" in pedido and "total o parcialmente" not in pedido
    ficha = {"ideas_clave": ["a", "b", "c"], "relacion_ra": "r", "errores_frecuentes": ["e"]}
    cliente = ClienteSimulado({"revisor": [json.dumps({"resuelve_entregable": False})]})
    revisar_ficha(ficha, ctx, cliente, trabajo_id=T, asignatura_id=A)
    assert "otros casos y datos" in cliente.llamadas[0]["mensajes"][-1]["content"]


def test_sin_veredicto_tras_reintento(ctx):
    cliente = ClienteSimulado({"revisor": ["no sé", "no sé"]})
    [r] = _revisar(ctx, cliente, [_item(ctx)])
    assert (r.revisor, r.motivo) == ("sin_veredicto", "revisor sin veredicto")
    assert len(cliente.llamadas) == 2


def test_reintento_que_funciona(ctx):
    cliente = ClienteSimulado({"revisor": ["no sé", _veredicto([2])]})
    [r] = _revisar(ctx, cliente, [_item(ctx)])
    assert r.revisor == "ok" and len(cliente.llamadas) == 2


def test_un_item_por_llamada(ctx):
    cliente = ClienteSimulado({"revisor": lambda m: _veredicto([2])})
    resultados = _revisar(ctx, cliente, [_item(ctx, f"i{k}") for k in range(1, 8)])
    assert [r.item_id for r in resultados] == [f"i{k}" for k in range(1, 8)]
    assert len(cliente.llamadas) == 7
    assert all(ll["timeout_s"] == 240 for ll in cliente.llamadas)


def test_pide_motivo_en_espanol(ctx):
    cliente = ClienteSimulado({"revisor": [_veredicto([2])]})
    _revisar(ctx, cliente, [_item(ctx)])
    texto = "\n".join(m["content"] for m in cliente.llamadas[0]["mensajes"])
    assert "en español" in texto and "motivo" in texto
    assert "PAE 1" in texto  # el revisor ve los entregables del momento


def test_revisar_ficha(ctx):
    ficha = {"ideas_clave": ["a", "b", "c"], "relacion_ra": "r", "errores_frecuentes": ["e"]}
    ok = revisar_ficha(ficha, ctx, ClienteSimulado({"revisor": [json.dumps(
        {"resuelve_entregable": False, "entregable": "", "motivo": ""})]}), trabajo_id=T, asignatura_id=A)
    assert (ok.item_id, ok.revisor) == ("ficha", "ok")
    mal = revisar_ficha(ficha, ctx, ClienteSimulado({"revisor": [json.dumps(
        {"resuelve_entregable": True, "entregable": "PAE 1", "motivo": "copia la PAE"})]}),
        trabajo_id=T, asignatura_id=A)
    assert mal.revisor == "devuelto" and "PAE 1" in mal.motivo


@pytest.mark.parametrize("indices", [
    [], [2], [0, 1, 2], [0, 1, 2, 3, 3], [0, 1, 2, 2],
    [-1, 1, 2, 3], [0, 1, 2, 4], [0, 1, 2, 3, 2],
], ids=["vacio", "parcial", "falta", "extra", "duplicado", "negativo",
        "fuera_de_rango", "contradictorio"])
@pytest.mark.parametrize("recupera", [False, True])
def test_veredictos_invalidos_reintentan(ctx, indices, recupera):
    invalido = json.dumps({
        "veredictos": [{"opcion": k, "valida": k == 2 and i == 2}
                       for i, k in enumerate(indices)],
        "resuelve_entregable": False,
    })
    cliente = ClienteSimulado({"revisor": [
        invalido, _veredicto([2]) if recupera else invalido,
    ]})
    [r] = _revisar(ctx, cliente, [_item(ctx)])
    assert r.revisor == ("ok" if recupera else "sin_veredicto")
    if not recupera:
        assert r.motivo == "revisor sin veredicto"
    assert len(cliente.llamadas) == 2


@pytest.mark.parametrize("ficha", [False, True])
@pytest.mark.parametrize("recupera", [False, True])
def test_length_con_json_completo_reintenta(ctx, monkeypatch, ficha, recupera):
    cliente = ClienteSimulado({"revisor": [_veredicto([2]), _veredicto([2])]})
    completar = cliente.completar

    def respuesta(*args, **kwargs):
        resultado = completar(*args, **kwargs)
        return replace(resultado, finish_reason=(
            "stop" if recupera and len(cliente.llamadas) == 2 else "length"))

    monkeypatch.setattr(cliente, "completar", respuesta)
    if ficha:
        r = revisar_ficha({"ideas_clave": ["a"]}, ctx, cliente,
                          trabajo_id=T, asignatura_id=A)
    else:
        [r] = _revisar(ctx, cliente, [_item(ctx)])
    assert r.revisor == ("ok" if recupera else "sin_veredicto")
    if not recupera:
        assert r.motivo == "revisor sin veredicto"
    assert len(cliente.llamadas) == 2
