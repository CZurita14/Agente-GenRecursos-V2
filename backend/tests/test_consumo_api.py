"""Panel de consumo de tokens: alcance por cuenta, desgloses, costo y clave del panel."""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import io
import json
import logging
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.aplicacion import crear_app
from app.auth.servicio import ServicioAuth
from app.config import Ajustes
from app.control.clave import hashear, verificar
from app.sga.simulado import ProveedorSimulado

ORIGEN = "https://materiales.example"
SGA = Path(__file__).parent / "fixtures" / "sga"
CLAVE = "clave-de-prueba-del-panel"
YO, OTRO, ADMIN = "docente@uti.edu.ec", "otro@uti.edu.ec", "admin@uti.edu.ec"
POST = {"Origin": ORIGEN}


@pytest.fixture(scope="module")
def hash_clave():
    return hashear(CLAVE, iteraciones=1000)


@pytest.fixture
def entorno(nueva_conexion, hash_clave):
    auth = ServicioAuth(nueva_conexion, "s" * 48, ProveedorSimulado(SGA))

    def construir(**kw):
        kw.setdefault("consumo_clave_hash", hash_clave)
        config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                         llm_model="m", api_origen=ORIGEN, auth_secreto="s" * 48, administradores=[ADMIN], **kw)
        return crear_app(config, auth=auth, conexion=nueva_conexion)

    with ExitStack() as pila:
        def cliente(app, correo=None):
            c = pila.enter_context(TestClient(app, base_url=ORIGEN))
            if correo:
                c.cookies.set("sesion", auth.sesion_directa(correo))
            return c
        yield construir, cliente


