"""A3: acceso real por docente y subida binaria de PDF sin correos reales."""
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.api.aplicacion import crear_app
from app.auth.servicio import ServicioAuth
from app.config import Ajustes
from app.silabo.lector import SilaboIlegible
from app.asignaturas.servicio import exigir_acceso

ORIGEN = "https://materiales.example"


@pytest.fixture
def entorno(nueva_conexion, silabo):
    codigos, rutas = {}, []
    auth = ServicioAuth(nueva_conexion, "s" * 48, lambda c, k: codigos.update({c: k}))

    def lector(ruta, **_):
        rutas.append(Path(ruta))
        assert Path(ruta).read_bytes().startswith(b"%PDF-")
        return silabo

    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                     llm_model="m", api_origen=ORIGEN, pdf_max_bytes=128, auth_secreto="s" * 48)
    app = crear_app(config, auth=auth, conexion=nueva_conexion, lector_pdf=lector)

    def cliente(correo):
        c = TestClient(app, base_url=ORIGEN)
        auth.pedir(correo)
        token = auth.verificar(correo, codigos[correo])
        c.cookies.set("sesion", token)
        return c

    return app, cliente, rutas


def subir(c):
    return c.post("/silabos", content=b"%PDF-datos-de-prueba",
                  headers={"Content-Type": "application/pdf", "Origin": ORIGEN})


def compartir(c, aid, correo, rol="lector"):
    return c.post(f"/asignaturas/{aid}/compartir", json={"correo": correo, "rol": rol},
                  headers={"Origin": ORIGEN})


def test_subir_devuelve_agente_y_menu_y_elimina_pdf(entorno, conn):
    app, cliente, rutas = entorno
    with cliente("dueno@uti.edu.ec") as c:
        r = subir(c)
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["agente"] == "ingenierias" and d["menu"]
        assert c.get(f"/asignaturas/{d['id']}/menu").json()["menu"] == d["menu"]
        listado = c.get("/asignaturas").json()
        assert len(listado) == 1 and listado[0]["rol"] == "dueno"
    assert rutas and all(not r.exists() for r in rutas)
    assert conn.execute("select count(*) n from asignatura").fetchone()["n"] == 1


def test_no_hay_acceso_cruzado_entre_duenos(entorno):
    _, cliente, _ = entorno
    with cliente("uno@uti.edu.ec") as uno, cliente("dos@uti.edu.ec") as dos:
        a, b = subir(uno).json()["id"], subir(dos).json()["id"]
        assert a != b
        assert [x["id"] for x in uno.get("/asignaturas").json()] == [a]
        assert [x["id"] for x in dos.get("/asignaturas").json()] == [b]
        assert uno.get(f"/asignaturas/{b}/menu").status_code == 403
        assert dos.get(f"/asignaturas/{a}/menu").status_code == 403


def test_compartir_lector_editor_y_retirar(entorno):
    _, cliente, _ = entorno
    with cliente("dueno@uti.edu.ec") as d, cliente("lector@uti.edu.ec") as l, cliente("editor@uti.edu.ec") as e:
        aid = subir(d).json()["id"]
        assert compartir(d, aid, "lector@uti.edu.ec").status_code == 200
        assert compartir(d, aid, "editor@uti.edu.ec", "editor").status_code == 200
        assert l.get(f"/asignaturas/{aid}/menu").status_code == 200
        assert e.get(f"/asignaturas/{aid}/menu").status_code == 200
        assert l.get("/asignaturas").json()[0]["rol"] == "lector"
        assert e.get("/asignaturas").json()[0]["rol"] == "editor"
        assert compartir(l, aid, "tercero@uti.edu.ec").status_code == 403
        assert compartir(e, aid, "tercero@uti.edu.ec").status_code == 403
        r = l.delete(f"/asignaturas/{aid}/compartir/editor@uti.edu.ec", headers={"Origin": ORIGEN})
        assert r.status_code == 403
        assert d.delete(f"/asignaturas/{aid}/compartir/lector@uti.edu.ec", headers={"Origin": ORIGEN}).status_code == 204
        assert l.get(f"/asignaturas/{aid}/menu").status_code == 403
        assert l.get("/asignaturas").json() == []
        assert e.get(f"/asignaturas/{aid}/menu").status_code == 200


