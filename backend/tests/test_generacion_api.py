"""A4 HTTP + cola + coordinador simulado; sin GPU ni correos reales."""
from contextlib import ExitStack
from copy import deepcopy
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.api.aplicacion import crear_app
from app.auth.servicio import ServicioAuth
from app.config import Ajustes
from app.agentes.orquestador import procesar_uno
from app.agentes.workers import WORKERS
from tests.test_coordinador import WorkerPrueba, cliente_revisor
from tests.test_asignaturas_concurrencia import esperar_locks

ORIGEN = "https://materiales.example"
HEADERS = {"Origin": ORIGEN}


@pytest.fixture
def entorno(nueva_conexion, silabo, conn, monkeypatch):
    enviados, clientes = {}, {}
    auth = ServicioAuth(nueva_conexion, "s" * 48, lambda c, k: enviados.update({c: k}))
    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                     llm_model="m", api_origen=ORIGEN, auth_secreto="s" * 48)
    app = crear_app(config, auth=auth, conexion=nueva_conexion, lector_pdf=lambda *_, **__: silabo)
    monkeypatch.setitem(WORKERS, "cuestionario", WorkerPrueba())
    monkeypatch.setitem(WORKERS, "ficha_clase", WorkerPrueba("ficha_clase"))
    with ExitStack() as pila:
        def cliente(correo):
            if correo not in clientes:
                c = pila.enter_context(TestClient(app, base_url=ORIGEN))
                auth.pedir(correo)
                c.cookies.set("sesion", auth.verificar(correo, enviados[correo]))
                clientes[correo] = c
            return clientes[correo]

        dueno = cliente("dueno@uti.edu.ec")
        aid = app.state.asignaturas.guardar("dueno@uti.edu.ec", silabo)["id"]

        def producir(herramienta="cuestionario", **kw):
            r = generar(dueno, aid, herramientas=[herramienta], **kw)
            assert r.status_code == 202, r.text
            assert procesar_uno(conn, cliente_revisor(), app.state.perfiles, "api-prueba", 360)
            filas = dueno.get(f"/asignaturas/{aid}/recursos").json()
            rid = next(f["id"] for f in filas if f["trabajo_id"] == r.json()["trabajos"][0]["id"])
            return dueno.get(f"/asignaturas/{aid}/recursos/{rid}").json()

        yield app, cliente, dueno, aid, producir


def generar(c, aid, **kw):
    datos = {"ambito": {"tipo": "clase", "id": "M2-S1"},
             "herramientas": ["cuestionario"], "cantidad": 4}
    datos.update(kw)
    return c.post(f"/asignaturas/{aid}/generar", json=datos, headers=HEADERS)


def guardar(c, aid, recurso, contenido=None, **kw):
    datos = {"revision": recurso["revision"], "contenido": contenido if contenido is not None else recurso["contenido"]}
    datos.update(kw)
    return c.put(f"/asignaturas/{aid}/recursos/{recurso['id']}", json=datos, headers=HEADERS)


def compartir(d, aid, correo, rol):
    return d.post(f"/asignaturas/{aid}/compartir", json={"correo": correo, "rol": rol}, headers=HEADERS)


def test_catalogo_solo_workers_disponibles_y_orden_de_facultad(entorno):
    _, _, d, aid, _ = entorno
    r = d.get(f"/asignaturas/{aid}/herramientas?ambito=clase")
    assert r.status_code == 200
    assert [h["id"] for h in r.json()["herramientas"]] == ["cuestionario", "ficha_clase"]
    assert r.json()["perfil_sugerido"] == "fundamentacion"
    # P3a/P3b: el ámbito momento ofrece sus propias herramientas, nunca las de clase.
    momento = [h["id"] for h in d.get(f"/asignaturas/{aid}/herramientas?ambito=momento").json()["herramientas"]]
    assert "cuestionario" not in momento and "ficha_clase" not in momento


def test_generar_encola_una_vez_por_herramienta_y_no_expone_snapshot(entorno, conn):
    _, _, d, aid, _ = entorno
    r = generar(d, aid, herramientas=["cuestionario", "ficha_clase"], instrucciones="Caso docente privado")
    assert r.status_code == 202 and len(r.json()["trabajos"]) == 2
    filas = d.get(f"/asignaturas/{aid}/trabajos").json()
    assert len(filas) == 2 and all(f["estado"] == "en_cola" for f in filas)
    assert all("parametros" not in f and "worker_id" not in f for f in filas)
    assert "Caso docente privado" not in str(filas)
    assert conn.execute("select parametros from trabajo limit 1").fetchone()["parametros"]["silabo"]


