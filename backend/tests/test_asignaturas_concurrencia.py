"""Regresiones de autorización cuando los locks obligan a esperar."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from fastapi import HTTPException
import pytest
from psycopg.types.json import Jsonb

from app.asignaturas.servicio import exigir_acceso
from app.asignaturas.servicio import ServicioAsignaturas
from app.agentes.facultades import cargar_catalogo, cargar_perfiles
from app.config import RAIZ


def esperar_locks(conn, pids, cantidad):
    limite = time.monotonic() + 3
    while time.monotonic() < limite:
        conn.execute("select pg_stat_clear_snapshot()")
        n = conn.execute("select count(*) n from pg_stat_activity where pid=any(%s) "
                         "and wait_event_type='Lock'", (pids.copy(),)).fetchone()["n"]
        if n == cantidad:
            return
        time.sleep(0.01)
    pytest.fail("La operación no esperó el bloqueo esperado")


@pytest.mark.parametrize("cambio,editar", [("retirar", False), ("degradar", True)])
def test_permiso_se_relee_despues_de_esperar(conn, nueva_conexion, silabo, cambio, editar):
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('dueno@uti.edu.ec','PF','1','ingenierias',%s) returning id",
                       (Jsonb(silabo.model_dump(mode="json")),)).fetchone()["id"]
    conn.execute("insert into asignatura_acceso values (%s,'editor@uti.edu.ec','editor')", (aid,))
    pids, listo = [], threading.Event()

    def autorizar():
        with nueva_conexion() as c:
            c.execute("set statement_timeout to '5s'")
            with c.transaction():
                pids.append(c.info.backend_pid)
                listo.set()
                try:
                    exigir_acceso(c, aid, "editor@uti.edu.ec", editar=editar)
                    return 200
                except HTTPException as exc:
                    return exc.status_code

    with ThreadPoolExecutor(max_workers=1) as pool:
        with conn.transaction():
            conn.execute("select id from asignatura where id=%s for update", (aid,))
            if cambio == "retirar":
                conn.execute("delete from asignatura_acceso where asignatura_id=%s", (aid,))
            else:
                conn.execute("update asignatura_acceso set rol='lector' where asignatura_id=%s", (aid,))
            futuro = pool.submit(autorizar)
            assert listo.wait(timeout=2)
            esperar_locks(conn, pids, 1)
        assert futuro.result(timeout=5) == 403


def test_dos_primeras_subidas_mismo_dueno_se_serializan(conn, nueva_conexion, silabo):
    pids, listos = [], threading.Event()

    def conexion():
        c = nueva_conexion()
        pids.append(c.info.backend_pid)
        if len(pids) == 2:
            listos.set()
        return c

    servicio = ServicioAsignaturas(conexion, cargar_catalogo(RAIZ / "kb/catalogo.yaml"),
                                    cargar_perfiles(RAIZ / "agentes"))
    correo = "dueno@uti.edu.ec"
    clave = f"{len(correo)}:{correo}{silabo.proyecto_formativo.codigo}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        with conn.transaction():
            conn.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (clave,))
            futuros = [pool.submit(servicio.guardar, correo, silabo) for _ in range(2)]
            assert listos.wait(timeout=2)
            esperar_locks(conn, pids, 2)
        resultados = [f.result(timeout=5) for f in futuros]
    assert resultados[0]["id"] == resultados[1]["id"]
    cambios = sorted(len(r["clases_cambiadas"]) for r in resultados)
    assert cambios == [0, sum(len(m.sesiones) for m in silabo.momentos)]
    assert conn.execute("select count(*) n from asignatura").fetchone()["n"] == 1
