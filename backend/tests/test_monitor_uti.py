"""API UTI v1 para el Monitor de Agentes: token, capacidades, salud y eventos sin datos personales."""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.aplicacion import crear_app
from app.auth.servicio import ServicioAuth
from app.config import Ajustes
from app.sga.simulado import ProveedorSimulado

ORIGEN = "https://materiales.example"
SGA = Path(__file__).parent / "fixtures" / "sga"
TOKEN = "token-de-prueba-del-monitor-0123456789"
AGENTE = "generador-recursos-uti"
CORREO = "docente.privado@uti.edu.ec"


@pytest.fixture
def entorno(nueva_conexion):
    auth = ServicioAuth(nueva_conexion, "s" * 48, ProveedorSimulado(SGA))

    def construir(**kw):
        kw.setdefault("monitor_token_hash", hashlib.sha256(TOKEN.encode()).hexdigest())
        config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                         llm_model="m", api_origen=ORIGEN, auth_secreto="s" * 48, **kw)
        return crear_app(config, auth=auth, conexion=nueva_conexion)

    with ExitStack() as pila:
        def cliente(app):
            return pila.enter_context(TestClient(app, base_url=ORIGEN))
        yield construir, cliente


def _h(token=TOKEN):
    return {"Authorization": f"Bearer {token}"}


def _trabajo(conn, aid, herramienta, estado, *, tipo="generacion", hace=timedelta(minutes=5), error=None):
    tid = uuid4()
    creado = datetime.now(timezone.utc) - hace
    conn.execute("insert into trabajo (id,asignatura_id,agente,ambito_tipo,ambito_id,herramienta,tipo,estado,error,"
                 "tokens_entrada,tokens_salida,creado,actualizado) values (%s,%s,'general','clase','M2-S1',%s,%s,%s,%s,"
                 "3000,1000,%s,%s)", (tid, aid, herramienta, tipo, estado, error, creado, creado + timedelta(seconds=20)))
    conn.execute("insert into llamada_llm (trabajo_id,asignatura_id,rol,tokens_entrada,tokens_salida,segundos,ok,creado,"
                 "modelo,tokens_cache,costo_usd) values (%s,%s,'worker',3000,1000,2.0,%s,%s,'deepseek-v4-pro',0,0.0086)",
                 (tid, aid, estado != "error", creado))
    return tid


@pytest.fixture
def sembrado(entorno, silabo, conn):
    construir, cliente = entorno
    app = construir()
    c = cliente(app)
    aid = app.state.asignaturas.guardar(CORREO, silabo)["id"]
    _trabajo(conn, aid, "tarjetas", "listo", hace=timedelta(minutes=30))
    _trabajo(conn, aid, "cuestionario", "requiere_revision", hace=timedelta(minutes=20))
    _trabajo(conn, aid, "presentacion", "error", hace=timedelta(minutes=10), error="JsonInvalido: no se pudo completar el trabajo")
    _trabajo(conn, aid, "chat", "listo", tipo="chat", hace=timedelta(minutes=5))
    conn.execute("insert into materia_sga (correo,id_sga,codigo_pf,paralelo,nombre,carrera,estado_sga,estado,fallos,sincronizada) "
                 "values (%s,'9001','S91-SIMU-3-90001-9001','1','MATERIA','SOFTWARE','ACTIVA','invalida',%s,%s)",
                 (CORREO, json.dumps(["inclusion: falta"]), datetime.now(timezone.utc) - timedelta(minutes=2)))
    return app, c


# --- autenticación ---------------------------------------------------------------------------


@pytest.mark.parametrize("ruta", ["/v1/capabilities", "/v1/health", "/v1/events"])
def test_sin_token_401_y_no_usa_la_sesion(sembrado, ruta):
    _, c = sembrado
    assert c.get(ruta).status_code == 401
    assert c.get(ruta, headers=_h("otro-token")).status_code == 401
    assert c.get(ruta, headers=_h()).status_code == 200


def test_sin_token_configurado_503(entorno):
    construir, cliente = entorno
    c = cliente(construir(monitor_token_hash=None))
    assert c.get("/v1/capabilities", headers=_h()).status_code == 503


def test_el_token_del_monitor_no_abre_el_resto_de_la_api(sembrado):
    _, c = sembrado
    assert c.get("/asignaturas", headers=_h()).status_code == 401


# --- capacidades y salud ---------------------------------------------------------------------


def test_capacidades(sembrado):
    _, c = sembrado
    assert c.get("/v1/capabilities", headers=_h()).json() == {
        "protocolVersion": "1", "agentId": AGENTE, "configuration": False, "training": False, "weightRules": {}}


