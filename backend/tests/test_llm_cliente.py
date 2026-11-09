"""Pruebas del cliente de IA; nunca llaman al servidor real."""
import json
import logging

import httpx
import pytest
from pydantic import BaseModel

from app.llm.cliente import (
    ClienteSimulado, ClienteVLLM, ContextoExcedido, ErrorDelServidor, Respuesta,
    ServidorNoDisponible,
)
from app.llm.json import JsonInvalido, pedir_json, ultimo_json

BASE = "http://servidor.test:8000/v1"
MSJ = [{"role": "user", "content": "hola"}]
ESQUEMA = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}


def test_cierre_del_cliente_libera_conexiones():
    cliente = ClienteVLLM(BASE, "m", 1, 1, lambda _: None)
    cliente.close()
    assert cliente._http.is_closed


def _respuesta_chat(content, reasoning=None, finish="stop"):
    mensaje = {"role": "assistant", "content": content}
    if reasoning is not None:
        mensaje["reasoning"] = reasoning
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "message": mensaje, "finish_reason": finish}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _cliente(manejador, registros=None):
    cuerpos = []

    def transporte(peticion: httpx.Request):
        if peticion.url.path.endswith("/tokenize"):
            cuerpos.append(("tokenize", json.loads(peticion.content)))
        else:
            cuerpos.append(("chat", json.loads(peticion.content)))
        return manejador(peticion)

    cliente = ClienteVLLM(
        BASE, "m", 120, 2, (registros if registros is not None else []).append,
        transporte=httpx.MockTransport(transporte),
    )
    return cliente, cuerpos


def _normal(contenido="ok", reasoning=None, tokens=100):
    def manejador(p):
        if p.url.path.endswith("/tokenize"):
            return httpx.Response(200, json={"count": tokens})
        return httpx.Response(200, json=_respuesta_chat(contenido, reasoning))
    return manejador


def _completar(c, **kw):
    base = dict(rol="r", esquema=None, temperatura=0.4, max_tokens=1000, pensar=False,
                trabajo_id=None, asignatura_id=None)
    base.update(kw)
    return c.completar(MSJ, **base)


def test_payload_con_esquema():
    c, cuerpos = _cliente(_normal('{"a":1}'))
    _completar(c, esquema=ESQUEMA)
    cuerpo = [b for t, b in cuerpos if t == "chat"][0]
    assert cuerpo["repetition_penalty"] == 1.05
    assert cuerpo["response_format"]["type"] == "json_schema"
    assert cuerpo["chat_template_kwargs"] == {"enable_thinking": False}
    assert not cuerpo.get("stream")


def test_sin_esquema_no_envia_penalizacion():
    c, cuerpos = _cliente(_normal())
    _completar(c)
    cuerpo = [b for t, b in cuerpos if t == "chat"][0]
    assert "repetition_penalty" not in cuerpo and "response_format" not in cuerpo


def test_max_tokens_respeta_contexto():
    c, cuerpos = _cliente(_normal(tokens=5000))
    _completar(c, max_tokens=6500)
    cuerpo = [b for t, b in cuerpos if t == "chat"][0]
    assert cuerpo["max_tokens"] == 8192 - 5000 - 300


def test_contexto_excedido():
    c, cuerpos = _cliente(_normal(tokens=7800))
    with pytest.raises(ContextoExcedido):
        _completar(c)
    assert not [1 for t, _ in cuerpos if t == "chat"]


def test_tokenize_usa_raiz_sin_v1():
    rutas = []

    def manejador(p):
        rutas.append(str(p.url))
        return httpx.Response(200, json={"count": 7})
    c, cuerpos = _cliente(manejador)
    assert c.contar_tokens(MSJ) == 7
    assert rutas == ["http://servidor.test:8000/tokenize"]
    assert cuerpos[0][1] == {"model": "m", "messages": MSJ}