@pytest.mark.parametrize("correo,rol,codigo", [("a@gmail.com", "lector", 403),
    ("a@uti.edu.ec", "dueno", 422), ("dueno@uti.edu.ec", "lector", 422)])
def test_compartir_valida_correo_rol_y_no_degrada_dueno(entorno, correo, rol, codigo):
    _, cliente, _ = entorno
    with cliente("dueno@uti.edu.ec") as d:
        aid = subir(d).json()["id"]
        assert compartir(d, aid, correo, rol).status_code == codigo
        assert d.get("/asignaturas").json()[0]["rol"] == "dueno"


def test_asignatura_inexistente_o_uuid_invalido(entorno):
    _, cliente, _ = entorno
    with cliente("dueno@uti.edu.ec") as d:
        assert d.get(f"/asignaturas/{uuid4()}/menu").status_code == 404
        assert d.get("/asignaturas/no-uuid/menu").status_code == 422


def test_reemplazo_silabo_mismo_dueno_conserva_id_y_compartidos(entorno, silabo):
    app, cliente, rutas = entorno
    with cliente("dueno@uti.edu.ec") as d:
        aid = subir(d).json()["id"]
        compartir(d, aid, "lector@uti.edu.ec")
        r = subir(d)
        assert r.json()["id"] == aid and r.json()["clases_cambiadas"] == []
        nuevo = silabo.model_copy(update={"proyecto_formativo": silabo.proyecto_formativo.model_copy(update={"version": "nueva"})})
        app.state.lector_pdf = lambda *_, **__: nuevo
        r = subir(d)
        assert r.json()["id"] == aid and r.json()["clases_cambiadas"] == []
        with cliente("lector@uti.edu.ec") as l:
            assert l.get(f"/asignaturas/{aid}/menu").status_code == 200
    assert all(not p.exists() for p in rutas)


def test_pdf_ilegible_limpia_temporal_y_no_filtra_texto(entorno, conn):
    app, cliente, _ = entorno
    rutas = []

    def falla(ruta, **_):
        rutas.append(Path(ruta))
        raise SilaboIlegible("texto privado del PDF")

    app.state.lector_pdf = falla
    with cliente("dueno@uti.edu.ec") as d:
        r = subir(d)
    assert r.status_code == 422 and "texto privado" not in r.text
    assert rutas and all(not p.exists() for p in rutas)
    assert conn.execute("select count(*) n from asignatura").fetchone()["n"] == 0


@pytest.mark.parametrize("tipo,contenido,codigo", [("text/plain", b"%PDF-a", 415),
    ("application/pdf", b"no es pdf", 415), ("application/pdf", b"", 422),
    ("application/pdf", b"%PDF-" + b"x" * 129, 413)])
def test_rechaza_entrada_antes_del_lector(entorno, tipo, contenido, codigo):
    _, cliente, rutas = entorno
    with cliente("dueno@uti.edu.ec") as d:
        r = d.post("/silabos", content=contenido, headers={"Content-Type": tipo, "Origin": ORIGEN})
    assert r.status_code == codigo and rutas == []


def test_pdf_tamano_sin_content_length(entorno):
    _, cliente, rutas = entorno
    with cliente("dueno@uti.edu.ec") as d:
        r = d.post("/silabos", content=iter([b"%PDF-", b"x" * 129]),
                   headers={"Content-Type": "application/pdf", "Origin": ORIGEN})
    assert r.status_code == 413 and rutas == []


def test_no_procesa_pdf_sin_sesion(entorno):
    app, _, rutas = entorno
    with TestClient(app) as web:
        assert subir(web).status_code == 401
    assert rutas == []


