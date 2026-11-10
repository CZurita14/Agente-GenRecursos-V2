"""A3: acceso real por docente a las asignaturas que el SGA le entregó, sin correos reales."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.api.aplicacion import crear_app
from app.auth.servicio import ServicioAuth
from app.config import Ajustes
from app.asignaturas.servicio import exigir_acceso
from tests.acceso import dar_acceso, quitar_acceso
from tests.silabos import subir

ORIGEN = "https://materiales.example"


@pytest.fixture
def entorno(nueva_conexion):
    auth = ServicioAuth(nueva_conexion, "s" * 48)
    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                     llm_model="m", api_origen=ORIGEN, auth_secreto="s" * 48)
    app = crear_app(config, auth=auth, conexion=nueva_conexion)

    def cliente(correo):
        c = TestClient(app, base_url=ORIGEN)
        c.cookies.set("sesion", auth.sesion_directa(correo))
        return c

    return app, cliente


def test_guardar_devuelve_agente_y_menu(entorno, conn, datos):
    app, cliente = entorno
    with cliente("dueno@uti.edu.ec") as c:
        d = subir(app, "dueno@uti.edu.ec", datos)
        assert d["agente"] == "ingenierias" and d["menu"]
        assert c.get(f"/asignaturas/{d['id']}/menu").json()["menu"] == d["menu"]
        listado = c.get("/asignaturas").json()
        assert len(listado) == 1 and listado[0]["rol"] == "dueno"
    assert conn.execute("select count(*) n from asignatura").fetchone()["n"] == 1


def test_no_hay_acceso_cruzado_entre_duenos(entorno, datos):
    app, cliente = entorno
    with cliente("uno@uti.edu.ec") as uno, cliente("dos@uti.edu.ec") as dos:
        a, b = subir(app, "uno@uti.edu.ec", datos)["id"], subir(app, "dos@uti.edu.ec", datos)["id"]
        assert a != b
        assert [x["id"] for x in uno.get("/asignaturas").json()] == [a]
        assert [x["id"] for x in dos.get("/asignaturas").json()] == [b]
        assert uno.get(f"/asignaturas/{b}/menu").status_code == 403
        assert dos.get(f"/asignaturas/{a}/menu").status_code == 403


def test_lector_y_editor_ven_el_menu_con_su_rol(entorno, conn, datos):
    app, cliente = entorno
    with cliente("dueno@uti.edu.ec") as d, cliente("lector@uti.edu.ec") as l, cliente("editor@uti.edu.ec") as e:
        aid = subir(app, "dueno@uti.edu.ec", datos)["id"]
        dar_acceso(conn, aid, "lector@uti.edu.ec", "lector")
        dar_acceso(conn, aid, "editor@uti.edu.ec", "editor")
        assert l.get(f"/asignaturas/{aid}/menu").status_code == 200
        assert e.get(f"/asignaturas/{aid}/menu").status_code == 200
        assert l.get("/asignaturas").json()[0]["rol"] == "lector"
        assert e.get("/asignaturas").json()[0]["rol"] == "editor"
        quitar_acceso(conn, aid, "lector@uti.edu.ec")
        assert l.get(f"/asignaturas/{aid}/menu").status_code == 403
        assert l.get("/asignaturas").json() == []
        assert e.get(f"/asignaturas/{aid}/menu").status_code == 200


def test_ya_no_se_puede_compartir_por_la_api(entorno, datos):
    app, cliente = entorno
    with cliente("dueno@uti.edu.ec") as d:
        aid = subir(app, "dueno@uti.edu.ec", datos)["id"]
        r = d.post(f"/asignaturas/{aid}/compartir", json={"correo": "lector@uti.edu.ec", "rol": "lector"},
                   headers={"Origin": ORIGEN})
        assert r.status_code in (404, 405)


def test_asignatura_inactiva_en_el_sga_es_inexistente(entorno, conn, datos):
    app, cliente = entorno
    with cliente("dueno@uti.edu.ec") as d:
        aid = subir(app, "dueno@uti.edu.ec", datos)["id"]
        conn.execute("update asignatura set activa_sga=false where id=%s", (aid,))
        assert d.get(f"/asignaturas/{aid}/menu").status_code == 404
        assert d.get("/asignaturas").json() == []


def test_asignatura_inexistente_o_uuid_invalido(entorno):
    _, cliente = entorno
    with cliente("dueno@uti.edu.ec") as d:
        assert d.get(f"/asignaturas/{uuid4()}/menu").status_code == 404
        assert d.get("/asignaturas/no-uuid/menu").status_code == 422


def test_reemplazo_silabo_mismo_dueno_conserva_id_y_compartidos(entorno, datos, conn):
    app, cliente = entorno
    with cliente("dueno@uti.edu.ec") as d:
        aid = subir(app, "dueno@uti.edu.ec", datos)["id"]
        dar_acceso(conn, aid, "lector@uti.edu.ec", "lector")
        r = subir(app, "dueno@uti.edu.ec", datos)
        assert r["id"] == aid and r["clases_cambiadas"] == []
        datos["proyecto_formativo"]["version"] = "nueva"
        r = subir(app, "dueno@uti.edu.ec", datos)
        assert r["id"] == aid and r["clases_cambiadas"] == []
        with cliente("lector@uti.edu.ec") as l:
            assert l.get(f"/asignaturas/{aid}/menu").status_code == 200


def test_guardia_de_escritura_deniega_lector_y_permiso_retirado(entorno, conn, datos):
    app, cliente = entorno
    with cliente("dueno@uti.edu.ec") as d:
        aid = subir(app, "dueno@uti.edu.ec", datos)["id"]
        dar_acceso(conn, aid, "editor@uti.edu.ec", "editor")
        dar_acceso(conn, aid, "lector@uti.edu.ec", "lector")
        with conn.transaction():
            assert exigir_acceso(conn, aid, "dueno@uti.edu.ec", editar=True)[1] == "dueno"
            assert exigir_acceso(conn, aid, "editor@uti.edu.ec", editar=True)[1] == "editor"
        for correo in ("lector@uti.edu.ec", "otro@uti.edu.ec"):
            with pytest.raises(HTTPException) as exc, conn.transaction():
                exigir_acceso(conn, aid, correo, editar=True)
            assert exc.value.status_code == 403
        dar_acceso(conn, aid, "editor@uti.edu.ec", "lector")
        with pytest.raises(HTTPException) as exc, conn.transaction():
            exigir_acceso(conn, aid, "editor@uti.edu.ec", editar=True)
        assert exc.value.status_code == 403


def test_nueva_version_devuelve_solo_clases_afectadas(entorno, datos):
    app, cliente = entorno
    with cliente("dueno@uti.edu.ec") as d:
        aid = subir(app, "dueno@uti.edu.ec", datos)["id"]
        sesion = datos["momentos"][0]["sesiones"][0]
        sesion["contenidos"] = [*sesion["contenidos"], "Contenido adicional"]
        r = subir(app, "dueno@uti.edu.ec", datos)
        assert r["id"] == aid
        assert r["clases_cambiadas"] == [sesion["id"]]