@pytest.mark.parametrize("cambios", [{"herramientas": ["desconocida"]}, {"herramientas": []},
    {"herramientas": ["cuestionario", "cuestionario"]}, {"cantidad": True}, {"cantidad": 41},
    {"ambito": {"tipo": "clase", "id": "AJENA"}}, {"ambito": {"tipo": "momento", "id": "M2"}},
    {"perfil_dificultad": "inventado"}, {"instrucciones": "x" * 4001}])
def test_generar_invalido_no_deja_trabajos(entorno, conn, cambios):
    _, _, d, aid, _ = entorno
    assert generar(d, aid, **cambios).status_code == 422
    assert conn.execute("select count(*) n from trabajo").fetchone()["n"] == 0


def test_perfil_elegido_llega_al_worker_y_a_evidencia(entorno):
    _, _, _, _, producir = entorno
    r = producir(perfil_dificultad="avanzado")
    assert r["evidencia"]["perfil_dificultad"] == "avanzado"
    assert r["revision"] == 0 and r["evidencia_vigente"] is True


def test_lector_consulta_pero_no_genera_ni_edita(entorno):
    _, cliente, d, aid, producir = entorno
    recurso = producir()
    l = cliente("lector@uti.edu.ec")
    compartir(d, aid, "lector@uti.edu.ec", "lector")
    for ruta in ("herramientas", "trabajos", "recursos", f"recursos/{recurso['id']}"):
        assert l.get(f"/asignaturas/{aid}/{ruta}").status_code == 200
    assert generar(l, aid).status_code == 403
    assert guardar(l, aid, recurso).status_code == 403


def test_editor_genera_y_edita_con_historial_y_evidencia_original(entorno, conn):
    _, cliente, d, aid, producir = entorno
    recurso = producir()
    editor = cliente("editor@uti.edu.ec")
    compartir(d, aid, "editor@uti.edu.ec", "editor")
    assert generar(editor, aid).status_code == 202
    contenido = deepcopy(recurso["contenido"])
    contenido[0]["contexto"] += " La empresa utiliza mediciones ficticias adicionales."
    r = guardar(editor, aid, recurso, contenido)
    assert r.status_code == 200, r.text
    actual = r.json()
    assert actual["revision"] == 1 and actual["contenido"] == contenido
    assert actual["estado"] == "requiere_revision" and actual["evidencia_vigente"] is False
    assert actual["evidencia"] == recurso["evidencia"]
    historial = conn.execute("select * from recurso_edicion").fetchall()
    assert len(historial) == 1 and historial[0]["usuario"] == "editor@uti.edu.ec"
    assert historial[0]["contenido_anterior"] == recurso["contenido"]
    assert historial[0]["contenido_nuevo"] == contenido and historial[0]["uso_mejora"] is False


def test_revision_obsoleta_no_pisa_otra_edicion(entorno, conn):
    _, _, d, aid, producir = entorno
    recurso = producir()
    contenido = deepcopy(recurso["contenido"])
    contenido[0]["contexto"] += " Caso de práctica adaptado por el docente."
    assert guardar(d, aid, recurso, contenido).status_code == 200
    assert guardar(d, aid, recurso).status_code == 409
    assert conn.execute("select count(*) n from recurso_edicion").fetchone()["n"] == 1


def test_guardar_sin_cambios_no_invalida_evidencia(entorno, conn):
    _, _, d, aid, producir = entorno
    recurso = producir()
    r = guardar(d, aid, recurso)
    assert r.status_code == 200 and r.json()["revision"] == 0
    assert r.json()["estado"] == recurso["estado"] and r.json()["evidencia_vigente"] is True
    assert conn.execute("select count(*) n from recurso_edicion").fetchone()["n"] == 0


def test_no_se_pueden_alterar_estado_evidencia_ni_ids_del_recurso(entorno):
    _, _, d, aid, producir = entorno
    recurso = producir()
    assert guardar(d, aid, recurso, estado="listo").status_code == 422
    assert guardar(d, aid, recurso, evidencia={"borrador": False}).status_code == 422
    contenido = deepcopy(recurso["contenido"])
    contenido[0]["item_id"] = "item-de-otra-asignatura"
    assert guardar(d, aid, recurso, contenido).status_code == 422


def test_uuid_recurso_ajeno_no_elude_asignatura(entorno, silabo):
    app, cliente, _, aid, producir = entorno
    recurso = producir()
    otro = cliente("otro@uti.edu.ec")
    bid = app.state.asignaturas.guardar("otro@uti.edu.ec", silabo)["id"]
    assert otro.get(f"/asignaturas/{aid}/recursos/{recurso['id']}").status_code == 403
    assert otro.get(f"/asignaturas/{bid}/recursos/{recurso['id']}").status_code == 404
    assert guardar(otro, bid, recurso).status_code == 404
    assert otro.get(f"/asignaturas/{bid}/trabajos").json() == []
    assert otro.get(f"/asignaturas/{bid}/recursos").json() == []


