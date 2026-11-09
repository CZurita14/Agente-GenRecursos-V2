"""Sincronización de materias y sílabos con el SGA (Tarea 3)."""
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.agentes.facultades import cargar_catalogo, cargar_perfiles
from app.asignaturas.servicio import ServicioAsignaturas, exigir_acceso
from app.config import RAIZ
from app.sga import SGANoDisponible
from app.sga.simulado import ProveedorSimulado
from app.sga.sincronizar import sincronizar

SGA = Path(__file__).parent / "fixtures" / "sga"
CLAVE = "clave-prueba-uno"
CORREO = "docente.uno@uti.edu.ec"
PF_A, PF_B = "S91-SIMU-3-90001-9001", "S91-SIMU-3-90002-9002"


class Envoltorio:
    """Proveedor que delega en el simulado y permite alterar lo que entrega."""

    def __init__(self, base, falla_en=None, cambia=None, quita=()):
        self.base, self.falla_en, self.cambia, self.quita = base, falla_en, cambia, set(quita)
        self.llamadas = 0

    def autenticar(self, usuario, clave):
        return self.base.autenticar(usuario, clave)

    def listar_materias(self, permiso):
        return [m for m in self.base.listar_materias(permiso) if m.id_sga not in self.quita]

    def obtener_silabo(self, permiso, materia):
        self.llamadas += 1
        if self.falla_en == self.llamadas:
            raise SGANoDisponible("SGA caído")
        crudo = self.base.obtener_silabo(permiso, materia)
        return self.cambia(materia, crudo) if self.cambia else crudo


@pytest.fixture
def servicio(nueva_conexion):
    return ServicioAsignaturas(nueva_conexion, cargar_catalogo(RAIZ / "kb/catalogo.yaml"),
                               cargar_perfiles(RAIZ / "agentes"))


@pytest.fixture
def base():
    return ProveedorSimulado(SGA)


def sync(conn, servicio, proveedor, usuario="docente.uno", clave=CLAVE):
    ident, permiso = proveedor.autenticar(usuario, clave)
    return sincronizar(conn, proveedor, ident, permiso, servicio)


def filas(conn, correo=CORREO):
    return conn.execute("select * from materia_sga where correo=%s order by id_sga", (correo,)).fetchall()


def test_mismas_materias(conn, servicio, base):
    r = sync(conn, servicio, base)
    _, permiso = base.autenticar("docente.uno", CLAVE)
    esperado = {(m.codigo_pf, m.paralelo) for m in base.listar_materias(permiso)}
    assert {(f["codigo_pf"], f["paralelo"]) for f in filas(conn)} == esperado
    assert {(m.codigo_pf, m.paralelo) for m in r.materias} == esperado
    assert all(f["estado"] in ("importada", "sin_cambios") and f["asignatura_id"] for f in filas(conn))


def test_dos_paralelos(conn, servicio, base):
    sync(conn, servicio, base)
    n = conn.execute("select count(*) n from asignatura where dueno=%s and codigo_pf=%s", (CORREO, PF_A)).fetchone()["n"]
    assert n == 1
    mias = [f for f in filas(conn) if f["codigo_pf"] == PF_A]
    assert len(mias) == 2 and mias[0]["asignatura_id"] == mias[1]["asignatura_id"]
    assert {f["paralelo"] for f in mias} == {"1", "2"}
    assert conn.execute("select count(*) n from asignatura").fetchone()["n"] == 2


def test_segunda_vez_sin_cambios(conn, servicio, base):
    sync(conn, servicio, base)
    r = sync(conn, servicio, base)
    assert {m.estado for m in r.materias} == {"sin_cambios"}
    assert {f["estado"] for f in filas(conn)} == {"sin_cambios"}


def test_sga_cae_a_mitad(conn, servicio, base):
    sync(conn, servicio, base)
    antes = conn.execute("select id,version_silabo,silabo from asignatura where codigo_pf=%s", (PF_B,)).fetchone()
    r = sync(conn, servicio, Envoltorio(base, falla_en=3))
    por_id = {m.id_sga: m for m in r.materias}
    assert por_id["90003"].estado == "no_disponible"
    assert por_id["90001"].estado == por_id["90002"].estado == "sin_cambios"
    despues = conn.execute("select id,version_silabo,silabo from asignatura where codigo_pf=%s", (PF_B,)).fetchone()
    assert despues == antes
    f = next(f for f in filas(conn) if f["id_sga"] == "90003")
    assert f["estado"] == "no_disponible" and f["asignatura_id"] == antes["id"]


def test_sga_cae_en_la_primera_vez(conn, servicio, base):
    r = sync(conn, servicio, Envoltorio(base, falla_en=3))
    assert {m.id_sga: m.estado for m in r.materias} == {
        "90001": "importada", "90002": "sin_cambios", "90003": "no_disponible"}
    f = next(f for f in filas(conn) if f["id_sga"] == "90003")
    assert f["asignatura_id"] is None


