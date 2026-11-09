"""Pool de conexiones de la API (revisión de A5: sin pool, cada petición abría 5 conexiones)."""
import threading

import pytest

from app.db.conexion import conectar
from app.db.pool import PoolConexiones


@pytest.fixture
def pool():
    creadas = []

    def fabrica():
        c = conectar()
        creadas.append(c)
        return c

    p = PoolConexiones(fabrica, max_inactivas=2)
    p.creadas = creadas
    yield p
    p.cerrar()


def test_reutiliza_la_conexion(pool):
    for _ in range(5):
        c = pool()
        c.autocommit = True
        assert c.execute("select 1 as uno").fetchone()["uno"] == 1
        c.close()
    assert len(pool.creadas) == 1


def test_restablece_ajustes_de_sesion(pool):
    c = pool()
    c.autocommit = True
    c.execute("set statement_timeout to '2s'")
    c.close()
    c = pool()
    c.autocommit = True
    assert c.execute("show statement_timeout").fetchone()["statement_timeout"] == "0"
    c.close()
    assert len(pool.creadas) == 1


def test_descarta_conexion_con_transaccion_abierta(pool):
    c = pool()
    c.execute("select 1")  # Sin autocommit: queda una transacción abierta.
    c.close()
    assert pool.creadas[0].closed
    pool().close()
    assert len(pool.creadas) == 2


def test_descarta_conexion_rota(pool):
    c = pool()
    c.autocommit = True
    pool.creadas[0].close()  # Simula una conexión caída mientras estaba prestada.
    c.close()
    pool().close()
    assert len(pool.creadas) == 2


def test_no_guarda_mas_inactivas_que_el_tope(pool):
    prestadas = [pool() for _ in range(4)]
    for c in prestadas:
        c.autocommit = True
        c.close()
    assert sum(not c.closed for c in pool.creadas) == 2


def test_cerrar_dos_veces_no_devuelve_dos_veces(pool):
    c = pool()
    c.autocommit = True
    c.close()
    c.close()
    a, b = pool(), pool()
    assert a._conn is not b._conn
    a.close(), b.close()


def test_uso_concurrente(pool):
    errores = []

    def trabajo():
        try:
            for _ in range(10):
                c = pool()
                c.autocommit = True
                c.execute("select 1").fetchone()
                c.close()
        except Exception as e:  # pragma: no cover - solo para reportar
            errores.append(e)

    hilos = [threading.Thread(target=trabajo) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == [] and len(pool.creadas) <= 6


def test_conserva_el_search_path_de_la_conexion(pool):
    c = pool()
    c.autocommit = True
    c.execute("set search_path to pg_catalog")
    c.close()
    c = pool()
    assert c.execute("show search_path").fetchone()["search_path"] == "pg_catalog"
    c.close()