def test_tamano_real_no_confia_en_content_length(entorno):
    _, cliente, rutas = entorno
    with cliente("dueno@uti.edu.ec") as d:
        r = d.post("/silabos", content=b"%PDF-" + b"x" * 129,
                   headers={"Content-Type": "application/pdf", "Origin": ORIGEN, "Content-Length": "1"})
    assert r.status_code == 413 and rutas == []


def test_lector_ocupado_rechaza_sin_crear_pdf(entorno):
    app, cliente, rutas = entorno
    with cliente("dueno@uti.edu.ec") as d:
        assert app.state.pdf_cupos.acquire(blocking=False)
        assert app.state.pdf_cupos.acquire(blocking=False)
        try:
            assert subir(d).status_code == 503
            assert rutas == []
        finally:
            app.state.pdf_cupos.release()
            app.state.pdf_cupos.release()
        assert subir(d).status_code == 201


def test_guardia_de_escritura_deniega_lector_y_permiso_retirado(entorno, conn):
    _, cliente, _ = entorno
    with cliente("dueno@uti.edu.ec") as d:
        aid = subir(d).json()["id"]
        compartir(d, aid, "editor@uti.edu.ec", "editor")
        compartir(d, aid, "lector@uti.edu.ec", "lector")
        with conn.transaction():
            assert exigir_acceso(conn, aid, "dueno@uti.edu.ec", editar=True)[1] == "dueno"
            assert exigir_acceso(conn, aid, "editor@uti.edu.ec", editar=True)[1] == "editor"
        for correo in ("lector@uti.edu.ec", "otro@uti.edu.ec"):
            with pytest.raises(HTTPException) as exc, conn.transaction():
                exigir_acceso(conn, aid, correo, editar=True)
            assert exc.value.status_code == 403
        compartir(d, aid, "editor@uti.edu.ec", "lector")
        with pytest.raises(HTTPException) as exc, conn.transaction():
            exigir_acceso(conn, aid, "editor@uti.edu.ec", editar=True)
        assert exc.value.status_code == 403


def test_nueva_version_devuelve_solo_clases_afectadas(entorno, silabo):
    app, cliente, _ = entorno
    with cliente("dueno@uti.edu.ec") as d:
        aid = subir(d).json()["id"]
        momento = silabo.momentos[0]
        sesion = momento.sesiones[0]
        nueva_sesion = sesion.model_copy(update={"contenidos": [*sesion.contenidos, "Contenido adicional"]})
        nuevo_momento = momento.model_copy(update={"sesiones": [nueva_sesion, *momento.sesiones[1:]]})
        nuevo = silabo.model_copy(update={"momentos": [nuevo_momento, *silabo.momentos[1:]]})
        app.state.lector_pdf = lambda *_, **__: nuevo
        r = subir(d)
        assert r.status_code == 201 and r.json()["id"] == aid
        assert r.json()["clases_cambiadas"] == [sesion.id]


@pytest.mark.parametrize("relativa,semanas,sesiones", [
    ("Software/AnalisisDatos-Ingenieria/silabo_Datos_Software-signed.pdf", 6, 11),
    ("Software/TIC-Ingenieria/TIC-Ingenieria.pdf", 4, 6)], ids=["datos", "tic"])
def test_upload_real_aislado_sin_ia(entorno, relativa, semanas, sesiones):
    from app.silabo.aislado import leer_pdf_aislado
    ruta = Path(__file__).resolve().parents[2] / "Silabos" / relativa
    if not ruta.exists():
        pytest.skip("PDF institucional no disponible localmente")
    app, cliente, _ = entorno
    app.state.lector_pdf = leer_pdf_aislado
    app.state.config = app.state.config.model_copy(update={"pdf_max_bytes": 10 * 1024 * 1024})
    with cliente("dueno@uti.edu.ec") as d:
        with ruta.open("rb") as pdf:
            r = d.post("/silabos", content=pdf,
                       headers={"Content-Type": "application/pdf", "Origin": ORIGEN})
        assert r.status_code == 201
        menu = r.json()["menu"]
        assert len(menu) == semanas and sum(len(s["clases"]) for s in menu) == sesiones
