"""Pruebas de la cola: FIFO, SKIP LOCKED, carril por asignatura, leases y espera."""
import threading
import time
import uuid
from datetime import datetime, timedelta

import pytest
from psycopg.types.json import Jsonb

from app.cola.trabajos import (
    Ambito, Trabajo, encolar, listar, poner_en_espera, registrar_avance, renovar_lease,
    terminar, tomar_siguiente,
)

AMBITO = Ambito("clase", "M2-C1")
TOLERANCIA = timedelta(seconds=5)


def test_lease_vencido_no_se_renueva(conn):
    tid = _encolar(conn, asignatura(conn))
    tomar_siguiente(conn, "w", 360)
    conn.execute("update trabajo set lease_hasta=now()-interval '1 second' where id=%s", (tid,))
    assert renovar_lease(conn, tid, "w", 360) is False


def asignatura(conn) -> uuid.UUID:
    """Inserta una asignatura mínima y devuelve su id."""
    fila = conn.execute(
        "insert into asignatura (dueno, codigo_pf, version_silabo, agente, silabo) "
        "values (%s, %s, 'v1', 'ingenieria', %s) returning id",
        ("docente@uti.edu.ec", f"PF-{uuid.uuid4().hex[:6]}", Jsonb({})),
    ).fetchone()
    return fila["id"]


def _encolar(conn, asig, herramienta="cuestionario") -> uuid.UUID:
    return encolar(conn, asignatura_id=asig, agente="ingenieria", ambito=AMBITO,
                   herramienta=herramienta, parametros={"n": 10})


def _ahora(conn) -> datetime:
    return conn.execute("select now() as t").fetchone()["t"]


def _fila(conn, trabajo_id) -> dict:
    return conn.execute("select * from trabajo where id = %s", (trabajo_id,)).fetchone()


def test_fifo(conn):
    a = _encolar(conn, asignatura(conn))
    b = _encolar(conn, asignatura(conn))
    t1 = tomar_siguiente(conn, "w1", 60)
    t2 = tomar_siguiente(conn, "w1", 60)
    assert (t1.id, t2.id) == (a, b)
    assert tomar_siguiente(conn, "w1", 60) is None


def test_tomar_devuelve_trabajo_tipado(conn):
    asig = asignatura(conn)
    a = _encolar(conn, asig)
    t = tomar_siguiente(conn, "w1", 60)
    assert isinstance(t, Trabajo)
    assert isinstance(t.id, uuid.UUID) and t.id == a
    assert t.asignatura_id == asig
    assert t.ambito == AMBITO
    assert t.parametros == {"n": 10}
    assert t.estado == "generando" and t.worker_id == "w1"
    assert abs(t.lease_hasta - (_ahora(conn) + timedelta(seconds=60))) < TOLERANCIA


def test_skip_locked(conn, nueva_conexion):
    a = _encolar(conn, asignatura(conn))
    b = _encolar(conn, asignatura(conn))
    c1, c2 = nueva_conexion(), nueva_conexion()
    c2.execute("set statement_timeout = '3s'")  # sin SKIP LOCKED, c2 se quedaría esperando
    with c1.transaction():
        t1 = tomar_siguiente(c1, "w1", 60)  # fila bloqueada hasta que c1 confirme
        t2 = tomar_siguiente(c2, "w2", 60)
    assert t1.id == a and t2.id == b


def test_carril_por_asignatura(conn):
    asig = asignatura(conn)
    a = _encolar(conn, asig)
    b = _encolar(conn, asig)
    assert tomar_siguiente(conn, "w1", 60).id == a
    assert tomar_siguiente(conn, "w2", 60) is None
    terminar(conn, a, "listo")
    assert tomar_siguiente(conn, "w2", 60).id == b


def test_carril_ocupado_no_bloquea_otras_asignaturas(conn):
    # Si el OR no va entre paréntesis, x2 (más antiguo) se elige, choca y devuelve None.
    x = asignatura(conn)
    x1 = _encolar(conn, x)
    _encolar(conn, x)
    y1 = _encolar(conn, asignatura(conn))
    assert tomar_siguiente(conn, "w1", 60).id == x1
    assert tomar_siguiente(conn, "w2", 60).id == y1


