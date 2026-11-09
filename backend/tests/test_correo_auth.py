"""Correo sin conexiones de red ni mensajes reales."""
import smtplib
import ssl

import pytest

from app.auth.correo import transporte_correo
from app.auth.servicio import AuthError
from app.config import Ajustes


def config(**kw):
    return Ajustes(_env_file=None, database_url="x", llm_base_url="http://modelo/v1",
                   llm_model="m", **kw)


def test_secreto_corto_rechazado():
    with pytest.raises(ValueError):
        config(auth_secreto="corto")


def test_origen_http_solo_desarrollo():
    with pytest.raises(ValueError):
        config(api_origen="http://materiales.example", entorno="produccion")
    assert config(api_origen="http://localhost:5173", entorno="desarrollo").api_origen.startswith("http:")


def test_secretos_ocultos_en_repr():
    c = config(auth_secreto="secreto-privado" * 4, smtp_clave="clave-privada")
    assert "secreto-privado" not in repr(c) and "clave-privada" not in repr(c)


@pytest.mark.parametrize("kw", [{}, {"smtp_modo": "consola"}, {"smtp_modo": "smtp"}])
def test_sin_envio_si_no_configurado_o_consola_en_produccion(kw, capsys):
    with pytest.raises(AuthError) as exc:
        transporte_correo(config(**kw))("a@uti.edu.ec", "123456")
    assert exc.value.codigo == 503
    assert capsys.readouterr().out == ""


def test_consola_solo_desarrollo_explicito(capsys):
    transporte_correo(config(smtp_modo="consola", entorno="desarrollo"))("a@uti.edu.ec", "123456")
    assert "SOLO DESARROLLO" in capsys.readouterr().out


def test_smtp_exige_tls_con_certificado_validado(monkeypatch):
    pasos = []

    class Servidor:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.example", 587, 10)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def starttls(self, *, context):
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            pasos.append("tls")

        def login(self, usuario, clave):
            assert pasos == ["tls"] and (usuario, clave) == ("usuario", "clave")
            pasos.append("login")

        def send_message(self, mensaje):
            assert mensaje["To"] == "a@uti.edu.ec"
            pasos.append("envio")

    monkeypatch.setattr("app.auth.correo.smtplib.SMTP", Servidor)
    transporte_correo(config(smtp_modo="smtp", smtp_host="smtp.example",
                             smtp_remitente="materiales@uti.edu.ec",
                             smtp_usuario="usuario", smtp_clave="clave"))("a@uti.edu.ec", "123456")
    assert pasos == ["tls", "login", "envio"]


def test_fallo_smtp_no_filtra_credenciales(monkeypatch):
    def falla(*_, **__):
        raise smtplib.SMTPException("credenciales privadas")

    monkeypatch.setattr("app.auth.correo.smtplib.SMTP", falla)
    with pytest.raises(AuthError) as exc:
        transporte_correo(config(smtp_modo="smtp", smtp_host="smtp.example",
                                 smtp_remitente="materiales@uti.edu.ec"))("a@uti.edu.ec", "123456")
    assert exc.value.codigo == 503 and "privadas" not in str(exc.value)


def test_rechazo_de_buzon_no_enumera_destinatario(monkeypatch):
    class Servidor:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def starttls(self, **_):
            pass

        def send_message(self, mensaje):
            if mensaje["To"] == "inexistente@uti.edu.ec":
                raise smtplib.SMTPRecipientsRefused({mensaje["To"]: (550, b"no existe")})

    monkeypatch.setattr("app.auth.correo.smtplib.SMTP", Servidor)
    enviar = transporte_correo(config(smtp_modo="smtp", smtp_host="smtp.example",
                                     smtp_remitente="materiales@uti.edu.ec"))
    assert enviar("existente@uti.edu.ec", "123456") is None
    assert enviar("inexistente@uti.edu.ec", "123456") is None


def test_http_no_revela_rechazo_smtp(monkeypatch, nueva_conexion):
    from fastapi.testclient import TestClient
    from app.api.aplicacion import crear_app
    from app.auth.servicio import ServicioAuth

    class Servidor:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def starttls(self, **_):
            pass

        def send_message(self, mensaje):
            if mensaje["To"] == "inexistente@uti.edu.ec":
                raise smtplib.SMTPRecipientsRefused({mensaje["To"]: (550, b"no existe")})

    monkeypatch.setattr("app.auth.correo.smtplib.SMTP", Servidor)
    c = config(smtp_modo="smtp", smtp_host="smtp.example",
               smtp_remitente="materiales@uti.edu.ec", api_origen="https://materiales.example", auth_secreto="s" * 48)
    servicio = ServicioAuth(nueva_conexion, "s" * 48, transporte_correo(c))
    with TestClient(crear_app(c, auth=servicio, conexion=nueva_conexion)) as web:
        respuestas = [web.post("/auth/codigo", json={"correo": correo},
                              headers={"Origin": c.api_origen})
                      for correo in ["existente@uti.edu.ec", "inexistente@uti.edu.ec"]]
    assert [r.status_code for r in respuestas] == [200, 200]
    assert respuestas[0].json() == respuestas[1].json()
