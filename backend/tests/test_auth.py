"""Ingreso con el SGA y sesiones contra PostgreSQL real, con el SGA simulado."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient

from app.agentes.facultades import cargar_catalogo, cargar_perfiles
from app.api.aplicacion import crear_app
from app.asignaturas.servicio import ServicioAsignaturas
from app.auth.servicio import AuthError, ServicioAuth, normalizar_correo
from app.config import RAIZ, Ajustes
from app.sga import SGAError, SGANoDisponible
from app.sga.simulado import ProveedorSimulado

CORREO = "docente@uti.edu.ec"
ORIGEN = {"Origin": "https://materiales.example"}
SGA = Path(__file__).parent / "fixtures" / "sga"
USUARIO, CLAVE = "docente.uno", "clave-prueba-uno"
CORREO_SGA = "docente.uno@uti.edu.ec"
CANARIO = "CANARIO-CLAVE-ERRADA-7731"


class SGACaido(ProveedorSimulado):
    def autenticar(self, usuario, clave):
        raise SGANoDisponible("SGA caído")


class SGAFalla(ProveedorSimulado):
    """Otra subclase de SGAError distinta de SGANoDisponible."""

    def autenticar(self, usuario, clave):
        raise SGAError("falla del SGA")


class SyncRota(ProveedorSimulado):
    """Autentica bien, pero la lista de materias falla de forma inesperada."""

    def listar_materias(self, permiso):
        raise RuntimeError("falla inesperada con la clave " + CLAVE)


@pytest.fixture
def reloj():
    return [datetime(2026, 10, 27, 15, tzinfo=timezone.utc)]


@pytest.fixture
def asignaturas(nueva_conexion):
    return ServicioAsignaturas(nueva_conexion, cargar_catalogo(RAIZ / "kb/catalogo.yaml"),
                               cargar_perfiles(RAIZ / "agentes"))


@pytest.fixture
def auth(nueva_conexion, asignaturas, reloj):
    return ServicioAuth(nueva_conexion, "s" * 48, ProveedorSimulado(SGA), asignaturas,
                        ahora=lambda: reloj[0])


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


# --- Ingreso con el SGA ---

def test_ingresar_abre_sesion_y_sincroniza(auth, conn):
    token = auth.ingresar(" docente.uno ", CLAVE)
    assert auth.identificar(token) == CORREO_SGA
    filas = conn.execute("select estado from materia_sga where correo=%s", (CORREO_SGA,)).fetchall()
    estados = {f["estado"] for f in filas}
    assert "importada" in estados and estados <= {"importada", "sin_cambios"}


def test_clave_incorrecta_y_usuario_inexistente_dan_el_mismo_error(auth):
    with pytest.raises(AuthError) as a:
        auth.ingresar(USUARIO, "otra-clave")
    with pytest.raises(AuthError) as b:
        auth.ingresar("no.existe", "otra-clave")
    assert (a.value.codigo, a.value.mensaje) == (b.value.codigo, b.value.mensaje) == (401, "Usuario o clave incorrectos")


def test_cinco_fallos_bloquean_con_429_y_la_clave_buena_no_entra(auth, reloj):
    for i in range(5):
        with pytest.raises(AuthError) as exc:
            auth.ingresar(USUARIO, "mala")
        assert exc.value.codigo == (429 if i == 4 else 401)
    assert exc.value.reintentar == 900
    with pytest.raises(AuthError) as exc:
        auth.ingresar(USUARIO, CLAVE)
    assert exc.value.codigo == 429 and 1 <= exc.value.reintentar <= 900
    reloj[0] += timedelta(minutes=14, seconds=59)
    with pytest.raises(AuthError) as exc:
        auth.ingresar(USUARIO, CLAVE)
    assert exc.value.codigo == 429
    reloj[0] += timedelta(seconds=2)
    assert auth.identificar(auth.ingresar(USUARIO, CLAVE)) == CORREO_SGA


def test_un_ingreso_correcto_reinicia_el_contador(auth, conn):
    for _ in range(4):
        with pytest.raises(AuthError):
            auth.ingresar(USUARIO, "mala")
    auth.ingresar(USUARIO, CLAVE)
    assert conn.execute("select count(*) n from auth_bloqueo").fetchone()["n"] == 0
    for _ in range(4):
        with pytest.raises(AuthError) as exc:
            auth.ingresar(USUARIO, "mala")
        assert exc.value.codigo == 401


def test_el_bloqueo_es_por_usuario_y_no_depende_de_la_instancia(auth, nueva_conexion, asignaturas, reloj):
    for _ in range(5):
        with pytest.raises(AuthError):
            auth.ingresar(USUARIO, "mala")
    otra = ServicioAuth(nueva_conexion, "s" * 48, ProveedorSimulado(SGA), asignaturas, ahora=lambda: reloj[0])
    with pytest.raises(AuthError) as exc:
        otra.ingresar(" DOCENTE.uno ", CLAVE)
    assert exc.value.codigo == 429
    assert otra.identificar(otra.ingresar("docente.dos", "clave-prueba-dos")) == "docente.dos@uti.edu.ec"


def test_fallos_concurrentes_se_acumulan(auth, conn):
    def fallar(_):
        try:
            auth.ingresar(USUARIO, "mala")
        except AuthError as exc:
            return exc.codigo

    with ThreadPoolExecutor(max_workers=5) as pool:
        codigos = list(pool.map(fallar, range(5)))
    assert sorted(codigos) == [401, 401, 401, 401, 429]
    assert conn.execute("select intentos from auth_bloqueo").fetchone()["intentos"] == 5


def test_diez_fallos_con_contencion_real_dejan_el_usuario_bloqueado(auth, conn, reloj):
    """Retiene la fila hasta ver a todos los competidores esperando el candado; el 6.º no puede limpiar el bloqueo."""
    cantidad = 10
    clave_u = auth._clave_bloqueo(USUARIO)
    conn.execute("insert into auth_bloqueo (usuario) values (%s)", (clave_u,))

    def fallar(_):
        try:
            auth.ingresar(USUARIO, "mala")
        except AuthError as exc:
            return exc.codigo

    with ThreadPoolExecutor(max_workers=cantidad) as pool:
        with conn.transaction():
            conn.execute("select * from auth_bloqueo where usuario=%s for update", (clave_u,))
            futuros = [pool.submit(fallar, i) for i in range(cantidad)]
            limite, esperando = time.monotonic() + 4, 0
            while time.monotonic() < limite and esperando < cantidad:
                conn.execute("select pg_stat_clear_snapshot()")
                esperando = conn.execute("select count(*) n from pg_stat_activity where wait_event_type='Lock' "
                                         "and pid<>pg_backend_pid()").fetchone()["n"]
                time.sleep(0.01)
            assert esperando == cantidad
        codigos = [f.result(timeout=10) for f in futuros]
    assert sorted(codigos) == [401] * 4 + [429] * 6
    fila = conn.execute("select * from auth_bloqueo").fetchone()
    assert fila["bloqueado_hasta"] is not None and fila["bloqueado_hasta"] > reloj[0] and fila["intentos"] == 5
    with pytest.raises(AuthError) as exc:
        auth.ingresar(USUARIO, CLAVE)
    assert exc.value.codigo == 429


def test_un_exito_en_vuelo_no_abre_sesion_si_otro_intento_bloqueo(nueva_conexion, asignaturas, conn):
    """Un intento correcto que empezó antes del bloqueo no abre sesión si el usuario quedó bloqueado."""
    class Lento(ProveedorSimulado):
        def autenticar(self, usuario, clave):
            resultado = super().autenticar(usuario, clave)
            for _ in range(5):  # Mientras este intento sigue en vuelo, otros cinco bloquean al usuario.
                with pytest.raises(AuthError):
                    otro.ingresar(usuario, "mala")
            return resultado

    servicio = ServicioAuth(nueva_conexion, "s" * 48, Lento(SGA), asignaturas)
    otro = ServicioAuth(nueva_conexion, "s" * 48, ProveedorSimulado(SGA), asignaturas)
    with pytest.raises(AuthError) as exc:
        servicio.ingresar(USUARIO, CLAVE)
    assert exc.value.codigo == 429
    assert conn.execute("select count(*) n from auth_sesion").fetchone()["n"] == 0


def test_sga_caido_da_503_sin_sesion_ni_fallo_contado(nueva_conexion, asignaturas, conn):
    servicio = ServicioAuth(nueva_conexion, "s" * 48, SGACaido(SGA), asignaturas)
    for _ in range(6):
        with pytest.raises(AuthError) as exc:
            servicio.ingresar(USUARIO, CLAVE)
        assert exc.value.codigo == 503
    assert conn.execute("select count(*) n from auth_sesion").fetchone()["n"] == 0
    assert conn.execute("select coalesce(sum(intentos),0) n from auth_bloqueo").fetchone()["n"] == 0


def test_otro_error_del_sga_da_503_y_no_cuenta(nueva_conexion, asignaturas, conn):
    servicio = ServicioAuth(nueva_conexion, "s" * 48, SGAFalla(SGA), asignaturas)
    for _ in range(7):
        with pytest.raises(AuthError) as exc:
            servicio.ingresar(USUARIO, CLAVE)
        assert exc.value.codigo == 503
    assert conn.execute("select coalesce(sum(intentos),0) n from auth_bloqueo").fetchone()["n"] == 0
    assert conn.execute("select count(*) n from auth_sesion").fetchone()["n"] == 0


def test_error_del_sga_no_levanta_un_bloqueo_vigente(auth, nueva_conexion, asignaturas, conn, reloj):
    for _ in range(5):
        with pytest.raises(AuthError):
            auth.ingresar(USUARIO, "mala")
    caido = ServicioAuth(nueva_conexion, "s" * 48, SGAFalla(SGA), asignaturas, ahora=lambda: reloj[0])
    with pytest.raises(AuthError) as exc:
        caido.ingresar(USUARIO, CLAVE)
    assert exc.value.codigo == 429
    assert conn.execute("select bloqueado_hasta from auth_bloqueo").fetchone()["bloqueado_hasta"] > reloj[0]


def test_sincronizacion_que_falla_no_impide_el_ingreso_ni_filtra_valores(nueva_conexion, asignaturas, caplog):
    servicio = ServicioAuth(nueva_conexion, "s" * 48, SyncRota(SGA), asignaturas)
    with caplog.at_level(logging.DEBUG):
        token = servicio.ingresar(USUARIO, CLAVE)
    assert servicio.identificar(token) == CORREO_SGA
    assert "RuntimeError" in caplog.text and CLAVE not in caplog.text


def _textos_de_la_base(conn):
    """Todo el texto de todas las tablas del esquema de prueba (text, varchar, jsonb)."""
    columnas = conn.execute(
        "select c.table_name t, c.column_name c from information_schema.columns c "
        "join information_schema.tables x using (table_schema, table_name) "
        "where c.table_schema=current_schema() and x.table_type='BASE TABLE' "
        "and c.data_type in ('text','character varying','jsonb','json')").fetchall()
    assert columnas
    for f in columnas:
        for fila in conn.execute(f'select "{f["c"]}"::text as v from "{f["t"]}"').fetchall():
            if fila["v"]:
                yield fila["v"]


def test_la_clave_no_queda_en_registros_ni_en_la_base(auth, conn, caplog):
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(AuthError):
            auth.ingresar(USUARIO, CANARIO)
        auth.ingresar(USUARIO, CLAVE)
    assert CLAVE not in caplog.text and CANARIO not in caplog.text
    assert not [v for v in _textos_de_la_base(conn) if CLAVE in v or CANARIO in v]
    assert not [v for v in vars(auth).values() if v in (CLAVE, CANARIO)]


def test_la_clave_tecleada_como_usuario_no_queda_en_la_base_ni_en_registros(auth, conn, caplog):
    tecleado = "CANARIO-USUARIO-CLAVE-5522"
    with caplog.at_level(logging.DEBUG):
        for _ in range(2):
            with pytest.raises(AuthError):
                auth.ingresar(tecleado, "otra")
    assert conn.execute("select count(*) n from auth_bloqueo").fetchone()["n"] == 1
    assert tecleado not in caplog.text and tecleado.lower() not in caplog.text
    assert not [v for v in _textos_de_la_base(conn) if tecleado.lower() in v.lower()]


# --- Sesiones ---

def test_sesion_directa_no_depende_de_la_instancia(auth, nueva_conexion, reloj):
    token = auth.sesion_directa(CORREO)
    otra = ServicioAuth(nueva_conexion, "s" * 48, ahora=lambda: reloj[0])
    assert otra.identificar(token) == CORREO


@pytest.mark.parametrize("tiempo", [timedelta(hours=8), timedelta(days=7)])
def test_sesion_expirada(auth, reloj, tiempo):
    token = auth.sesion_directa(CORREO)
    inicio = reloj[0]
    if tiempo.days:
        for hora in range(6, 168, 6):
            reloj[0] = inicio + timedelta(hours=hora)
            assert auth.identificar(token) == CORREO
    reloj[0] = inicio + tiempo
    assert auth.identificar(token) is None


def test_sesion_se_renueva_por_actividad_y_logout_revoca(auth, reloj):
    token = auth.sesion_directa(CORREO)
    reloj[0] += timedelta(hours=7)
    assert auth.identificar(token) == CORREO
    reloj[0] += timedelta(hours=7)
    assert auth.identificar(token) == CORREO
    auth.salir(token)
    assert auth.identificar(token) is None
    assert auth.identificar("cookie-inventada") is None


@pytest.fixture
def web(auth):
    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                     llm_model="m", api_origen="https://materiales.example", auth_secreto="s" * 48)
    with TestClient(crear_app(config, auth=auth, conexion=auth.conexion), base_url="https://materiales.example") as c:
        yield c


def test_http_ingreso_cookie_materias_yo_y_salida(web, auth, caplog):
    with caplog.at_level(logging.DEBUG):
        r = web.post("/auth/ingresar", json={"usuario": USUARIO, "clave": CLAVE}, headers=ORIGEN)
    assert r.status_code == 200, r.text
    assert CLAVE not in r.text and CLAVE not in caplog.text
    cuerpo = r.json()
    assert cuerpo["correo"] == CORREO_SGA and cuerpo["materias"]
    for m in cuerpo["materias"]:
        assert set(m) == {"id_sga", "codigo_pf", "paralelo", "nombre", "carrera", "estado_sga",
                          "estado", "asignatura_id"}
    cookie = r.headers["set-cookie"].lower()
    assert "sesion=" in cookie and "httponly" in cookie and "secure" in cookie
    assert "samesite=lax" in cookie and "max-age=604800" in cookie and "path=/" in cookie
    assert web.get("/auth/yo").json() == {"correo": CORREO_SGA, "rol": "docente"}
    token = web.cookies.get("sesion")
    assert web.post("/auth/salir", headers=ORIGEN).status_code == 200
    assert web.get("/auth/yo").status_code == 401
    assert auth.identificar(token) is None


def test_http_credenciales_incorrectas_401_uniforme_sin_cookie(web):
    a = web.post("/auth/ingresar", json={"usuario": USUARIO, "clave": "mala"}, headers=ORIGEN)
    b = web.post("/auth/ingresar", json={"usuario": "no.existe", "clave": "mala"}, headers=ORIGEN)
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json() == {"detail": "Usuario o clave incorrectos"}
    assert "set-cookie" not in a.headers and "set-cookie" not in b.headers


def test_http_bloqueo_429_con_retry_after_y_persiste(web):
    for _ in range(5):
        r = web.post("/auth/ingresar", json={"usuario": USUARIO, "clave": "mala"}, headers=ORIGEN)
    assert r.status_code == 429 and r.headers["retry-after"] == "900"
    r = web.post("/auth/ingresar", json={"usuario": USUARIO, "clave": CLAVE}, headers=ORIGEN)
    assert r.status_code == 429 and "set-cookie" not in r.headers


def test_http_sga_caido_503_sin_cookie(nueva_conexion, asignaturas):
    servicio = ServicioAuth(nueva_conexion, "s" * 48, SGACaido(SGA), asignaturas)
    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                     llm_model="m", api_origen="https://materiales.example", auth_secreto="s" * 48)
    with TestClient(crear_app(config, auth=servicio, conexion=nueva_conexion),
                    base_url="https://materiales.example") as c:
        r = c.post("/auth/ingresar", json={"usuario": USUARIO, "clave": CLAVE}, headers=ORIGEN)
        assert r.status_code == 503 and "set-cookie" not in r.headers


def test_http_no_abre_sesion_desde_otro_origen(web):
    r = web.post("/auth/ingresar", json={"usuario": USUARIO, "clave": CLAVE},
                 headers={"Origin": "https://intruso.example"})
    assert r.status_code == 403 and "set-cookie" not in r.headers


def test_http_las_rutas_del_codigo_por_correo_ya_no_existen(web):
    for ruta in ("/auth/codigo", "/auth/verificar"):
        r = web.post(ruta, json={"correo": CORREO, "codigo": "123456"}, headers=ORIGEN)
        assert r.status_code == 401  # Sin sesión: la ruta ya no es pública.


def test_http_rechaza_cookie_falsa(web):
    web.cookies.set("sesion", "inventada")
    assert web.get("/auth/yo").status_code == 401


# --- Acceso de prueba (sin el SGA): apagado por defecto y prohibido en producción ---

def _app_prueba(nueva_conexion, auth, **extra):
    config = Ajustes(_env_file=None, database_url="postgresql://no-usar", llm_base_url="http://m/v1", llm_model="m",
                     api_origen="http://localhost:5173", entorno="desarrollo",
                     auth_secreto="s" * 16 + "x" * 16, **extra)
    return TestClient(crear_app(config, auth=auth, conexion=nueva_conexion), base_url="https://testserver")


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


# --- Correo y usuario del SGA (revisión final) ---

class CorreoDelSGA(ProveedorSimulado):
    """El SGA devuelve el correo con mayúsculas o espacios, o de otro dominio."""

    def __init__(self, base, correo):
        super().__init__(base)
        self.correo = correo

    def autenticar(self, usuario, clave):
        ident, permiso = super().autenticar(usuario, clave)
        return replace(ident, correo=self.correo), permiso


class Registra(ProveedorSimulado):
    """Anota el usuario tal como llega al SGA."""

    def __init__(self, base):
        super().__init__(base)
        self.usuarios = []

    def autenticar(self, usuario, clave):
        self.usuarios.append(usuario)
        return super().autenticar(usuario, clave)


def test_correo_del_sga_con_mayusculas_se_normaliza_antes_de_sincronizar(nueva_conexion, asignaturas, conn):
    servicio = ServicioAuth(nueva_conexion, "s" * 48, CorreoDelSGA(SGA, "  Docente.Uno@UTI.Edu.EC "), asignaturas)
    correo = servicio.identificar(servicio.ingresar(USUARIO, CLAVE))
    assert correo == CORREO_SGA
    assert {f["correo"] for f in conn.execute("select correo from materia_sga").fetchall()} == {CORREO_SGA}
    assert {f["dueno"] for f in conn.execute("select dueno from asignatura").fetchall()} == {CORREO_SGA}
    assert asignaturas.materias(correo) and asignaturas.listar(correo)


def test_correo_del_sga_de_otro_dominio_da_403_sin_escribir(nueva_conexion, asignaturas, conn):
    servicio = ServicioAuth(nueva_conexion, "s" * 48, CorreoDelSGA(SGA, "docente.uno@gmail.com"), asignaturas)
    with pytest.raises(AuthError) as exc:
        servicio.ingresar(USUARIO, CLAVE)
    assert exc.value.codigo == 403
    for tabla in ("materia_sga", "asignatura", "auth_sesion"):
        assert conn.execute(f"select count(*) n from {tabla}").fetchone()["n"] == 0


def test_el_usuario_llega_al_sga_sin_cambiar_mayusculas_y_el_bloqueo_no_las_distingue(
        nueva_conexion, asignaturas, conn):
    sga = Registra(SGA)
    servicio = ServicioAuth(nueva_conexion, "s" * 48, sga, asignaturas)
    for usuario in (" Docente.UNO ", "docente.uno", "DOCENTE.uno"):
        with pytest.raises(AuthError):
            servicio.ingresar(usuario, "mala")
    assert sga.usuarios == ["Docente.UNO", "docente.uno", "DOCENTE.uno"]
    fila = conn.execute("select count(*) n, max(intentos) i from auth_bloqueo").fetchone()
    assert (fila["n"], fila["i"]) == (1, 3)


def test_http_el_usuario_llega_al_sga_sin_cambiar_mayusculas(nueva_conexion, asignaturas):
    sga = Registra(SGA)
    servicio = ServicioAuth(nueva_conexion, "s" * 48, sga, asignaturas)
    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                     llm_model="m", api_origen="https://materiales.example", auth_secreto="s" * 48)
    with TestClient(crear_app(config, auth=servicio, conexion=nueva_conexion),
                    base_url="https://materiales.example") as c:
        r = c.post("/auth/ingresar", json={"usuario": " Docente.UNO ", "clave": "mala"}, headers=ORIGEN)
    assert r.status_code == 401 and sga.usuarios == ["Docente.UNO"]


def test_ingreso_y_get_materias_dan_el_mismo_orden(web, auth):
    r = web.post("/auth/ingresar", json={"usuario": USUARIO, "clave": CLAVE}, headers=ORIGEN)
    assert r.status_code == 200
    assert r.json()["materias"] == web.get("/materias").json()
    assert not hasattr(auth, "materias")


def test_el_presupuesto_de_sincronizacion_sale_de_la_configuracion(nueva_conexion):
    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1", llm_model="m",
                     api_origen="https://materiales.example", auth_secreto="s" * 48, sga_sincronizacion_max_s=30)
    app = crear_app(config, conexion=nueva_conexion)
    assert app.state.auth.sincronizacion_max_s == 30


# --- Registro de ingresos ---

def _registro(conn):
    return [dict(f) for f in conn.execute(
        "select evento,correo,usuario_hash,ip from auth_registro order by id").fetchall()]


def test_registro_guarda_ingreso_fallos_bloqueo_y_salida(auth, conn):
    for _ in range(5):
        with pytest.raises(AuthError):
            auth.ingresar(USUARIO, CANARIO, "10.1.2.3")
    filas = _registro(conn)
    assert [f["evento"] for f in filas] == ["fallido"] * 4 + ["bloqueado"]
    # Un intento fallido no deja el usuario tecleado en claro: solo su seudónimo, y nunca la clave.
    assert all(f["correo"] is None and f["usuario_hash"] and f["ip"] == "10.1.2.3" for f in filas)
    assert len({f["usuario_hash"] for f in filas}) == 1
    assert not [v for v in _textos_de_la_base(conn) if CANARIO in v]
    conn.execute("delete from auth_bloqueo")
    conn.execute("delete from auth_registro")
    token = auth.ingresar(USUARIO, CLAVE, "10.1.2.3")
    auth.salir(token, "10.1.2.4")
    assert _registro(conn) == [
        {"evento": "ingreso", "correo": CORREO_SGA, "usuario_hash": None, "ip": "10.1.2.3"},
        {"evento": "salida", "correo": CORREO_SGA, "usuario_hash": None, "ip": "10.1.2.4"}]


def test_registro_guarda_sga_no_disponible(nueva_conexion, asignaturas, conn):
    servicio = ServicioAuth(nueva_conexion, "s" * 48, SGACaido(SGA), asignaturas)
    with pytest.raises(AuthError):
        servicio.ingresar(USUARIO, CLAVE)
    assert [f["evento"] for f in _registro(conn)] == ["sga_no_disponible"]


def test_un_fallo_del_registro_no_impide_el_ingreso(auth, monkeypatch, caplog):
    def sin_tabla(*a, **k):
        raise RuntimeError("tabla no disponible")
    conexion = auth.conexion

    class Rota:
        def __init__(self):
            object.__setattr__(self, "c", conexion())

        def __setattr__(self, n, v):  # autocommit y demás atributos van a la conexión real.
            setattr(self.c, n, v)

        def __getattr__(self, n):
            return getattr(self.c, n)

        def execute(self, sql, *a, **k):
            if "auth_registro" in sql:
                sin_tabla()
            return self.c.execute(sql, *a, **k)

    monkeypatch.setattr(auth, "conexion", Rota)
    with caplog.at_level(logging.WARNING):
        token = auth.ingresar(USUARIO, CLAVE)
    assert auth.identificar(token) == CORREO_SGA
    assert "No se pudo registrar el evento de acceso (RuntimeError)" in caplog.text


def test_http_registra_ingreso_y_salida(web, conn):
    assert web.post("/auth/ingresar", json={"usuario": USUARIO, "clave": CLAVE}, headers=ORIGEN).status_code == 200
    assert web.post("/auth/salir", headers=ORIGEN).status_code == 200
    assert [(f["evento"], f["correo"]) for f in _registro(conn)] == [("ingreso", CORREO_SGA), ("salida", CORREO_SGA)]


# --- Cuenta del docente ---

def test_el_primer_ingreso_crea_la_cuenta_y_los_siguientes_la_actualizan(auth, conn, reloj):
    primero = reloj[0]
    auth.ingresar(USUARIO, CLAVE)
    reloj[0] = primero + timedelta(days=3)
    auth.ingresar(CORREO_SGA.upper(), CLAVE)
    filas = conn.execute("select * from docente").fetchall()
    assert len(filas) == 1
    f = filas[0]
    assert (f["correo"], f["nombre"], f["ingresos"]) == (CORREO_SGA, "Docente Uno Simulado", 2)
    assert (f["primer_ingreso"], f["ultimo_ingreso"]) == (primero, reloj[0])


def test_un_ingreso_fallido_no_crea_cuenta(auth, conn):
    with pytest.raises(AuthError):
        auth.ingresar(USUARIO, CANARIO)
    with pytest.raises(AuthError):
        auth.ingresar("no.existe@uti.edu.ec", CANARIO)
    assert conn.execute("select count(*) n from docente").fetchone()["n"] == 0


def test_la_cuenta_se_crea_aunque_falle_la_sincronizacion(nueva_conexion, asignaturas, conn):
    servicio = ServicioAuth(nueva_conexion, "s" * 48, SyncRota(SGA), asignaturas)
    servicio.ingresar(USUARIO, CLAVE)
    assert conn.execute("select correo from docente").fetchone()["correo"] == CORREO_SGA