def test_un_reintento_y_servidor_no_disponible():
    llamadas = []

    def manejador(p):
        if p.url.path.endswith("/tokenize"):
            return httpx.Response(200, json={"count": 100})
        llamadas.append(1)
        raise httpx.ConnectError("sin red")
    registros = []
    c, _ = _cliente(manejador, registros)
    with pytest.raises(ServidorNoDisponible):
        _completar(c, trabajo_id=None)
    assert len(llamadas) == 2
    assert registros[-1]["ok"] is False


def test_reintento_5xx_y_exito():
    estado = {"n": 0}

    def manejador(p):
        if p.url.path.endswith("/tokenize"):
            return httpx.Response(200, json={"count": 100})
        estado["n"] += 1
        if estado["n"] == 1:
            return httpx.Response(503, json={"error": "ocupado"})
        return httpx.Response(200, json=_respuesta_chat("hola"))
    registros = []
    c, _ = _cliente(manejador, registros)
    r = _completar(c)
    assert r.texto == "hola" and estado["n"] == 2
    assert registros[-1]["ok"] is True
    assert registros[-1]["tokens_entrada"] == 10 and registros[-1]["tokens_salida"] == 5
    assert set(registros[-1]) >= {"trabajo_id", "asignatura_id", "rol", "tokens_entrada",
                                  "tokens_salida", "segundos", "ok"}


def test_pedir_json_reintenta_dos_veces():
    class M(BaseModel):
        a: int
    sim = ClienteSimulado({"r": ["{" + " " * 50] * 3})
    with pytest.raises(JsonInvalido):
        pedir_json(sim, MSJ, M, ESQUEMA, rol="r")
    assert len(sim.llamadas) == 3
    sim = ClienteSimulado({"r": ["{" + " " * 50, '{"a": 2}']})
    valor, _ = pedir_json(sim, MSJ, M, ESQUEMA, rol="r")
    assert valor.a == 2 and len(sim.llamadas) == 2


def test_simulado_lista_vacia_y_callable():
    sim = ClienteSimulado({"r": [], "f": lambda m: "x" * 8})
    with pytest.raises(AssertionError):
        sim.completar(MSJ, rol="r", esquema=None, temperatura=0, max_tokens=10, pensar=False,
                      trabajo_id=None, asignatura_id=None)
    r = sim.completar(MSJ, rol="f", esquema=None, temperatura=0, max_tokens=10, pensar=False,
                      trabajo_id=None, asignatura_id=None)
    assert r.texto == "xxxxxxxx" and r.tokens_salida == 2
    assert sim.llamadas[-1]["rol"] == "f"


def test_ultimo_json_ignora_think():
    assert ultimo_json('<think>{"a":1}</think> razono… {"b": 2}') == {"b": 2}


def test_separa_razonamiento_en_content():
    c, _ = _cliente(_normal("<think>\nOkay, 17*3…\n</think>\n\n51", reasoning=None))
    r = _completar(c, pensar=True)
    assert r.texto == "51" and r.razonamiento.startswith("Okay")


def test_separa_razonamiento_en_campo():
    c, _ = _cliente(_normal("51", reasoning="Okay…"))
    r = _completar(c, pensar=True)
    assert r.texto == "51" and r.razonamiento.startswith("Okay")


def test_extra_body():
    c, cuerpos = _cliente(_normal('{"a":1}'))
    _completar(c, esquema=ESQUEMA, pensar=True)
    cuerpo = [b for t, b in cuerpos if t == "chat"][0]
    assert cuerpo["chat_template_kwargs"] == {"enable_thinking": True}
    assert cuerpo["repetition_penalty"] == 1.05
    assert "extra_body" not in cuerpo


def test_4xx_en_chat_no_se_reintenta():
    llamadas = []

    def manejador(p):
        if p.url.path.endswith("/tokenize"):
            return httpx.Response(200, json={"count": 100})
        llamadas.append(1)
        return httpx.Response(400, json={"error": "mala peticion"})
    registros = []
    c, _ = _cliente(manejador, registros)
    with pytest.raises(Exception) as info:
        _completar(c)
    assert not isinstance(info.value, ServidorNoDisponible)
    assert len(llamadas) == 1 and registros[-1]["ok"] is False


