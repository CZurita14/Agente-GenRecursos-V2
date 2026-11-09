"""Identidad de transporte y etiquetas de bitácora, sin red."""
import pytest
from starlette.requests import Request

from app.control.identidad import ProxyInvalido, ip_cliente, operacion_segura
from app.config import Ajustes


def req(ip, cadena):
    return Request({"type": "http", "client": (ip, 1234),
                    "headers": [(b"x-forwarded-for", cadena.encode())]})


def test_no_confia_en_xff_por_defecto():
    assert ip_cliente(req("198.51.100.1", "203.0.113.2"), []) == "198.51.100.1"


def test_proxy_confiable_recorrido_desde_derecha():
    redes = ["10.0.0.0/8"]
    assert ip_cliente(req("10.0.0.1", "203.0.113.99, 198.51.100.2, 10.0.0.2"), redes) == "198.51.100.2"
    assert ip_cliente(req("10.0.0.1", "invalido, 198.51.100.2"), redes) == "198.51.100.2"


@pytest.mark.parametrize("cadena", ["invalido", "198.51.100.1, invalido", ",".join(["10.0.0.1"] * 11), "x" * 2049])
def test_cadena_invalida_no_usa_ip_del_proxy(cadena):
    with pytest.raises(ProxyInvalido):
        ip_cliente(req("10.0.0.1", cadena), ["10.0.0.0/8"])


def test_proxy_sin_cabecera_actua_como_cliente_directo():
    assert ip_cliente(req("10.0.0.1", ""), ["10.0.0.0/8"]) == "10.0.0.1"


def test_ipv4_mapeada_e_ipv6_normalizadas():
    assert ip_cliente(req("::ffff:198.51.100.1", ""), []) == "198.51.100.1"
    assert ip_cliente(req("2001:0db8::1", ""), []) == "2001:db8::1"
    assert ip_cliente(req("2001:db8::1%zona", ""), []) == "2001:db8::1"


@pytest.mark.parametrize("red", ["0.0.0.0/0", "::/0", "*", "no-es-red"])
def test_no_se_puede_confiar_en_todo_internet(red):
    with pytest.raises(ValueError):
        Ajustes(_env_file=None, database_url="x", llm_base_url="http://no-usar/v1", llm_model="m", proxies_confiables=[red])


def test_etiquetas_no_devuelven_parametros_dinamicos():
    assert operacion_segura("/asignaturas/UUID-PRIVADO/compartir/correo@uti.edu.ec") == "compartir"
    assert operacion_segura("/asignaturas/UUID-PRIVADO/recursos/RID-PRIVADO") == "recurso"
    assert operacion_segura("/ruta/CANARIO-PRIVADO") == "desconocida"


def test_admin_normalizado_y_dominio_estricto():
    base = dict(_env_file=None, database_url="x", llm_base_url="http://no-usar/v1", llm_model="m")
    assert Ajustes(**base, administradores=[" Admin@UTI.EDU.EC "]).administradores == ["admin@uti.edu.ec"]
    with pytest.raises(ValueError):
        Ajustes(**base, administradores=["admin@mail.uti.edu.ec"])


def test_entrada_servidor_no_reescribe_ip_ni_imprime_url(monkeypatch):
    from app import servidor
    llamadas = []
    monkeypatch.setattr(servidor.uvicorn, "run", lambda *a, **kw: llamadas.append((a, kw)))
    servidor.main([])
    assert llamadas[0][1]["proxy_headers"] is False
    assert llamadas[0][1]["access_log"] is False
