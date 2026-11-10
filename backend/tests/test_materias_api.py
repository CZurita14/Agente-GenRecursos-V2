"""V2: las materias del docente salen del SGA; ya no se sube ningún PDF."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.aplicacion import crear_app
from app.auth.servicio import ServicioAuth
from app.config import Ajustes
from app.sga.simulado import ProveedorSimulado
from app.sga.sincronizar import sincronizar
from tests.test_sga_sincronizar import CLAVE, Envoltorio

ORIGEN = "https://materiales.example"
SGA = Path(__file__).parent / "fixtures" / "sga"
CORREO = "docente.uno@uti.edu.ec"
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


def _sincronizar(conn, app, proveedor):
    identidad, permiso = proveedor.autenticar("docente.uno", CLAVE)
    return sincronizar(conn, proveedor, identidad, permiso, app.state.asignaturas)


def test_materias_devuelve_las_del_sga_del_docente_ordenadas(entorno, conn):
    app, cliente = entorno
    esperado = json.loads((SGA / "materias" / "docente.uno.json").read_text(encoding="utf-8"))
    with cliente(CORREO) as c:
        _sincronizar(conn, app, ProveedorSimulado(SGA))
        _materia(conn, "otro@uti.edu.ec", "x9", "PF-Z", "A", "Ajena")  # prueba el filtro por docente
        r = c.get("/materias")
    assert r.status_code == 200
    filas = r.json()
    assert all(set(f) == CLAVES for f in filas)
    assert [(f["id_sga"], f["codigo_pf"], f["paralelo"], f["nombre"], f["carrera"]) for f in filas] == [
        (m["id_sga"], m["codigo_pf"], m["paralelo"], m["nombre"], m["carrera"])
        for m in sorted(esperado, key=lambda m: (m["codigo_pf"], m["paralelo"]))]
    assert all(f["estado"] in ("importada", "sin_cambios") and f["asignatura_id"] for f in filas)
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


def test_asignatura_de_una_materia_que_el_sga_ya_no_lista_es_inexistente(entorno, conn):
    app, cliente = entorno
    with cliente(CORREO) as c:
        _sincronizar(conn, app, ProveedorSimulado(SGA))
        aid = next(f["asignatura_id"] for f in c.get("/materias").json() if f["id_sga"] == "90003")
        assert c.get(f"/asignaturas/{aid}/menu").status_code == 200
        _sincronizar(conn, app, Envoltorio(ProveedorSimulado(SGA), quita={"90003"}))
        assert c.get(f"/asignaturas/{aid}/menu").status_code == 404
        assert aid not in [a["id"] for a in c.get("/asignaturas").json()]
        assert "90003" not in [f["id_sga"] for f in c.get("/materias").json()]
