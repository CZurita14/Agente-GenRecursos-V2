"""Contrato HTTP de A1 sin llamadas al servidor real."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.aplicacion import crear_app
from app.config import Ajustes
from app.llm.cliente import ServidorNoDisponible
from app.silabo.lector.errores import SilaboIlegible


def ruta_publica(c, funcion):
    """Ruta de prueba en un camino público por POST (/salud solo admite GET/HEAD).

    Se coloca primero para que sustituya al manejador real de /auth/codigo.
    """
    c.app.add_api_route("/auth/codigo", funcion, methods=["POST"])
    c.app.router.routes.insert(0, c.app.router.routes.pop())


def cliente(respuesta=None, error=False):
    def modelos(request):
        assert request.url.path == "/v1/models"
        if error:
            raise httpx.ConnectError("detalle privado", request=request)
        return httpx.Response(200, json=respuesta or {
            "data": [{"id": "modelo-prueba", "max_model_len": 8192}]})

    config = Ajustes(_env_file=None, database_url="postgresql://no-usar",
                     llm_base_url="http://modelo/v1", llm_model="modelo-prueba",
                     api_origen="https://materiales.example")
    return TestClient(crear_app(config, transporte=httpx.MockTransport(modelos)))


def test_salud_modelo_y_agentes():
    with cliente() as c:
        r = c.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"
    assert r.json()["ia"] is True
    assert "general" in r.json()["agentes"]


@pytest.mark.parametrize("datos", [
    {"data": [{"id": "otro", "max_model_len": 8192}]},
    {"data": [{"id": "modelo-prueba", "max_model_len": 4096}]},
    {"data": "invalido"}, {"error": "detalle privado"},
])
def test_salud_no_da_ok_con_modelo_incompatible(datos):
    with cliente(datos) as c:
        assert c.get("/salud").status_code == 503


def test_salud_no_filtra_error_de_red():
    with cliente(error=True) as c:
        r = c.get("/salud")
    assert r.status_code == 503
    assert "detalle privado" not in r.text
    assert "http://" not in r.text


@pytest.mark.parametrize("ruta", ["/asignaturas", "/auth/yo", "/docs", "/openapi.json"])
def test_rutas_cerradas_sin_sesion(ruta):
    with cliente() as c:
        assert c.get(ruta).status_code == 401


@pytest.mark.parametrize("origen", [None, "null", "https://intruso.example",
                                     "https://materiales.example.intruso"])
def test_post_exige_origen_exacto(origen):
    headers = {"Origin": origen} if origen else {}
    with cliente() as c:
        assert c.post("/auth/codigo", headers=headers).status_code == 403


def test_preflight_solo_admite_origen_configurado():
    with cliente() as c:
        headers = {"Origin": "https://materiales.example",
                   "Access-Control-Request-Method": "POST"}
        r = c.options("/auth/codigo", headers=headers)
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == headers["Origin"]
        assert r.headers["access-control-allow-credentials"] == "true"
        headers["Origin"] = "https://intruso.example"
        r = c.options("/auth/codigo", headers=headers)
        assert "access-control-allow-origin" not in r.headers


def test_origen_configurado_no_tiene_comodines():
    with pytest.raises(ValueError):
        Ajustes(_env_file=None, database_url="x", llm_base_url="http://modelo/v1",
                llm_model="m", api_origen="*")


@pytest.mark.parametrize("error,codigo", [(SilaboIlegible, 422), (ServidorNoDisponible, 503)])
def test_error_no_incluye_contenido_interno(error, codigo):
    c = cliente()

    def fallar():
        raise error("contenido privado")

    ruta_publica(c, fallar)
    with c:
        r = c.post("/auth/codigo", headers={"Origin": "https://materiales.example"})
    assert r.status_code == codigo
    assert "contenido privado" not in r.text


def test_validacion_no_devuelve_valores_recibidos():
    c = cliente()

    def validar(numero: int):
        return numero

    ruta_publica(c, validar)
    with c:
        r = c.post("/auth/codigo?numero=contenido-privado",
                   headers={"Origin": "https://materiales.example"})
    assert r.status_code == 422
    assert "contenido-privado" not in r.text