def test_dos_asignaturas_con_recursos_no_mezclan_listados(entorno, silabo, conn):
    app, cliente, d, aid, producir = entorno
    primero = producir()
    otro = cliente("otro@uti.edu.ec")
    bid = app.state.asignaturas.guardar("otro@uti.edu.ec", silabo)["id"]
    assert generar(otro, bid).status_code == 202
    assert procesar_uno(conn, cliente_revisor(), app.state.perfiles, "api-prueba", 360)
    propios = d.get(f"/asignaturas/{aid}/recursos").json()
    ajenos = otro.get(f"/asignaturas/{bid}/recursos").json()
    assert [r["id"] for r in propios] == [primero["id"]]
    assert len(ajenos) == 1 and ajenos[0]["id"] != primero["id"]
    assert {t["id"] for t in d.get(f"/asignaturas/{aid}/trabajos").json()}.isdisjoint(
        {t["id"] for t in otro.get(f"/asignaturas/{bid}/trabajos").json()})
    assert d.get(f"/asignaturas/{aid}/recursos/{ajenos[0]['id']}").status_code == 404


def test_recurso_ausente_y_uuid_invalido(entorno):
    _, _, d, aid, _ = entorno
    assert d.get(f"/asignaturas/{aid}/recursos/{uuid4()}").status_code == 404
    assert d.get(f"/asignaturas/{aid}/recursos/no-uuid").status_code == 422


def test_ficha_se_puede_editar_sin_convertirla_en_cuestionario(entorno):
    _, _, d, aid, producir = entorno
    recurso = producir("ficha_clase")
    contenido = deepcopy(recurso["contenido"])
    contenido["conceptual"]["ideas_clave"][0] = "Idea ajustada por el docente"
    assert guardar(d, aid, recurso, contenido).status_code == 200
    assert guardar(d, aid, recurso, []).status_code == 409


def test_editar_usa_snapshot_aunque_silabo_actual_cambie(entorno, silabo):
    app, _, d, aid, producir = entorno
    recurso = producir()
    m = silabo.momentos[0]
    s = m.sesiones[0].model_copy(update={"contenidos": ["Contenido completamente nuevo"]})
    nuevo = silabo.model_copy(update={"momentos": [m.model_copy(update={"sesiones": [s, *m.sesiones[1:]]}), *silabo.momentos[1:]]})
    app.state.asignaturas.guardar("dueno@uti.edu.ec", nuevo)
    r = d.get(f"/asignaturas/{aid}/recursos/{recurso['id']}")
    assert r.json()["silabo_actualizado"] is True
    assert guardar(d, aid, recurso).status_code == 200


def test_retirada_de_editor_impide_generar_y_editar(entorno):
    _, cliente, d, aid, producir = entorno
    recurso = producir()
    editor = cliente("editor@uti.edu.ec")
    compartir(d, aid, "editor@uti.edu.ec", "editor")
    assert d.delete(f"/asignaturas/{aid}/compartir/editor@uti.edu.ec", headers=HEADERS).status_code == 204
    assert generar(editor, aid).status_code == 403
    assert guardar(editor, aid, recurso).status_code == 403


def test_ediciones_concurrentes_no_se_sobrescriben(entorno, nueva_conexion, conn):
    app, _, _, aid, producir = entorno
    recurso = producir()
    servicio = app.state.recursos
    original = servicio.conexion
    pids, listos = [], threading.Event()

    def conexion():
        c = nueva_conexion()
        pids.append(c.info.backend_pid)
        if len(pids) == 2:
            listos.set()
        return c

    def editar(n):
        contenido = deepcopy(recurso["contenido"])
        contenido[0]["contexto"] += f" Caso ficticio adicional {n}."
        try:
            servicio.editar(aid, recurso["id"], "dueno@uti.edu.ec", 0, contenido)
            return 200
        except HTTPException as exc:
            return exc.status_code

    servicio.conexion = conexion
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            with conn.transaction():
                conn.execute("select id from recurso where id=%s for update", (recurso["id"],))
                futuros = [pool.submit(editar, n) for n in range(2)]
                assert listos.wait(timeout=2)
                esperar_locks(conn, pids, 2)
            assert sorted(f.result(timeout=5) for f in futuros) == [200, 409]
    finally:
        servicio.conexion = original
    assert conn.execute("select count(*) n from recurso_edicion").fetchone()["n"] == 1


