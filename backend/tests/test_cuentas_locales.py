"""Cuentas locales de la etapa de pruebas: alta por el administrador, ingreso sin el SGA y PDF del sílabo."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agentes.facultades import cargar_catalogo, cargar_perfiles
from app.api.aplicacion import crear_app
from app.asignaturas import pdf
from app.asignaturas.servicio import ServicioAsignaturas
from app.auth.servicio import ServicioAuth
from app.config import RAIZ, Ajustes
from app.sga.simulado import ProveedorSimulado

SGA = Path(__file__).parent / "fixtures" / "sga"
ADMIN = "admin@uti.edu.ec"
DOCENTE = "piloto@indoamerica.edu.ec"
CLAVE, NUEVA = "clave-inicial-1", "clave-nueva-2026"
ORIGEN = {"Origin": "http://localhost:5173"}
SILABO = SGA / "sga_silabos" / "S91-SIMU-3-90001-9001.json"


def _config(**extra):
    base = dict(_env_file=None, database_url="postgresql://no-usar", llm_base_url="http://m/v1", llm_model="m",
                api_origen="http://localhost:5173", entorno="desarrollo", auth_secreto="s" * 48,
                administradores=[ADMIN])
    return Ajustes(**{**base, **extra})


@pytest.fixture
def cliente(nueva_conexion):
    def _crear(**extra):
        config = _config(**extra)
        asignaturas = ServicioAsignaturas(nueva_conexion, cargar_catalogo(RAIZ / "kb/catalogo.yaml"),
                                          cargar_perfiles(RAIZ / "agentes"))
        auth = ServicioAuth(nueva_conexion, "s" * 48, ProveedorSimulado(SGA), asignaturas,
                            cuentas_locales=config.cuentas_locales)
        return TestClient(crear_app(config, auth=auth, conexion=nueva_conexion), base_url="https://testserver")
    return _crear


def _como(c, correo):
    c.cookies.clear()
    c.cookies.set("sesion", c.app.state.auth.sesion_directa(correo))


def _ingresar(c, usuario, clave):
    c.cookies.clear()
    return c.post("/auth/ingresar", json={"usuario": usuario, "clave": clave}, headers=ORIGEN)


def test_prohibido_en_produccion():
    with pytest.raises(ValueError, match="CUENTAS_LOCALES"):
        Ajustes(_env_file=None, database_url="postgresql://no-usar", llm_base_url="http://m/v1", llm_model="m",
                api_origen="https://materiales.example", entorno="produccion", cuentas_locales=True)


def test_apagado_las_rutas_no_existen(cliente):
    with cliente() as c:
        assert c.get("/auth/modo").json()["cuentas_locales"] is False
        _como(c, ADMIN)
        assert c.get("/admin/cuentas").status_code == 404
        r = c.post("/admin/cuentas", json={"correo": DOCENTE, "clave": CLAVE}, headers=ORIGEN)
        assert r.status_code == 404


def test_solo_administradores(cliente):
    with cliente(cuentas_locales=True) as c:
        _como(c, "otro@uti.edu.ec")
        assert c.get("/admin/cuentas").status_code == 403
        assert c.post("/admin/cuentas", json={"correo": DOCENTE, "clave": CLAVE}, headers=ORIGEN).status_code == 403


@pytest.mark.parametrize("correo", ["svelez@andalucia.fin.ec", "a@gmail.com", "a@uti.edu.ec.otro.com",
                                    "a@mail.indoamerica.edu.ec", "Nombre <a@uti.edu.ec>"])
def test_solo_correos_institucionales(cliente, correo):
    with cliente(cuentas_locales=True) as c:
        _como(c, ADMIN)
        r = c.post("/admin/cuentas", json={"correo": correo, "clave": CLAVE}, headers=ORIGEN)
        assert r.status_code == 422 and "@indoamerica.edu.ec" in r.json()["detail"]


def test_alta_ingreso_y_cambio_de_clave(cliente, conn):
    with cliente(cuentas_locales=True) as c:
        _como(c, ADMIN)
        r = c.post("/admin/cuentas", json={"correo": " Piloto@IndoAmerica.edu.ec ", "nombre": "Docente Piloto",
                                           "clave": CLAVE}, headers=ORIGEN)
        assert r.status_code == 201 and r.json() == {"correo": DOCENTE}
        assert c.post("/admin/cuentas", json={"correo": DOCENTE, "clave": CLAVE}, headers=ORIGEN).status_code == 422
        assert c.post("/admin/cuentas", json={"correo": "x@uti.edu.ec", "clave": "corta"},
                      headers=ORIGEN).status_code == 422
        fila = conn.execute("select clave_hash from cuenta_local where correo=%s", (DOCENTE,)).fetchone()
        assert CLAVE not in fila["clave_hash"] and fila["clave_hash"].startswith("pbkdf2_sha256$")
        [cuenta] = c.get("/admin/cuentas").json()
        assert cuenta["correo"] == DOCENTE and cuenta["cambiar_clave"] and cuenta["activa"]

        assert _ingresar(c, DOCENTE, "clave-errada-99").status_code == 401
        r = _ingresar(c, DOCENTE, CLAVE)
        assert r.status_code == 200 and r.json() == {"correo": DOCENTE, "materias": []}
        yo = c.get("/auth/yo").json()
        assert yo["cuenta_local"] and yo["cambiar_clave"] and yo["rol"] == "docente"

        assert c.post("/auth/clave", json={"actual": "otra-clave-1", "nueva": NUEVA}, headers=ORIGEN).status_code == 422
        assert c.post("/auth/clave", json={"actual": CLAVE, "nueva": CLAVE}, headers=ORIGEN).status_code == 422
        assert c.post("/auth/clave", json={"actual": CLAVE, "nueva": NUEVA}, headers=ORIGEN).status_code == 204
        assert c.get("/auth/yo").json()["cambiar_clave"] is False
        assert _ingresar(c, DOCENTE, CLAVE).status_code == 401
        assert _ingresar(c, DOCENTE, NUEVA).status_code == 200
        assert conn.execute("select nombre from docente where correo=%s", (DOCENTE,)).fetchone()["nombre"] == "Docente Piloto"


def test_restablecer_y_desactivar_cierran_sesiones(cliente):
    with cliente(cuentas_locales=True) as c:
        _como(c, ADMIN)
        c.post("/admin/cuentas", json={"correo": DOCENTE, "clave": CLAVE}, headers=ORIGEN)
        docente = c.app.state.auth.ingresar(DOCENTE, CLAVE)
        assert c.post(f"/admin/cuentas/{DOCENTE}/clave", json={"clave": NUEVA}, headers=ORIGEN).status_code == 204
        assert c.app.state.auth.identificar(docente) is None
        assert _ingresar(c, DOCENTE, NUEVA).status_code == 200
        assert c.get("/auth/yo").json()["cambiar_clave"] is True

        _como(c, ADMIN)
        docente = c.app.state.auth.ingresar(DOCENTE, NUEVA)
        assert c.post(f"/admin/cuentas/{DOCENTE}/estado", json={"activa": False}, headers=ORIGEN).status_code == 204
        assert c.app.state.auth.identificar(docente) is None
        assert _ingresar(c, DOCENTE, NUEVA).status_code == 401  # Igual que una clave errada.
        _como(c, ADMIN)
        assert c.post("/admin/cuentas/nadie@uti.edu.ec/estado", json={"activa": True}, headers=ORIGEN).status_code == 404


def test_bloqueo_tras_cinco_intentos(cliente):
    with cliente(cuentas_locales=True) as c:
        _como(c, ADMIN)
        c.post("/admin/cuentas", json={"correo": DOCENTE, "clave": CLAVE}, headers=ORIGEN)
        codigos = [_ingresar(c, DOCENTE, f"errada-{k}-xxxx").status_code for k in range(5)]
        assert codigos == [401, 401, 401, 401, 429]
        assert _ingresar(c, DOCENTE, CLAVE).status_code == 429


def test_cuenta_sga_no_cambia_con_el_modo(cliente):
    """Sin cuenta local, el ingreso sigue yendo al SGA y sincroniza sus materias."""
    with cliente(cuentas_locales=True) as c:
        r = _ingresar(c, "docente.uno", "clave-prueba-uno")
        assert r.status_code == 200 and r.json()["materias"]
        yo = c.get("/auth/yo").json()
        assert yo["cuenta_local"] is False and yo["cambiar_clave"] is False


def test_pdf_del_silabo(cliente, monkeypatch):
    silabo = json.loads(SILABO.read_text(encoding="utf-8"))
    leidos = []
    monkeypatch.setattr(pdf, "leer", lambda datos: leidos.append(datos) or silabo)
    with cliente(cuentas_locales=True) as c:
        _como(c, ADMIN)
        c.post("/admin/cuentas", json={"correo": DOCENTE, "clave": CLAVE}, headers=ORIGEN)
        _ingresar(c, DOCENTE, CLAVE)
        cabeceras = {**ORIGEN, "Content-Type": "application/pdf"}
        assert c.post("/silabos/pdf", content=b"{}", headers={**ORIGEN, "Content-Type": "application/json"}).status_code == 415
        r = c.post("/silabos/pdf", content=b"%PDF-1.7 prueba", headers=cabeceras)
        assert r.status_code == 200, r.text
        cuerpo = r.json()
        assert cuerpo["estado"] == "importada" and cuerpo["asignatura_id"] and leidos == [b"%PDF-1.7 prueba"]
        [materia] = c.get("/materias").json()
        assert materia["codigo_pf"] == cuerpo["codigo_pf"] and materia["asignatura_id"] == cuerpo["asignatura_id"]
        assert [a["id"] for a in c.get("/asignaturas").json()] == [cuerpo["asignatura_id"]]
        # Volver a subir el mismo sílabo no duplica la materia.
        assert c.post("/silabos/pdf", content=b"%PDF-1.7 prueba", headers=cabeceras).json()["estado"] == "sin_cambios"
        assert len(c.get("/materias").json()) == 1
        # Un ingreso posterior no sincroniza con el SGA: la materia sigue ahí.
        _ingresar(c, DOCENTE, CLAVE)
        assert len(c.get("/materias").json()) == 1


def test_pdf_rechazos(cliente, monkeypatch):
    with cliente(cuentas_locales=True) as c:
        _ingresar(c, "docente.uno", "clave-prueba-uno")
        cabeceras = {**ORIGEN, "Content-Type": "application/pdf"}
        assert c.post("/silabos/pdf", content=b"%PDF-1.7", headers=cabeceras).status_code == 403  # Cuenta del SGA.
        _como(c, ADMIN)
        c.post("/admin/cuentas", json={"correo": DOCENTE, "clave": CLAVE}, headers=ORIGEN)
        _ingresar(c, DOCENTE, CLAVE)
        r = c.post("/silabos/pdf", content=b"no es un pdf", headers=cabeceras)
        assert r.status_code == 422 and "PDF" in r.json()["detail"]
        monkeypatch.setattr(pdf, "leer", lambda datos: {"portada": {"pf_codigo": "x"}})
        r = c.post("/silabos/pdf", content=b"%PDF-1.7", headers=cabeceras)
        assert r.status_code == 422 and "código" in r.json()["detail"]