def test_semaforo_se_libera_tras_excepcion():
    estado = {"n": 0}

    def manejador(p):
        if p.url.path.endswith("/tokenize"):
            return httpx.Response(200, json={"count": 100})
        estado["n"] += 1
        if estado["n"] <= 2:
            raise httpx.ConnectError("sin red")
        return httpx.Response(200, json=_respuesta_chat("ok"))
    c = ClienteVLLM(BASE, "m", 120, 1, lambda d: None,
                    transporte=httpx.MockTransport(manejador))
    with pytest.raises(ServidorNoDisponible):
        _completar(c)
    assert _completar(c).texto == "ok"  # con max_concurrencia=1 se bloquearía si no se liberó


def test_registrar_que_falla_no_tapa_el_resultado(caplog):
    def malo(d):
        raise RuntimeError("bd caída")
    c = ClienteVLLM(BASE, "m", 120, 1, malo, transporte=httpx.MockTransport(_normal("hola")))
    with caplog.at_level(logging.ERROR, logger="app.llm"):
        assert _completar(c).texto == "hola"
    assert any(r.name == "app.llm" for r in caplog.records)

    def caido(p):
        if p.url.path.endswith("/tokenize"):
            return httpx.Response(200, json={"count": 100})
        raise httpx.ConnectError("sin red")
    c = ClienteVLLM(BASE, "m", 120, 1, malo, transporte=httpx.MockTransport(caido))
    with pytest.raises(ServidorNoDisponible):
        _completar(c)


def test_tokenize_4xx_no_reintenta():
    n = []

    def manejador(p):
        n.append(1)
        return httpx.Response(422, json={"error": "x"})
    c, _ = _cliente(manejador)
    with pytest.raises(ErrorDelServidor):
        c.contar_tokens(MSJ)
    assert len(n) == 1


def test_tokenize_red_transitoria_y_exito():
    n = []

    def manejador(p):
        n.append(1)
        if len(n) == 1:
            raise httpx.ConnectError("sin red")
        return httpx.Response(200, json={"count": 9})
    c, _ = _cliente(manejador)
    assert c.contar_tokens(MSJ) == 9 and len(n) == 2


def test_tokenize_cuerpo_invalido_y_5xx_persistente():
    c, _ = _cliente(lambda p: httpx.Response(200, json={"otro": 1}))
    with pytest.raises(ErrorDelServidor):
        c.contar_tokens(MSJ)
    n = []

    def manejador(p):
        n.append(1)
        return httpx.Response(503)
    c, _ = _cliente(manejador)
    with pytest.raises(ServidorNoDisponible):
        c.contar_tokens(MSJ)
    assert len(n) == 2


def test_finish_reason_se_rellena():
    def manejador(p):
        if p.url.path.endswith("/tokenize"):
            return httpx.Response(200, json={"count": 100})
        return httpx.Response(200, json=_respuesta_chat("{", finish="length"))
    c, _ = _cliente(manejador)
    assert _completar(c).finish_reason == "length"


def test_pedir_json_reintenta_si_finish_reason_length():
    class M(BaseModel):
        a: int

    class Corta(ClienteSimulado):
        def completar(self, *a, **k):
            r = super().completar(*a, **k)
            if len(self.llamadas) == 1:  # válido pero cortado: igual se reintenta
                return Respuesta(r.texto, "", 1, 1, 0.0, "length")
            return r
    sim = Corta({"r": ['{"a": 1}', '{"a": 2}']})
    valor, _ = pedir_json(sim, MSJ, M, ESQUEMA, rol="r")
    assert valor.a == 2 and len(sim.llamadas) == 2


def test_ultimo_json_dos_objetos():
    assert ultimo_json('{"a":1} texto {"b":2}') == {"b": 2}
    assert ultimo_json('x {"a":{"b":1}} fin') == {"a": {"b": 1}}
