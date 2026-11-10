"""V2: las materias del docente salen del SGA; ya no se sube ningún PDF."""
import pytest
from fastapi.testclient import TestClient

from app.api.aplicacion import crear_app
from app.auth.servicio import ServicioAuth
from app.config import Ajustes
from tests.silabos import subir

ORIGEN = "https://materiales.example"
CLAVES = {"id_sga", "codigo_pf", "paralelo", "nombre", "carrera", "estado_sga", "estado", "asignatura_id"}


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


def _materia(conn, correo, id_sga, codigo, paralelo, nombre, estado="importada", asignatura_id=None):
    conn.execute(
        "insert into materia_sga (correo,id_sga,codigo_pf,paralelo,nombre,carrera,estado_sga,estado,asignatura_id) "
        "values (%s,%s,%s,%s,%s,'Software','activa',%s,%s)",
        (correo, id_sga, codigo, paralelo, nombre, estado, asignatura_id))


def test_materias_devuelve_solo_las_del_docente_ordenadas(entorno, conn, datos):
    app, cliente = entorno
    with cliente("uno@uti.edu.ec") as c:
        aid = subir(app, "uno@uti.edu.ec", datos)["id"]
        _materia(conn, "uno@uti.edu.ec", "s2", "PF-B", "A", "Bases", asignatura_id=aid)
        _materia(conn, "uno@uti.edu.ec", "s3", "PF-A", "B", "Algebra", estado="no_disponible")
        _materia(conn, "uno@uti.edu.ec", "s1", "PF-A", "A", "Algebra", estado="invalida")
        _materia(conn, "dos@uti.edu.ec", "x9", "PF-Z", "A", "Ajena")
        r = c.get("/materias")
    assert r.status_code == 200
    filas = r.json()
    assert [(f["codigo_pf"], f["paralelo"]) for f in filas] == [("PF-A", "A"), ("PF-A", "B"), ("PF-B", "A")]
    assert all(set(f) == CLAVES for f in filas)
    assert [f["asignatura_id"] for f in filas] == [None, None, aid]
    assert "Ajena" not in r.text


def test_materias_sin_sesion_es_401(entorno):
    app, _ = entorno
    with TestClient(app, base_url=ORIGEN) as web:
        assert web.get("/materias").status_code == 401


def test_ya_no_se_puede_subir_un_pdf(entorno):
    _, cliente = entorno
    with cliente("uno@uti.edu.ec") as c:
        r = c.post("/silabos", content=b"%PDF-1.4", headers={"Content-Type": "application/pdf", "Origin": ORIGEN})
    assert r.status_code == 404


def test_asignatura_que_el_sga_ya_no_lista_es_inexistente(entorno, conn, datos):
    app, cliente = entorno
    with cliente("uno@uti.edu.ec") as c:
        aid = subir(app, "uno@uti.edu.ec", datos)["id"]
        conn.execute("update asignatura set activa_sga=false where id=%s", (aid,))
        assert c.get(f"/asignaturas/{aid}/menu").status_code == 404
