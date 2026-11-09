"""Ingreso y sesiones contra PostgreSQL real, correo capturado sin envíos."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.api.aplicacion import crear_app
from app.auth.servicio import AuthError, ServicioAuth, normalizar_correo
from app.config import Ajustes

CORREO = "docente@uti.edu.ec"
ORIGEN = {"Origin": "https://materiales.example"}


@pytest.fixture
def auth(nueva_conexion):
    enviados = []
    reloj = [datetime(2026, 10, 27, 15, tzinfo=timezone.utc)]
    servicio = ServicioAuth(nueva_conexion, "s" * 48,
                            lambda correo, codigo: enviados.append((correo, codigo)),
                            ahora=lambda: reloj[0])
    return servicio, enviados, reloj


@pytest.mark.parametrize("correo", ["a@uti.edu.ec.otro.com", "a@mail.uti.edu.ec",
    "a@indoamerica.edu.ec.otro.com", "a@gmail.com", "a@@uti.edu.ec",
    "a\r\n@uti.edu.ec", "Nombre <a@uti.edu.ec>"])
def test_dominio_no_permitido(correo):
    with pytest.raises(AuthError) as exc:
        normalizar_correo(correo)
    assert exc.value.codigo == 403


def test_correo_normalizado():
    assert normalizar_correo(" Docente@UTI.EDU.EC ") == CORREO
    assert normalizar_correo("a@indoamerica.edu.ec") == "a@indoamerica.edu.ec"


def test_codigo_y_sesion_no_se_guardan_en_claro(auth, conn):
    servicio, enviados, _ = auth
    servicio.pedir(CORREO)
    codigo = enviados[0][1]
    assert len(codigo) == 6 and codigo.isascii() and codigo.isdigit()
    reto = conn.execute("select * from auth_reto").fetchone()
    esperado = hmac.new(("s" * 48).encode(),
                        f"codigo:{CORREO}:{reto['nonce']}:{codigo}".encode(), hashlib.sha256).hexdigest()
    assert reto["codigo_hash"] == esperado
    token = servicio.verificar(CORREO, codigo)
    assert servicio.identificar(token) == CORREO
    sesion = conn.execute("select * from auth_sesion").fetchone()
    assert sesion["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    with pytest.raises(AuthError):
        servicio.verificar(CORREO, codigo)


def test_codigo_expira(auth):
    servicio, enviados, reloj = auth
    servicio.pedir(CORREO)
    reloj[0] += timedelta(minutes=10)
    with pytest.raises(AuthError) as exc:
        servicio.verificar(CORREO, enviados[0][1])
    assert exc.value.codigo == 401


def test_cinco_fallos_bloquean_y_reenvio_no_borra_bloqueo(auth):
    servicio, enviados, reloj = auth
    servicio.pedir(CORREO)
    for i in range(5):
        with pytest.raises(AuthError) as exc:
            servicio.verificar(CORREO, "incorrecto")
        assert exc.value.codigo == (429 if i == 4 else 401)
    with pytest.raises(AuthError) as exc:
        servicio.verificar(CORREO, enviados[0][1])
    assert exc.value.codigo == 429
    reloj[0] += timedelta(minutes=2)
    with pytest.raises(AuthError) as exc:
        servicio.pedir(CORREO)
    assert exc.value.codigo == 429
    reloj[0] += timedelta(minutes=14)
    servicio.pedir(CORREO)
    assert servicio.identificar(servicio.verificar(CORREO, enviados[-1][1])) == CORREO


def test_reenvio_invalida_anterior_y_conserva_intentos(auth):
    servicio, enviados, reloj = auth
    servicio.pedir(CORREO)
    for _ in range(3):
        with pytest.raises(AuthError):
            servicio.verificar(CORREO, "incorrecto")
    reloj[0] += timedelta(seconds=61)
    servicio.pedir(CORREO)
    # No depende de que el generador aleatorio dé códigos diferentes.
    with pytest.raises(AuthError):
        servicio.verificar(CORREO, "incorrecto")
    with pytest.raises(AuthError) as exc:
        servicio.verificar(CORREO, "incorrecto")
    assert exc.value.codigo == 429


def test_reenvio_reemplaza_codigo(auth, monkeypatch):
    servicio, enviados, reloj = auth
    numeros = iter([111111, 222222])
    monkeypatch.setattr("app.auth.servicio.secrets.randbelow", lambda _: next(numeros))
    servicio.pedir(CORREO)
    reloj[0] += timedelta(seconds=61)
    servicio.pedir(CORREO)
    with pytest.raises(AuthError) as exc:
        servicio.verificar(CORREO, enviados[0][1])
    assert exc.value.codigo == 401
    assert servicio.identificar(servicio.verificar(CORREO, enviados[1][1])) == CORREO


def test_sesion_y_bloqueo_no_dependen_de_la_instancia(auth, nueva_conexion):
    servicio, enviados, reloj = auth
    servicio.pedir(CORREO)
    token = servicio.verificar(CORREO, enviados[0][1])
    otra = ServicioAuth(nueva_conexion, "s" * 48, lambda *_: None, ahora=lambda: reloj[0])
    assert otra.identificar(token) == CORREO
    servicio.pedir("otro@uti.edu.ec")
    for _ in range(5):
        with pytest.raises(AuthError):
            servicio.verificar("otro@uti.edu.ec", "error")
    with pytest.raises(AuthError) as exc:
        otra.pedir("otro@uti.edu.ec")
    assert exc.value.codigo == 429


def test_fallos_concurrentes_se_acumulan(auth, conn, nueva_conexion):
    servicio, _, _ = auth
    servicio.pedir(CORREO)

    def fallar(_):
        try:
            servicio.verificar(CORREO, "error")
        except AuthError as exc:
            return exc.codigo

    codigos = contencion_real(servicio, conn, nueva_conexion, fallar, 5)
    assert sorted(codigos) == [401, 401, 401, 401, 429]
    assert conn.execute("select intentos from auth_reto").fetchone()["intentos"] == 5


def test_envio_incierto_conserva_codigo_utilizable_y_limite(nueva_conexion, conn):
    entregados = []

    def falla(correo, codigo):
        entregados.append(codigo)
        raise AuthError(503, "Envío no disponible")

    servicio = ServicioAuth(nueva_conexion, "s" * 48, falla)
    with pytest.raises(AuthError):
        servicio.pedir(CORREO)
    assert conn.execute("select count(*) n from auth_reto").fetchone()["n"] == 1
    with pytest.raises(AuthError) as exc:
        servicio.pedir(CORREO)
    assert exc.value.codigo == 429
    assert servicio.identificar(servicio.verificar(CORREO, entregados[0])) == CORREO


def test_envio_no_retiene_bloqueo(nueva_conexion):
    enviados = []
    servicio = None

    def entregar(correo, codigo):
        # Verificación desde otra conexión mientras todavía corre el transporte.
        enviados.append(servicio.verificar(correo, codigo))

    servicio = ServicioAuth(nueva_conexion, "s" * 48, entregar)
    servicio.pedir(CORREO)
    assert servicio.identificar(enviados[0]) == CORREO


def test_reenvio_inmediato_limitado(auth):
    servicio, enviados, _ = auth
    servicio.pedir(CORREO)
    with pytest.raises(AuthError) as exc:
        servicio.pedir(CORREO)
    assert exc.value.codigo == 429 and len(enviados) == 1


@pytest.mark.parametrize("tiempo", [timedelta(hours=8), timedelta(days=7)])
def test_sesion_expirada(auth, tiempo):
    servicio, enviados, reloj = auth
    servicio.pedir(CORREO)
    token = servicio.verificar(CORREO, enviados[0][1])
    inicio = reloj[0]
    if tiempo.days:
        for hora in range(6, 168, 6):
            reloj[0] = inicio + timedelta(hours=hora)
            assert servicio.identificar(token) == CORREO
    reloj[0] = inicio + tiempo
    assert servicio.identificar(token) is None


def test_sesion_se_renueva_por_actividad_y_logout_revoca(auth):
    servicio, enviados, reloj = auth
    servicio.pedir(CORREO)
    token = servicio.verificar(CORREO, enviados[0][1])
    reloj[0] += timedelta(hours=7)
    assert servicio.identificar(token) == CORREO
    reloj[0] += timedelta(hours=7)
    assert servicio.identificar(token) == CORREO
    servicio.salir(token)
    assert servicio.identificar(token) is None
    assert servicio.identificar("cookie-inventada") is None


def test_codigo_solo_crea_una_sesion_bajo_concurrencia(auth, conn, nueva_conexion):
    servicio, enviados, _ = auth
    servicio.pedir(CORREO)

    def verificar(_):
        try:
            return servicio.verificar(CORREO, enviados[0][1])
        except AuthError:
            return None

    tokens = contencion_real(servicio, conn, nueva_conexion, verificar, 2)
    assert sum(t is not None for t in tokens) == 1
    assert conn.execute("select count(*) n from auth_sesion").fetchone()["n"] == 1


def contencion_real(servicio, conn, nueva_conexion, accion, cantidad):
    """Retiene la fila hasta observar a todos los competidores esperando un lock."""
    pids = []
    barrera = threading.Barrier(cantidad, timeout=5)

    def conexion():
        c = nueva_conexion()
        c.execute("set lock_timeout to '5s'")
        pids.append(c.info.backend_pid)
        barrera.wait()
        return c

    original = servicio.conexion
    servicio.conexion = conexion
    try:
        with ThreadPoolExecutor(max_workers=cantidad) as pool:
            with conn.transaction():
                conn.execute("select * from auth_reto where correo=%s for update", (CORREO,))
                futuros = [pool.submit(accion, i) for i in range(cantidad)]
                limite = time.monotonic() + 4
                esperando = 0
                while time.monotonic() < limite:
                    # pg_stat_clear_snapshot evita reutilizar una vista antigua en esta transacción.
                    conn.execute("select pg_stat_clear_snapshot()")
                    esperando = conn.execute("select count(*) n from pg_stat_activity "
                                             "where pid=any(%s) and wait_event_type='Lock'", (pids.copy(),)).fetchone()["n"]
                    if esperando == cantidad:
                        break
                    time.sleep(0.01)
                assert esperando == cantidad
            return [f.result(timeout=5) for f in futuros]
    finally:
        servicio.conexion = original


@pytest.fixture
def web(auth):
    servicio, _, _ = auth
    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                     llm_model="m", api_origen="https://materiales.example", auth_secreto="s" * 48)
    with TestClient(crear_app(config, auth=servicio, conexion=servicio.conexion), base_url="https://materiales.example") as c:
        yield c


def test_http_ingreso_cookie_yo_y_salida(web, auth):
    _, enviados, _ = auth
    r = web.post("/auth/codigo", json={"correo": CORREO}, headers=ORIGEN)
    assert r.status_code == 200 and enviados[0][1] not in r.text
    r = web.post("/auth/verificar", json={"correo": CORREO, "codigo": enviados[0][1]}, headers=ORIGEN)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    assert web.get("/auth/yo").json() == {"correo": CORREO, "rol": "docente"}
    token = web.cookies.get("sesion")
    assert web.post("/auth/salir", headers=ORIGEN).status_code == 200
    assert web.get("/auth/yo").status_code == 401
    assert auth[0].identificar(token) is None


def test_http_no_abre_sesion_desde_otro_origen(web, auth):
    servicio, enviados, _ = auth
    servicio.pedir(CORREO)
    r = web.post("/auth/verificar", json={"correo": CORREO, "codigo": enviados[0][1]},
                 headers={"Origin": "https://intruso.example"})
    assert r.status_code == 403 and "set-cookie" not in r.headers


def test_http_rechaza_cookie_falsa(web):
    web.cookies.set("sesion", "inventada")
    assert web.get("/auth/yo").status_code == 401


def test_http_bloqueo_persiste_entre_peticiones(web, auth):
    web.post("/auth/codigo", json={"correo": CORREO}, headers=ORIGEN)
    for _ in range(5):
        r = web.post("/auth/verificar", json={"correo": CORREO, "codigo": "error"}, headers=ORIGEN)
    assert r.status_code == 429
    assert "retry-after" in r.headers
    assert web.post("/auth/codigo", json={"correo": CORREO}, headers=ORIGEN).status_code == 429


def test_http_respuesta_uniforme_para_correos_nuevos_y_previos(web, auth):
    r1 = web.post("/auth/codigo", json={"correo": CORREO}, headers=ORIGEN)
    auth[2][0] += timedelta(seconds=61)
    r2 = web.post("/auth/codigo", json={"correo": CORREO}, headers=ORIGEN)
    r3 = web.post("/auth/codigo", json={"correo": "nuevo@uti.edu.ec"}, headers=ORIGEN)
    assert r1.status_code == r2.status_code == r3.status_code == 200
    assert r1.json() == r2.json() == r3.json()


def test_http_dominio_invalido_no_envia(web, auth):
    r = web.post("/auth/codigo", json={"correo": "a@mail.uti.edu.ec"}, headers=ORIGEN)
    assert r.status_code == 403 and auth[1] == []


# --- Acceso de prueba (sin SMTP institucional): apagado por defecto y prohibido en producción ---

def _app_prueba(nueva_conexion, auth, **extra):
    config = Ajustes(_env_file=None, database_url="postgresql://no-usar", llm_base_url="http://m/v1", llm_model="m",
                     api_origen="http://localhost:5173", entorno="desarrollo",
                     auth_secreto="s" * 16 + "x" * 16, **extra)
    return TestClient(crear_app(config, auth=auth[0], conexion=nueva_conexion), base_url="https://testserver")


ORIGEN_PRUEBA = {"Origin": "http://localhost:5173"}


def test_acceso_prueba_prohibido_en_produccion():
    with pytest.raises(ValueError, match="ACCESO_PRUEBA"):
        Ajustes(_env_file=None, database_url="postgresql://no-usar", llm_base_url="http://m/v1", llm_model="m",
                api_origen="https://materiales.example", entorno="produccion", acceso_prueba=True)


def test_acceso_prueba_apagado_por_defecto(nueva_conexion, auth):
    with _app_prueba(nueva_conexion, auth) as c:
        assert c.get("/auth/modo").json() == {"acceso_prueba": False}
        r = c.post("/auth/prueba", json={"correo": "docente@uti.edu.ec"}, headers=ORIGEN_PRUEBA)
        assert r.status_code == 404 and "sesion" not in r.cookies


def test_acceso_prueba_con_correo_e_invitado(nueva_conexion, auth):
    with _app_prueba(nueva_conexion, auth, acceso_prueba=True) as c:
        assert c.get("/auth/modo").json() == {"acceso_prueba": True}
        r = c.post("/auth/prueba", json={"correo": "Docente@UTI.edu.ec"}, headers=ORIGEN_PRUEBA)
        assert r.status_code == 200 and "HttpOnly" in r.headers["set-cookie"]
        assert c.get("/auth/yo").json()["correo"] == "docente@uti.edu.ec"
        c.cookies.clear()
        assert c.get("/auth/yo").status_code == 401
        assert c.post("/auth/prueba", json={}, headers=ORIGEN_PRUEBA).status_code == 200
        assert c.get("/auth/yo").json()["correo"] == "invitado@uti.edu.ec"


def test_acceso_prueba_mantiene_dominio_y_origen(nueva_conexion, auth):
    with _app_prueba(nueva_conexion, auth, acceso_prueba=True) as c:
        assert c.post("/auth/prueba", json={"correo": "alguien@gmail.com"}, headers=ORIGEN_PRUEBA).status_code == 403
        assert c.post("/auth/prueba", json={"correo": "docente@uti.edu.ec"},
                      headers={"Origin": "https://malicioso.example"}).status_code == 403
