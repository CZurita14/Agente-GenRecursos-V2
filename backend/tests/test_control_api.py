"""A5: cuotas persistentes, permisos administrativos y registro mínimo."""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.api.aplicacion import crear_app
from app.auth.servicio import ServicioAuth
from app.config import Ajustes

ORIGEN = "https://materiales.example"


@pytest.fixture
def entorno(nueva_conexion):
    enviados = {}
    auth = ServicioAuth(nueva_conexion, "s" * 48, lambda c, k: enviados.update({c: k}))

    def construir(**kw):
        config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                         llm_model="m", api_origen=ORIGEN, auth_secreto="s" * 48,
                         administradores=["admin@uti.edu.ec"], **kw)
        app = crear_app(config, auth=auth, conexion=nueva_conexion)
        app.state.control.limites.ahora = lambda: datetime(2026, 10, 27, 12, 5, tzinfo=timezone.utc)
        return app

    with ExitStack() as pila:
        def cliente(app=None, correo=None, ip="198.51.100.10"):
            app = app or construir()
            c = pila.enter_context(TestClient(app, base_url=ORIGEN, client=(ip, 12345)))
            if correo:
                auth.pedir(correo)
                c.cookies.set("sesion", auth.verificar(correo, enviados[correo]))
            return c

        yield construir, cliente, enviados


def test_consumo_solo_admin_configurado(entorno, conn):
    _, cliente, _ = entorno
    normal = cliente(correo="docente@uti.edu.ec")
    assert normal.get("/admin/consumo", headers={"X-Rol": "administrador"}).status_code == 403
    admin = cliente(correo="admin@uti.edu.ec", ip="198.51.100.20")
    assert admin.get("/auth/yo").json()["rol"] == "administrador"
    conn.execute("insert into llamada_llm (rol,tokens_entrada,tokens_salida,segundos,ok) "
                 "values ('worker',100,50,2.5,true),('revisor',20,10,1,false)")
    r = admin.get("/admin/consumo")
    assert r.status_code == 200
    total = r.json()["totales"]
    assert total["llamadas"] == 2 and total["tokens_entrada"] == 120 and total["tokens_salida"] == 60
    assert total["fallos"] == 1
    assert "asignatura_id" not in r.text and "correo" not in r.text


def test_consumo_acota_intervalo_y_no_admite_usuario_sin_sesion(entorno):
    _, cliente, _ = entorno
    assert cliente().get("/admin/consumo").status_code == 401
    admin = cliente(correo="admin@uti.edu.ec", ip="198.51.100.30")
    assert admin.get("/admin/consumo?desde=2026-01-01&hasta=2026-12-31").status_code == 422
    assert admin.get("/admin/consumo?desde=2026-12-31&hasta=2026-01-01").status_code == 422
    assert admin.get("/admin/consumo?hasta=0001-01-01").status_code == 422


