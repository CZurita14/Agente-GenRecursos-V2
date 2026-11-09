"""Límites persistentes; las pruebas SQL requieren la migración 007."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import threading
import time

import psycopg
import pytest

from app.control.limites import ControlLimites, LimiteExcedido, seudonimo


SECRETO = "s" * 32
FIJO = datetime(2026, 10, 27, 12, 0, 5, 100000, tzinfo=timezone.utc)


def test_seudonimo():
    resultado = seudonimo(SECRETO.encode(), "ip", "192.0.2.1")
    assert len(resultado) == 64
    assert int(resultado, 16) >= 0
    assert resultado == seudonimo(SECRETO.encode(), "ip", "192.0.2.1")
    assert resultado != hashlib.sha256(b"192.0.2.1").hexdigest()
    assert resultado != seudonimo(b"t" * 32, "ip", "192.0.2.1")
    assert resultado != seudonimo(SECRETO.encode(), "correo", "192.0.2.1")
    assert seudonimo(SECRETO.encode(), "a:b", "c") != seudonimo(SECRETO.encode(), "a", "b:c")
    assert resultado == hmac.new(SECRETO.encode(), b"2:ip192.0.2.1", hashlib.sha256).hexdigest()


@pytest.mark.parametrize("secreto", ["", "s" * 31, None, b"s" * 32, 32])
def test_secreto_invalido(secreto):
    with pytest.raises(ValueError):
        ControlLimites(None, secreto, {"ip": (3, 60)})


@pytest.mark.parametrize("reglas", [
    None, [], {"ip": (0, 60)}, {"ip": (-1, 60)}, {"ip": (True, 60)},
    {"ip": (3, 0)}, {"ip": (3, -1)}, {"ip": (3, False)},
    {"ip": (1.5, 60)}, {"ip": (3, 1.5)}, {"ip": (3,)},
    {"ip": "3,60"}, {"": (3, 60)}, {1: (3, 60)},
    {"ip": (2147483648, 60)},
])
def test_reglas_invalidas(reglas):
    with pytest.raises(ValueError):
        ControlLimites(None, SECRETO, reglas)


def test_regla_desconocida_no_abre_conexion():
    def prohibida():
        pytest.fail("No debe abrir conexión para reglas desconocidas")
    reglas = {"ip": (3, 60)}
    control = ControlLimites(prohibida, SECRETO, reglas)
    reglas["inyectada"] = (100, 60)
    with pytest.raises(ValueError):
        control.consumir("inyectada", "192.0.2.1")


def test_persiste_entre_instancias_y_no_guarda_raw(conn, nueva_conexion):
    valor = "persona@uti.edu.ec"
    for _ in range(2):
        ControlLimites(nueva_conexion, SECRETO, {"correo": (2, 60)}, ahora=lambda: FIJO).consumir("correo", valor)
    with pytest.raises(LimiteExcedido):
        ControlLimites(nueva_conexion, SECRETO, {"correo": (2, 60)}, ahora=lambda: FIJO).consumir("correo", valor)
    filas = conn.execute("select * from control_limite").fetchall()
    assert len(filas) == 1
    assert filas[0]["contador"] == 2
    assert filas[0]["clave"] == seudonimo(SECRETO.encode(), "correo", valor)
    assert valor not in repr(filas)


def test_reset_reintentar_y_limpieza(conn, nueva_conexion):
    reloj = [FIJO]
    control = ControlLimites(nueva_conexion, SECRETO, {"ip": (1, 60)}, ahora=lambda: reloj[0])
    control.consumir("ip", "192.0.2.1")
    for _ in range(3):
        with pytest.raises(LimiteExcedido) as exc:
            control.consumir("ip", "192.0.2.1")
        assert exc.value.reintentar == 55
        assert isinstance(exc.value.reintentar, int)
    fila = conn.execute("select * from control_limite").fetchone()
    inicio = FIJO.replace(second=0, microsecond=0)
    assert fila["ventana"] == inicio
    assert fila["vence"] == inicio + timedelta(seconds=120)
    assert fila["contador"] == 1
    reloj[0] = inicio + timedelta(seconds=59, microseconds=999999)
    with pytest.raises(LimiteExcedido) as exc:
        control.consumir("ip", "192.0.2.1")
    assert exc.value.reintentar == 1
    reloj[0] = inicio + timedelta(seconds=60)
    control.consumir("ip", "192.0.2.1")
    fila = conn.execute("select * from control_limite").fetchone()
    assert fila["ventana"] == reloj[0]
    assert fila["contador"] == 1
    assert fila["vence"] == reloj[0] + timedelta(seconds=120)


def test_ventana_floor_epoch_no_minuto(conn, nueva_conexion):
    control = ControlLimites(nueva_conexion, SECRETO, {"ip": (1, 47)}, ahora=lambda: FIJO)
    control.consumir("ip", "192.0.2.1")
    fila = conn.execute("select * from control_limite").fetchone()
    assert int(fila["ventana"].timestamp()) == int(FIJO.timestamp()) // 47 * 47


def test_reglas_e_ips_separadas(conn, nueva_conexion):
    control = ControlLimites(nueva_conexion, SECRETO, {"ip": (1, 60), "login": (1, 60)}, ahora=lambda: FIJO)
    for regla, valor in [("ip", "192.0.2.1"), ("ip", "192.0.2.2"), ("login", "192.0.2.1")]:
        control.consumir(regla, valor)
        with pytest.raises(LimiteExcedido):
            control.consumir(regla, valor)
    assert conn.execute("select count(*) n from control_limite").fetchone()["n"] == 3


def test_cinco_conexiones_realmente_contienden(conn, nueva_conexion):
    conexiones = [nueva_conexion() for _ in range(5)]
    barrera = threading.Barrier(6)
    clave = seudonimo(SECRETO.encode(), "ip", "192.0.2.1")
    inicio = FIJO.replace(second=0, microsecond=0)

    def consumir(c):
        barrera.wait(timeout=5)
        try:
            ControlLimites(lambda: c, SECRETO, {"ip": (3, 60)}, ahora=lambda: FIJO).consumir("ip", "192.0.2.1")
            return True
        except LimiteExcedido:
            return False

    pids = [c.info.backend_pid for c in conexiones]
    with ThreadPoolExecutor(max_workers=5) as pool:
        with conn.transaction():
            # Una ventana anterior sin confirmar fuerza a los cinco UPSERT a esperar;
            # el primero reinicia el contador al entrar en la ventana actual.
            conn.execute("insert into control_limite (regla,clave,ventana,contador,vence) "
                         "values (%s,%s,%s,1,%s)",
                         ("ip", clave, inicio - timedelta(seconds=60), inicio + timedelta(seconds=60)))
            futuros = [pool.submit(consumir, c) for c in conexiones]
            barrera.wait(timeout=5)
            limite = time.monotonic() + 1.5
            while time.monotonic() < limite:
                conn.execute("select pg_stat_clear_snapshot()")
                n = conn.execute("select count(*) n from pg_stat_activity where pid=any(%s) "
                                 "and wait_event_type='Lock'", (pids,)).fetchone()["n"]
                if n == 5:
                    break
                time.sleep(0.01)
            else:
                pytest.fail("Los cinco consumidores no contendieron simultáneamente")
        assert sorted(f.result(timeout=5) for f in futuros) == [False, False, True, True, True]
    assert conn.execute("select contador from control_limite").fetchone()["contador"] == 3


@pytest.mark.parametrize("zona,desfase", [("UTC", 0), ("America/Guayaquil", -5)])
def test_reloj_default_es_db(conn, nueva_conexion, monkeypatch, zona, desfase):
    import app.control.limites as modulo

    class SinRelojHost(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            pytest.fail("Producción debe usar clock_timestamp()")

    monkeypatch.setattr(modulo, "datetime", SinRelojHost)

    def conexion_con_zona():
        c = nueva_conexion()
        c.execute("select set_config('TimeZone', %s, false)", (zona,))
        reloj_db = c.execute("select clock_timestamp() ahora").fetchone()["ahora"]
        assert reloj_db.utcoffset() == timedelta(hours=desfase)
        return c

    antes = conn.execute("select clock_timestamp() ahora").fetchone()["ahora"]
    ControlLimites(conexion_con_zona, SECRETO, {"ip": (3, 1)}).consumir("ip", "192.0.2.1")
    despues = conn.execute("select clock_timestamp() ahora").fetchone()["ahora"]
    ventana = conn.execute("select ventana from control_limite").fetchone()["ventana"]
    assert antes.replace(microsecond=0) <= ventana <= despues


@pytest.mark.parametrize("ahora", [datetime(2026, 1, 1), FIJO.astimezone(timezone(timedelta(hours=1))), None, "fecha"])
def test_reloj_inyectado_invalido(conn, nueva_conexion, ahora):
    control = ControlLimites(nueva_conexion, SECRETO, {"ip": (1, 60)}, ahora=lambda: ahora)
    with pytest.raises(ValueError):
        control.consumir("ip", "192.0.2.1")


def test_contador_int_max_no_desborda(conn, nueva_conexion):
    control = ControlLimites(nueva_conexion, SECRETO, {"ip": (2147483647, 60)}, ahora=lambda: FIJO)
    control.consumir("ip", "192.0.2.1")
    conn.execute("update control_limite set contador=2147483646")
    control.consumir("ip", "192.0.2.1")
    with pytest.raises(LimiteExcedido):
        control.consumir("ip", "192.0.2.1")
    assert conn.execute("select contador from control_limite").fetchone()["contador"] == 2147483647


def test_lock_timeout_acotado(conn, nueva_conexion):
    control = ControlLimites(nueva_conexion, SECRETO, {"ip": (3, 60)}, ahora=lambda: FIJO)
    control.consumir("ip", "192.0.2.1")
    with conn.transaction():
        conn.execute("select * from control_limite for update")
        inicio = time.monotonic()
        with pytest.raises(psycopg.errors.LockNotAvailable):
            control.consumir("ip", "192.0.2.1")
        assert 1.5 <= time.monotonic() - inicio < 4
