"""Transporte de códigos: consola explícita de desarrollo o SMTP con TLS."""
import smtplib
import ssl
from email.message import EmailMessage

from app.auth.servicio import AuthError


def transporte_correo(config):
    def enviar(correo, codigo):
        if config.smtp_modo == "consola" and config.entorno == "desarrollo":
            print(f"[SOLO DESARROLLO] Código de ingreso para {correo}: {codigo}", flush=True)
            return
        if config.smtp_modo != "smtp" or not config.smtp_host or not config.smtp_remitente:
            raise AuthError(503, "Envío de códigos no configurado")
        mensaje = EmailMessage()
        mensaje["From"], mensaje["To"] = config.smtp_remitente, correo
        mensaje["Subject"] = "Código de acceso a materiales de aprendizaje"
        mensaje.set_content(f"Tu código de acceso es {codigo}. Caduca en 10 minutos. Si no lo solicitaste, ignora este mensaje.")
        try:
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10) as servidor:
                servidor.starttls(context=ssl.create_default_context())
                if config.smtp_usuario:
                    servidor.login(config.smtp_usuario, config.smtp_clave.get_secret_value() if config.smtp_clave else "")
                servidor.send_message(mensaje)
        except smtplib.SMTPRecipientsRefused:
            # Un rechazo del buzón no debe revelar si existe ese destinatario.
            # El reto caducará aunque el solicitante nunca reciba el mensaje.
            return
        except (OSError, smtplib.SMTPException):
            raise AuthError(503, "No se pudo enviar el código") from None
    return enviar