def test_materia_retirada(conn, servicio, base):
    sync(conn, servicio, base)
    aid = conn.execute("select id from asignatura where codigo_pf=%s", (PF_B,)).fetchone()["id"]
    sync(conn, servicio, Envoltorio(base, quita={"90003"}))
    assert {f["id_sga"] for f in filas(conn)} == {"90001", "90002"}
    with pytest.raises(HTTPException) as exc, conn.transaction():
        exigir_acceso(conn, aid, CORREO)
    assert exc.value.status_code == 404
    assert [x["codigo_pf"] for x in servicio.listar(CORREO)] == [PF_A]
    # La asignatura (y con ella sus recursos) sigue en la base de datos.
    assert conn.execute("select count(*) n from asignatura where id=%s", (aid,)).fetchone()["n"] == 1
    # Si la materia vuelve, vuelve el acceso.
    sync(conn, servicio, base)
    with conn.transaction():
        assert exigir_acceso(conn, aid, CORREO)[1] == "dueno"
    assert sorted(x["codigo_pf"] for x in servicio.listar(CORREO)) == [PF_A, PF_B]


def test_silabo_invalido(conn, servicio, base):
    def rompe(materia, crudo):
        if materia.codigo_pf == PF_B:
            crudo = json.loads(json.dumps(crudo))
            crudo["proyecto_formativo"]["creditos"] = "VALOR-SECRETO-QUE-NO-DEBE-SALIR"
        return crudo

    r = sync(conn, servicio, Envoltorio(base, cambia=rompe))
    m = next(m for m in r.materias if m.codigo_pf == PF_B)
    assert m.estado == "invalida" and m.fallos
    f = next(f for f in filas(conn) if f["codigo_pf"] == PF_B)
    assert f["estado"] == "invalida" and f["fallos"] == m.fallos and f["asignatura_id"] is None
    assert "VALOR-SECRETO" not in json.dumps(f["fallos"], default=str)
    # Las demás materias no se afectan.
    assert {x.estado for x in r.materias if x.codigo_pf == PF_A} <= {"importada", "sin_cambios"}


def _id_sesion(fila):
    return fila["silabo"]["momentos"][0]["sesiones"][0]["id"]


def test_version_cambia(conn, servicio, base):
    sync(conn, servicio, base)
    antes = conn.execute("select id,version_silabo,silabo from asignatura where codigo_pf=%s", (PF_A,)).fetchone()

    def nueva(materia, crudo):
        if materia.codigo_pf == PF_A:
            crudo = json.loads(json.dumps(crudo))
            crudo["proyecto_formativo"]["version"] = "2.0"
            ses = crudo["momentos"][0]["sesiones"][0]
            ses["contenidos"] = [*ses["contenidos"], "Contenido adicional"]
        return crudo

    r = sync(conn, servicio, Envoltorio(base, cambia=nueva))
    m = next(m for m in r.materias if m.id_sga == "90001")
    assert m.estado == "importada" and m.clases_cambiadas == [_id_sesion(antes)]
    despues = conn.execute("select id,version_silabo from asignatura where codigo_pf=%s", (PF_A,)).fetchone()
    assert despues["id"] == antes["id"] and despues["version_silabo"] == "2.0"
    # El paralelo 2 ya encuentra la versión nueva.
    assert next(x for x in r.materias if x.id_sga == "90002").estado == "sin_cambios"


def test_docentes_aislados(conn, servicio, base):
    sync(conn, servicio, base)
    sync(conn, servicio, base, "docente.dos", "clave-prueba-dos")
    assert len(filas(conn, "docente.dos@uti.edu.ec")) == 1
    assert len(filas(conn)) == 3
    assert [x["codigo_pf"] for x in servicio.listar("docente.dos@uti.edu.ec")] == ["S91-SIMU-2-90003-9003"]


def test_lista_vacia_quita_todo_y_sga_caido_no_toca_nada(conn, servicio, base):
    sync(conn, servicio, base)

    class Caido(Envoltorio):
        def listar_materias(self, permiso):
            raise SGANoDisponible("SGA caído")

    ident, permiso = base.autenticar("docente.uno", CLAVE)
    with pytest.raises(SGANoDisponible):
        sincronizar(conn, Caido(base), ident, permiso, servicio)
    assert len(filas(conn)) == 3 and len(servicio.listar(CORREO)) == 2
    sync(conn, servicio, Envoltorio(base, quita={"90001", "90002", "90003"}))
    assert filas(conn) == [] and servicio.listar(CORREO) == []


def test_codigo_distinto_al_de_la_materia_es_invalido(conn, servicio, base):
    def otro(materia, crudo):
        crudo = json.loads(json.dumps(crudo))
        crudo["proyecto_formativo"]["codigo"] = "S91-SIMU-3-99999-9999"
        return crudo

    r = sync(conn, servicio, Envoltorio(base, cambia=otro))
    assert {m.estado for m in r.materias} == {"invalida"}
    assert all(m.fallos == ["proyecto_formativo.codigo: no coincide con la materia del SGA"] for m in r.materias)
    assert conn.execute("select count(*) n from asignatura").fetchone()["n"] == 0


def test_exige_autocommit(conn, servicio, base):
    conn.autocommit = False
    try:
        with pytest.raises(ValueError):
            sync(conn, servicio, base)
    finally:
        conn.rollback()
        conn.autocommit = True