def test_cuota_ip_persiste_entre_instancias_y_no_acepta_xff_no_confiable(entorno):
    construir, cliente, _ = entorno
    c = cliente(construir(limite_ip_minuto=2))
    for n in range(2):
        assert c.get("/auth/yo", headers={"X-Forwarded-For": f"203.0.113.{n}"}).status_code == 401
    otra = cliente(construir(limite_ip_minuto=2))
    r = otra.get("/auth/yo", headers={"X-Forwarded-For": "203.0.113.100"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_cuota_por_usuario_suma_sesiones_y_diferentes_ips(entorno):
    construir, cliente, _ = entorno
    app = construir(limite_usuario_minuto=1)
    c1 = cliente(app, correo="docente@uti.edu.ec", ip="198.51.100.11")
    assert c1.get("/auth/yo").status_code == 200
    # Copiar una sesión válida a otro cliente; no solicitar otro código en el cooldown.
    c2 = cliente(app, ip="198.51.100.12")
    c2.cookies.set("sesion", c1.cookies.get("sesion"))
    assert c2.get("/auth/yo").status_code == 429


def test_cuota_email_codigo_no_se_elude_rotando_ip(entorno, conn):
    construir, cliente, enviados = entorno
    app = construir(limite_codigo_correo_hora=1)
    uno = cliente(app, ip="198.51.100.41")
    r = uno.post("/auth/codigo", json={"correo": "docente@uti.edu.ec"}, headers={"Origin": ORIGEN})
    assert r.status_code == 200
    conn.execute("update auth_reto set emitido=clock_timestamp()-interval '61 seconds'")
    otro = cliente(app, ip="198.51.100.42")
    r = otro.post("/auth/codigo", json={"correo": "Docente@UTI.EDU.EC"}, headers={"Origin": ORIGEN})
    assert r.status_code == 429 and "retry-after" in r.headers


def test_auditoria_no_guarda_cuerpo_url_query_cookie_ip_ni_correo(entorno, conn):
    _, cliente, _ = entorno
    c = cliente(correo="docente@uti.edu.ec")
    token = c.cookies.get("sesion")
    c.get("/auth/yo?secreto=CANARIO-QUERY")
    c.post("/asignaturas/no-uuid/compartir", json={"correo": "secreto@uti.edu.ec", "canario": "CANARIO-CUERPO"},
           headers={"Origin": ORIGEN})
    filas = conn.execute("select * from acceso_api").fetchall()
    assert filas and all(f["estado"] in (200, 422) for f in filas)
    texto = json.dumps(filas, default=str)
    for privado in ("CANARIO", token, "198.51.100.10", "docente@uti.edu.ec", "secreto@uti.edu.ec", "no-uuid"):
        assert privado not in texto
    assert all(len(f["ip_hash"]) == 64 and len(f["actor_hash"]) == 64 for f in filas)


def test_avisoprivacidad_borrador_y_protegido(entorno):
    _, cliente, _ = entorno
    assert cliente().get("/privacidad").status_code == 401
    c = cliente(correo="docente@uti.edu.ec", ip="198.51.100.51")
    r = c.get("/privacidad")
    assert r.status_code == 200 and r.json()["estado"] == "borrador"
    assert "revisión institucional" in r.json()["texto"]


def test_no_log_access_crudo_de_uvicorn(entorno):
    _, cliente, _ = entorno
    cliente(correo="docente@uti.edu.ec")
    assert logging.getLogger("uvicorn.access").disabled is True


def test_fallo_de_auditoria_no_revierte_respuesta_ni_filtra_error(entorno, caplog):
    construir, cliente, _ = entorno
    app = construir()
    c = cliente(app, correo="docente@uti.edu.ec")

    def falla():
        raise RuntimeError("CANARIO-PRIVADO")

    app.state.control.conexion = falla
    with caplog.at_level(logging.WARNING):
        r = c.get("/auth/yo")
    assert r.status_code == 200
    assert "CANARIO" not in caplog.text and "RuntimeError" in caplog.text


def test_error_inesperado_no_filtra_excepcion_en_respuesta_o_log(entorno, caplog):
    construir, cliente, _ = entorno
    app = construir()

    def falla():
        raise RuntimeError("CANARIO-PRIVADO")

    app.add_api_route("/prueba-error", falla)
    c = cliente(app, correo="docente@uti.edu.ec")
    with caplog.at_level(logging.WARNING):
        r = c.get("/prueba-error")
    assert r.status_code == 500 and "CANARIO" not in r.text and "CANARIO" not in caplog.text


def test_rechazos_429_no_generan_bitacora_ilimitada(entorno, conn):
    construir, cliente, _ = entorno
    c = cliente(construir(limite_ip_minuto=1))
    assert c.get("/auth/yo").status_code == 401
    for _ in range(4):
        assert c.get("/auth/yo").status_code == 429
    filas = conn.execute("select estado from acceso_api").fetchall()
    assert sorted(f["estado"] for f in filas) == [401, 429]


def test_proxy_invalido_no_agota_la_cuota_del_proxy_legitimo(entorno):
    construir, cliente, _ = entorno
    app = construir(limite_ip_minuto=1, proxies_confiables=["10.0.0.1/32"])
    c = cliente(app, ip="10.0.0.1")
    assert c.get("/auth/yo", headers={"X-Forwarded-For": "invalido"}).status_code == 400
    assert c.get("/auth/yo", headers={"X-Forwarded-For": "invalido"}).status_code == 429
    assert c.get("/auth/yo").status_code == 401
    assert c.get("/auth/yo", headers={"X-Forwarded-For": "198.51.100.20"}).status_code == 401


def test_cuota_generacion_no_deja_un_segundo_trabajo(entorno, silabo, conn):
    construir, cliente, _ = entorno
    app = construir(limite_generar_correo_hora=1)
    c = cliente(app, correo="docente@uti.edu.ec")
    aid = app.state.asignaturas.guardar("docente@uti.edu.ec", silabo)["id"]
    datos = {"ambito": {"tipo": "clase", "id": "M2-S1"}, "herramientas": ["cuestionario"]}
    assert c.post(f"/asignaturas/{aid}/generar", json=datos, headers={"Origin": ORIGEN}).status_code == 202
    assert c.post(f"/asignaturas/{aid}/generar", json=datos, headers={"Origin": ORIGEN}).status_code == 429
    assert conn.execute("select count(*) n from trabajo").fetchone()["n"] == 1


def test_cuota_pdf_rechaza_antes_del_lector(entorno, silabo):
    construir, cliente, _ = entorno
    app = construir(limite_pdf_correo_hora=1)
    c = cliente(app, correo="docente@uti.edu.ec")
    lecturas = []

    def lector(*_, **__):
        lecturas.append(True)
        return silabo

    app.state.lector_pdf = lector
    headers = {"Origin": ORIGEN, "Content-Type": "application/pdf"}
    assert c.post("/silabos", content=b"%PDF-prueba", headers=headers).status_code == 201
    assert c.post("/silabos", content=b"%PDF-prueba", headers=headers).status_code == 429
    assert len(lecturas) == 1


def test_agotar_cuota_usuario_no_impide_revocar_sesion(entorno):
    construir, cliente, _ = entorno
    app = construir(limite_usuario_minuto=1)
    c = cliente(app, correo="docente@uti.edu.ec")
    token = c.cookies.get("sesion")
    assert c.get("/auth/yo").status_code == 200
    assert c.get("/auth/yo").status_code == 429
    assert c.post("/auth/salir", headers={"Origin": ORIGEN}).status_code == 200
    assert app.state.auth.identificar(token) is None


def test_peticiones_reutilizan_conexiones(nueva_conexion):
    # Revisión A5: sin pool, cada petición autenticada abría al menos 5 conexiones (~15 ms c/u).
    creadas = []

    def contar():
        creadas.append(1)
        return nueva_conexion()

    enviados = {}
    auth = ServicioAuth(contar, "s" * 48, lambda c, k: enviados.update({c: k}))
    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                     llm_model="m", api_origen=ORIGEN, auth_secreto="s" * 48)
    app = crear_app(config, auth=auth, conexion=contar)
    auth.conexion = app.state.conexion  # Como en producción: la sesión usa la fábrica de la app.
    with TestClient(app, base_url=ORIGEN, client=("198.51.100.30", 1)) as c:
        auth.pedir("docente@uti.edu.ec")
        c.cookies.set("sesion", auth.verificar("docente@uti.edu.ec", enviados["docente@uti.edu.ec"]))
        antes = len(creadas)
        for _ in range(5):
            assert c.get("/auth/yo").status_code == 200
        assert len(creadas) - antes <= 2