def test_carril_entre_workers_concurrentes(conn, nueva_conexion):
    # c2 no ve el trabajo de c1 aún sin confirmar; el índice trabajo_carril lo frena.
    asig = asignatura(conn)
    a = _encolar(conn, asig)
    _encolar(conn, asig)
    c1, c2 = nueva_conexion(), nueva_conexion()
    c2.execute("set statement_timeout = '5s'")  # una regresión falla en vez de colgar
    resultado = {}

    def segundo():
        try:
            resultado["t"] = tomar_siguiente(c2, "w2", 60)
        except Exception as e:  # noqa: BLE001
            resultado["e"] = e

    with c1.transaction():
        t1 = tomar_siguiente(c1, "w1", 60)
        hilo = threading.Thread(target=segundo, daemon=True)
        hilo.start()
        hilo.join(0.5)
        assert hilo.is_alive()  # espera en el índice único a que c1 termine
    hilo.join(5)
    assert not hilo.is_alive()
    assert t1.id == a
    assert "e" not in resultado and resultado["t"] is None
    activos = conn.execute(
        "select count(*) as n from trabajo where estado = 'generando'").fetchone()["n"]
    assert activos == 1


def test_lease_vencido_se_retoma(conn):
    a = _encolar(conn, asignatura(conn))
    assert tomar_siguiente(conn, "w1", 1).id == a
    assert renovar_lease(conn, a, "w1", 1) is True
    time.sleep(1.2)
    t = tomar_siguiente(conn, "w2", 60)
    assert t.id == a and t.worker_id == "w2"
    assert renovar_lease(conn, a, "w1", 60) is False
    assert renovar_lease(conn, a, "w2", 60) is True


def test_lease_vencido_gana_a_pendiente_mas_antiguo(conn):
    # b (más antiguo, en espera) no debe tapar la recuperación de a (activo, lease vencido).
    asig = asignatura(conn)
    b = _encolar(conn, asig)
    poner_en_espera(conn, b)
    a = _encolar(conn, asig)
    assert tomar_siguiente(conn, "w1", 60).id == a
    conn.execute("update trabajo set disponible_desde = now() - interval '1 s' where id = %s", (b,))
    conn.execute("update trabajo set lease_hasta = now() - interval '1 s' where id = %s", (a,))
    assert tomar_siguiente(conn, "w2", 60).id == a
    terminar(conn, a, "listo")
    assert tomar_siguiente(conn, "w2", 60).id == b


def test_renovar_falla_si_no_esta_activo(conn):
    a = _encolar(conn, asignatura(conn))
    tomar_siguiente(conn, "w1", 60)
    terminar(conn, a, "error", "falló")
    assert renovar_lease(conn, a, "w1", 60) is False
    f = _fila(conn, a)
    assert f["estado"] == "error" and f["error"] == "falló"
    assert f["worker_id"] is None and f["lease_hasta"] is None
    # Aunque conserve el worker_id, un trabajo fuera de estado activo no se renueva.
    b = _encolar(conn, asignatura(conn))
    tomar_siguiente(conn, "w1", 60)
    conn.execute("update trabajo set estado = 'listo' where id = %s", (b,))
    assert renovar_lease(conn, b, "w1", 60) is False


@pytest.mark.parametrize("estado", ["listo", "requiere_revision", "error", "en_espera",
                                    "en_cola"])
def test_registrar_avance_solo_estados_activos(conn, estado):
    a = _encolar(conn, asignatura(conn))
    tomar_siguiente(conn, "w1", 60)
    with pytest.raises(ValueError):
        registrar_avance(conn, a, estado=estado)
    assert _fila(conn, a)["estado"] == "generando"


def test_retomar_suma_intento(conn):
    a = _encolar(conn, asignatura(conn))
    assert tomar_siguiente(conn, "w1", 60).intentos == 0  # primera toma: no cuenta
    conn.execute("update trabajo set lease_hasta = now() - interval '1 s' where id = %s", (a,))
    t = tomar_siguiente(conn, "w2", 60)
    assert t.id == a and t.intentos == 1
    # Tras la espera, volver a tomarlo tampoco cuenta (ya lo sumó poner_en_espera).
    poner_en_espera(conn, a, worker_id="w2")
    conn.execute("update trabajo set disponible_desde = now() - interval '1 s' where id = %s", (a,))
    assert tomar_siguiente(conn, "w3", 60).intentos == 2