def test_json_excesivo_se_rechaza_antes_de_validar_o_editar(entorno, conn):
    app, _, d, aid, producir = entorno
    recurso = producir()
    # La configuración del middleware se fija al construir la app, por eso usamos 1MB.
    r = d.put(f"/asignaturas/{aid}/recursos/{recurso['id']}", content=b"x" * (1024 * 1024 + 1),
              headers={**HEADERS, "Content-Type": "application/json"})
    assert r.status_code == 413
    assert conn.execute("select count(*) n from recurso_edicion").fetchone()["n"] == 0


@pytest.mark.parametrize("ruta", ["trabajos", "recursos"])
def test_listados_acotan_paginacion(entorno, ruta):
    _, _, d, aid, _ = entorno
    assert d.get(f"/asignaturas/{aid}/{ruta}?limite=201").status_code == 422
    assert d.get(f"/asignaturas/{aid}/{ruta}?desde=-1").status_code == 422


def test_no_se_edita_recurso_sin_snapshot_original(entorno, conn):
    _, _, d, aid, producir = entorno
    recurso = producir()
    conn.execute("update trabajo set parametros=parametros-'silabo' where id=%s", (recurso["trabajo_id"],))
    assert guardar(d, aid, recurso).status_code == 409


def test_clase_sin_contenidos_genera_y_permite_edicion(entorno, silabo, monkeypatch):
    app, _, d, aid, producir = entorno
    m = silabo.momentos[0]
    sesion = m.sesiones[0].model_copy(update={"contenidos": []})
    vacio = silabo.model_copy(update={"momentos": [m.model_copy(update={"sesiones": [sesion, *m.sesiones[1:]]}), *silabo.momentos[1:]]})
    app.state.asignaturas.guardar("dueno@uti.edu.ec", vacio)

    class ConAlternativa(WorkerPrueba):
        def generar(self, tarea, cliente):
            contexto = tarea.contexto.model_copy(update={"contenidos": [tarea.contexto.momento_titulo]})
            return super().generar(tarea.model_copy(update={"contexto": contexto}), cliente)

    monkeypatch.setitem(WORKERS, "cuestionario", ConAlternativa())
    recurso = producir()
    contenido = deepcopy(recurso["contenido"])
    contenido[0]["contexto"] += " El docente precisa el caso con datos ficticios."
    r = guardar(d, aid, recurso, contenido)
    assert r.status_code == 200 and r.json()["estado"] == "requiere_revision"


def test_polling_estado_del_trabajo_y_recurso_editado(entorno, conn):
    _, _, d, aid, producir = entorno
    recurso = producir()
    contenido = deepcopy(recurso["contenido"])
    contenido[0]["contexto"] += " Contexto de práctica adaptado."
    assert guardar(d, aid, recurso, contenido).status_code == 200
    trabajos = d.get(f"/asignaturas/{aid}/trabajos").json()
    trabajo = next(t for t in trabajos if t["id"] == recurso["trabajo_id"])
    assert trabajo["estado"] == "listo"
    assert trabajo["recurso_id"] == recurso["id"]
    assert trabajo["recurso_estado"] == "requiere_revision" and trabajo["recurso_revision"] == 1
    for estado in ("en_cola", "generando", "verificando", "revisando", "listo", "requiere_revision", "error", "en_espera"):
        conn.execute("update trabajo set estado=%s,error='detalle privado' where id=%s", (estado, recurso["trabajo_id"]))
        filas = d.get(f"/asignaturas/{aid}/trabajos").json()
        assert filas[0]["estado"] == estado and "detalle privado" not in str(filas)


def test_ejecucion_posterior_a_cambio_respeta_snapshot_y_perfil(entorno, silabo, conn):
    app, _, d, aid, _ = entorno
    r = generar(d, aid, perfil_dificultad="avanzado")
    assert r.status_code == 202
    m = silabo.momentos[0]
    sesion = m.sesiones[0].model_copy(update={"contenidos": ["Contenido de otra versión"]})
    nuevo = silabo.model_copy(update={"momentos": [m.model_copy(update={"sesiones": [sesion, *m.sesiones[1:]]}), *silabo.momentos[1:]]})
    app.state.asignaturas.guardar("dueno@uti.edu.ec", nuevo)
    assert procesar_uno(conn, cliente_revisor(), app.state.perfiles, "api-prueba", 360)
    rid = d.get(f"/asignaturas/{aid}/recursos").json()[0]["id"]
    recurso = d.get(f"/asignaturas/{aid}/recursos/{rid}").json()
    assert recurso["evidencia"]["perfil_dificultad"] == "avanzado"
    assert recurso["evidencia"]["contenidos"] == m.sesiones[0].contenidos
    assert recurso["silabo_actualizado"] is True