def _trabajo(conn, aid, herramienta, *, tipo="generacion", estado="listo", hace=timedelta(hours=1),
             llamadas=((("worker", 1000, 500, 2.0, True)),)):
    tid = uuid4()
    creado = datetime.now(timezone.utc) - hace
    conn.execute("insert into trabajo (id,asignatura_id,agente,ambito_tipo,ambito_id,herramienta,tipo,estado,"
                 "tokens_entrada,tokens_salida,creado,actualizado) values (%s,%s,'general','clase','M1-S1',%s,%s,%s,%s,%s,%s,%s)",
                 (tid, aid, herramienta, tipo, estado, sum(l[1] for l in llamadas), sum(l[2] for l in llamadas),
                  creado, creado + timedelta(minutes=3)))
    for rol, e, s, seg, ok, *costo in llamadas:
        # costo = (modelo, tokens en caché, costo_usd); sin él, una llamada anterior al registro de costo.
        modelo, cache, usd = costo or (None, 0, None)
        conn.execute("insert into llamada_llm (trabajo_id,asignatura_id,rol,tokens_entrada,tokens_salida,segundos,ok,creado,"
                     "modelo,tokens_cache,costo_usd) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                     (tid, aid, rol, e, s, seg, ok, creado, modelo, cache, usd))
    return tid


@pytest.fixture
def sembrado(entorno, silabo, conn):
    construir, cliente = entorno
    app = construir()
    cliente(app)  # arranca la aplicación (lifespan) antes de usar sus servicios
    mia = app.state.asignaturas.guardar(YO, silabo)["id"]
    ajena = app.state.asignaturas.guardar(OTRO, silabo)["id"]
    _trabajo(conn, mia, "cuestionario", llamadas=(("worker", 10_000, 4_000, 5.0, True, "deepseek-v4-pro", 8_000, 0.02),
                                                   ("revisor", 30_000, 6_000, 9.0, True, "deepseek-v4-pro", 20_000, 0.03)))
    _trabajo(conn, mia, "tarjetas", llamadas=(("worker", 3_000, 1_000, 1.0, True),
                                              ("worker", 1_000, 0, 0.5, False)))
    _trabajo(conn, mia, "chat", tipo="chat", llamadas=(("coordinador", 2_000, 500, 1.0, True),))
    _trabajo(conn, ajena, "cuestionario", llamadas=(("worker", 999_000, 999_000, 9.0, True),))
    _trabajo(conn, mia, "tarjetas", hace=timedelta(days=40))  # fuera del periodo por omisión
    return app, cliente, str(mia), str(ajena)


def _desbloquear(c, clave=CLAVE):
    return c.post("/consumo/desbloquear", json={"clave": clave}, headers=POST)


# --- clave ---------------------------------------------------------------------------------


def test_hash_y_verificacion():
    h = hashear("abc", iteraciones=1000)
    assert h.startswith("pbkdf2_sha256$1000$") and verificar("abc", h)
    assert not verificar("abd", h) and not verificar("abc", "basura") and not verificar(" abc", h)


def test_hash_clave_por_stdin(monkeypatch, capsys):
    from app import operacion
    monkeypatch.setattr("sys.stdin", io.StringIO("otra-clave\n"))
    assert operacion.main(["hash-clave"]) == 0
    salida = capsys.readouterr().out.strip()
    assert verificar("otra-clave", salida) and "otra-clave" not in salida


# --- acceso ----------------------------------------------------------------------------------


def test_sin_sesion_401(sembrado):
    app, cliente, *_ = sembrado
    assert cliente(app).get("/consumo").status_code == 401


def test_sin_clave_403(sembrado):
    app, cliente, *_ = sembrado
    r = cliente(app, YO).get("/consumo")
    assert r.status_code == 403 and r.json()["detail"] == "Ingresa la clave del panel"


def test_clave_erronea_403(sembrado):
    app, cliente, *_ = sembrado
    c = cliente(app, YO)
    r = _desbloquear(c, "no-es")
    assert r.status_code == 403 and r.json()["detail"] == "Clave incorrecta"
    assert c.get("/consumo").status_code == 403


def test_clave_con_espacios_no_entra(sembrado):
    app, cliente, *_ = sembrado
    assert _desbloquear(cliente(app, YO), f" {CLAVE} ").status_code == 403


def test_clave_correcta_abre(sembrado):
    app, cliente, *_ = sembrado
    c = cliente(app, YO)
    r = _desbloquear(c)
    assert r.status_code == 204
    galleta = r.headers["set-cookie"].lower()
    assert "consumo=" in galleta and "httponly" in galleta and "max-age=1800" in galleta
    assert c.get("/consumo").status_code == 200


def test_admin_entra_directo(sembrado):
    app, cliente, *_ = sembrado
    assert cliente(app, ADMIN).get("/consumo").status_code == 200


def test_cookie_de_otra_sesion(sembrado):
    app, cliente, *_ = sembrado
    a = cliente(app, YO)
    _desbloquear(a)
    b = cliente(app, YO)  # otra sesión de la misma cuenta
    b.cookies.set("consumo", a.cookies.get("consumo"))
    assert b.get("/consumo").status_code == 403


def test_cookie_vencida(sembrado, monkeypatch):
    app, cliente, *_ = sembrado
    c = cliente(app, YO)
    _desbloquear(c)
    import app.api.consumo as modulo
    monkeypatch.setattr(modulo, "_ahora", lambda: datetime.now(timezone.utc) + timedelta(minutes=31))
    assert c.get("/consumo").status_code == 403


def test_sin_hash_503(entorno):
    construir, cliente = entorno
    app = construir(consumo_clave_hash=None)
    assert _desbloquear(cliente(app, YO)).status_code == 503
    assert cliente(app, ADMIN).get("/consumo").status_code == 200


def test_sexto_intento_429(sembrado):
    app, cliente, *_ = sembrado
    c = cliente(app, YO)
    assert [_desbloquear(c, "mal").status_code for _ in range(5)] == [403] * 5
    r = _desbloquear(c)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_clave_no_se_registra(sembrado, conn, caplog):
    app, cliente, *_ = sembrado
    with caplog.at_level(logging.DEBUG):
        _desbloquear(cliente(app, YO), "clave-secreta-que-no-debe-salir")
    assert "clave-secreta-que-no-debe-salir" not in caplog.text
    filas = conn.execute("select * from acceso_api").fetchall()
    assert "clave-secreta-que-no-debe-salir" not in json.dumps(filas, default=str)


# --- contenido -----------------------------------------------------------------------------


def _resumen(sembrado, **params):
    app, cliente, *_ = sembrado
    c = cliente(app, YO)
    _desbloquear(c)
    r = c.get("/consumo", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_solo_proyectos_de_la_cuenta(sembrado):
    _, _, mia, ajena = sembrado
    d = _resumen(sembrado)
    assert [a["id"] for a in d["proyectos"]] == [mia]
    assert d["totales"]["tokens_entrada"] == 46_000 and d["totales"]["tokens_salida"] == 11_500
    assert d["totales"]["llamadas"] == 5 and d["totales"]["fallos"] == 1


def test_proyecto_ajeno_404(sembrado):
    _, _, _, ajena = sembrado
    app, cliente, *_ = sembrado
    c = cliente(app, YO)
    _desbloquear(c)
    assert c.get("/consumo", params={"asignatura": ajena}).status_code == 404


def test_por_herramienta_chat_y_costo(sembrado):
    d = _resumen(sembrado)
    h = {x["herramienta"]: x for x in d["por_herramienta"]}
    assert set(h) == {"cuestionario", "tarjetas"}
    assert h["cuestionario"]["recursos"] == 1 and h["cuestionario"]["tokens"] == 50_000
    assert h["cuestionario"]["por_recurso"] == 50_000 and h["cuestionario"]["parte_revision"] == 0.72
    assert h["cuestionario"]["costo_usd"] == 0.05  # lo guardado por cada llamada
    assert d["chat"] == {"pedidos": 1, "tokens": 2_500}
    assert d["totales"]["tokens_cache"] == 28_000


def test_costo_guardado_mas_estimacion_de_llamadas_antiguas(sembrado):
    d = _resumen(sembrado)
    # Guardado: 0,02 + 0,03. Antiguas (sin modelo) a tarifa máxima de v4-pro: entrada 1,32 y salida 3,96 por millón.
    antiguas = ((3_000 + 1_000 + 2_000) * 1.32 + (1_000 + 0 + 500) * 3.96) / 1e6
    assert d["costo_usd"] == round(0.05 + antiguas, 4)
    assert d["costo_estimado_llamadas"] == 3
    assert d["tarifa"]["vigencia"] == "2026-11-24"


def test_recientes_sin_contenido(sembrado):
    d = _resumen(sembrado)
    assert len(d["recientes"]) == 2  # el chat y lo de hace 40 días no cuentan
    assert set(d["recientes"][0]) == {"herramienta", "ambito_id", "estado", "tokens", "segundos", "creado"}


def test_periodo_vacio(sembrado):
    d = _resumen(sembrado, desde="2020-01-01", hasta="2020-01-02")
    assert d["totales"]["tokens_entrada"] == 0 and d["por_herramienta"] == [] and d["recientes"] == []
    assert d["costo_usd"] == 0.0 and d["costo_estimado_llamadas"] == 0


def test_rango_maximo(sembrado):
    app, cliente, *_ = sembrado
    c = cliente(app, ADMIN)
    assert c.get("/consumo", params={"desde": "2026-01-01", "hasta": "2026-03-01"}).status_code == 422


def test_asignatura_inactiva_suma(sembrado, conn):
    _, _, mia, _ = sembrado
    conn.execute("update asignatura set activa_sga=false where id=%s", (mia,))
    d = _resumen(sembrado)
    assert d["totales"]["tokens_entrada"] == 46_000