def _retomado_por_w2(conn) -> tuple[uuid.UUID, uuid.UUID]:
    """a de la asignatura X: w1 lo tomó, su lease venció y w2 lo retomó. b espera en X."""
    asig = asignatura(conn)
    a = _encolar(conn, asig)
    b = _encolar(conn, asig)
    tomar_siguiente(conn, "w1", 60)
    conn.execute("update trabajo set lease_hasta = now() - interval '1 s' where id = %s", (a,))
    assert tomar_siguiente(conn, "w2", 60).id == a
    return a, b


def test_terminar_zombi_no_libera_carril(conn):
    a, _ = _retomado_por_w2(conn)
    assert terminar(conn, a, "listo", worker_id="w1") is False
    f = _fila(conn, a)
    assert (f["estado"], f["worker_id"]) == ("generando", "w2")
    assert tomar_siguiente(conn, "w3", 60) is None  # el carril sigue ocupado por w2
    assert terminar(conn, a, "listo", worker_id="w2") is True
    assert _fila(conn, a)["worker_id"] is None


def test_avance_y_espera_zombi_no_tocan(conn):
    a, _ = _retomado_por_w2(conn)
    assert registrar_avance(conn, a, estado="verificando", tokens=(5, 5),
                            worker_id="w1") is False
    assert poner_en_espera(conn, a, worker_id="w1") is None
    f = _fila(conn, a)
    assert (f["estado"], f["worker_id"], f["tokens_entrada"]) == ("generando", "w2", 0)
    assert registrar_avance(conn, a, estado="verificando", tokens=(5, 5),
                            worker_id="w2") is True
    assert _fila(conn, a)["estado"] == "verificando"


def test_id_desconocido(conn):
    x = uuid.uuid4()
    assert poner_en_espera(conn, x) is None
    assert terminar(conn, x, "error") is False
    assert registrar_avance(conn, x, tokens=(1, 1)) is False


def test_en_espera_con_backoff(conn):
    a = _encolar(conn, asignatura(conn))
    tomar_siguiente(conn, "w1", 60)
    d1 = poner_en_espera(conn, a)
    assert abs(d1 - (_ahora(conn) + timedelta(seconds=30))) < TOLERANCIA
    d2 = poner_en_espera(conn, a)
    f = _fila(conn, a)
    assert f["intentos"] == 2 and f["estado"] == "en_espera"
    assert f["disponible_desde"] == d2
    assert abs(d2 - (_ahora(conn) + timedelta(seconds=60))) < TOLERANCIA
    assert f["worker_id"] is None and f["lease_hasta"] is None
    assert tomar_siguiente(conn, "w1", 60) is None
    conn.execute("update trabajo set disponible_desde = now() - interval '1 s' where id = %s", (a,))
    assert tomar_siguiente(conn, "w1", 60).id == a


def test_espera_tope_600(conn):
    a = _encolar(conn, asignatura(conn))
    conn.execute("update trabajo set intentos = 20 where id = %s", (a,))
    d = poner_en_espera(conn, a)
    assert abs(d - (_ahora(conn) + timedelta(seconds=600))) < TOLERANCIA


def test_tokens_se_acumulan(conn):
    a = _encolar(conn, asignatura(conn))
    tomar_siguiente(conn, "w1", 60)
    registrar_avance(conn, a, tokens=(100, 50))
    registrar_avance(conn, a, estado="verificando", lotes_total=3, lotes_hechos=1,
                     tokens=(100, 50))
    f = _fila(conn, a)
    assert (f["tokens_entrada"], f["tokens_salida"]) == (200, 100)
    assert (f["estado"], f["lotes_total"], f["lotes_hechos"]) == ("verificando", 3, 1)
    registrar_avance(conn, a, rondas_revision=1)
    f = _fila(conn, a)
    assert (f["lotes_total"], f["rondas_revision"]) == (3, 1)


def test_listar(conn):
    asig = asignatura(conn)
    a = _encolar(conn, asig)
    b = _encolar(conn, asig, "glosario")
    _encolar(conn, asignatura(conn))
    assert [t.id for t in listar(conn, asig)] == [a, b]


@pytest.mark.parametrize("estado", ["listo", "requiere_revision", "error"])
def test_terminados_no_se_toman(conn, estado):
    a = _encolar(conn, asignatura(conn))
    tomar_siguiente(conn, "w1", 60)
    terminar(conn, a, estado)
    assert tomar_siguiente(conn, "w1", 60) is None