def test_salud(sembrado):
    _, c = sembrado
    d = c.get("/v1/health", headers=_h()).json()
    assert d["status"] in ("ready", "degraded")
    m = d["metrics"]
    assert m["errorRate"] == 0.5  # en los últimos 15 minutos hubo 2 llamadas a la IA y 1 falló (con menos de 3, sigue ready)
    assert set(m) <= {"cpuPercent", "memoryMb", "errorRate"}
    assert all(v is None or v >= 0 for v in m.values())


def test_salud_degradada_con_muchos_fallos(entorno, silabo, conn):
    construir, cliente = entorno
    app = construir()
    c = cliente(app)
    aid = app.state.asignaturas.guardar(CORREO, silabo)["id"]
    for _ in range(3):
        _trabajo(conn, aid, "tarjetas", "error")
    assert c.get("/v1/health", headers=_h()).json()["status"] == "degraded"


def test_salud_sin_llamadas_omite_la_tasa(entorno):
    construir, cliente = entorno
    m = cliente(construir()).get("/v1/health", headers=_h()).json()["metrics"]
    assert "errorRate" not in m


# --- eventos ---------------------------------------------------------------------------------


def _todos(c, limit=100):
    eventos, cursor = [], None
    for _ in range(20):
        r = c.get("/v1/events", headers=_h(), params={"limit": limit, **({"cursor": cursor} if cursor else {})}).json()
        assert r["agentId"] == AGENTE and isinstance(r["nextCursor"], str) and r["nextCursor"]
        eventos += r["events"]
        cursor = r["nextCursor"]
        if not r["hasMore"]:
            return eventos, cursor
    raise AssertionError("no terminó")


def test_eventos_de_generacion_chat_y_silabo(sembrado):
    _, c = sembrado
    eventos, _ = _todos(c)
    tipos = [(e["type"], e["status"], e["severity"]) for e in eventos]
    assert ("servicio.iniciado", "ok", "info") in tipos
    assert ("recurso.generado", "ok", "info") in tipos
    assert ("recurso.revision_requerida", "needs_review", "warning") in tipos
    assert ("recurso.fallido", "failed", "error") in tipos
    assert ("chat.atendido", "ok", "info") in tipos
    assert ("silabo.invalido", "failed", "warning") in tipos
    assert sum(e["type"] == "recurso.solicitado" for e in eventos) == 3
    fechas = [e["timestamp"] for e in eventos]
    assert fechas == sorted(fechas)
    assert len({e["id"] for e in eventos}) == len(eventos)
    generado = next(e for e in eventos if e["type"] == "recurso.generado")
    assert generado["metadata"] == {"durationMs": 20000, "count": 4000, "success": True}
    assert "Tarjetas" in generado["message"] and "Momento 2, sesión 1" in generado["message"]


def test_eventos_sin_datos_personales(sembrado):
    _, c = sembrado
    texto = json.dumps(_todos(c)[0], ensure_ascii=False)
    assert CORREO not in texto and "@" not in texto
    assert "inclusion: falta" in texto  # el fallo nombra la ruta del campo, nunca su valor


def test_paginacion_por_cursor_sin_repetir_ni_perder(sembrado):
    _, c = sembrado
    todos, _ = _todos(c)
    por_paginas, _ = _todos(c, limit=2)
    assert [e["id"] for e in por_paginas] == [e["id"] for e in todos]


def test_cursor_final_no_repite_y_trae_lo_nuevo(sembrado, conn):
    app, c = sembrado
    _, cursor = _todos(c)
    r = c.get("/v1/events", headers=_h(), params={"cursor": cursor}).json()
    assert r["events"] == [] and r["hasMore"] is False and r["nextCursor"] == cursor
    aid = conn.execute("select id from asignatura").fetchone()["id"]
    _trabajo(conn, aid, "tarjetas", "listo", hace=timedelta(seconds=-60))
    nuevos = c.get("/v1/events", headers=_h(), params={"cursor": cursor}).json()["events"]
    assert {e["type"] for e in nuevos} == {"recurso.solicitado", "recurso.generado"}


def test_cursor_invalido_400(sembrado):
    _, c = sembrado
    assert c.get("/v1/events", headers=_h(), params={"cursor": "basura"}).status_code == 400


def test_limite_maximo_100(sembrado):
    _, c = sembrado
    assert c.get("/v1/events", headers=_h(), params={"limit": 101}).status_code == 422


def test_comando_token_monitor(tmp_path, capsys):
    from app import operacion
    destino = tmp_path / "token.txt"
    assert operacion.main(["token-monitor", str(destino)]) == 0
    token = destino.read_text(encoding="utf-8").strip()
    salida = capsys.readouterr().out.strip()
    assert len(token) >= 40 and token not in salida
    assert salida == hashlib.sha256(token.encode()).hexdigest()
    assert operacion.main(["token-monitor", str(destino)]) != 0 or destino.read_text(encoding="utf-8").strip() == token
