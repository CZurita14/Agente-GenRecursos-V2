"""Reglas de acceso y bitácora sin cuerpos, rutas dinámicas ni identidad en claro."""
from contextlib import closing
import logging

from app.control.limites import ControlLimites, LimiteExcedido, seudonimo

log = logging.getLogger(__name__)


class ControlAcceso:
    def __init__(self, conexion, config):
        self.conexion = conexion
        self.secreto = config.auth_secreto.get_secret_value().encode()
        self.limites = ControlLimites(conexion, config.auth_secreto.get_secret_value(), {
            "ip_minuto": (config.limite_ip_minuto, 60),
            "usuario_minuto": (config.limite_usuario_minuto, 60),
            "ingresar_ip_minuto": (config.limite_ingresar_ip_minuto, 60),
            "ingresar_usuario_minuto": (config.limite_ingresar_usuario_minuto, 60),
            "generar_correo_hora": (config.limite_generar_correo_hora, 3600),
            "editar_correo_minuto": (config.limite_editar_correo_minuto, 60),
            "audit_429_minuto": (1, 60),
        })

    def ip(self, ip, operacion, metodo):
        self.limites.consumir("ip_minuto", ip)
        if metodo == "POST" and operacion == "auth.ingresar":
            self.limites.consumir("ingresar_ip_minuto", ip)

    def usuario(self, correo, operacion, metodo):
        if metodo == "POST" and operacion == "auth.salir":
            # Una sesión consumida por terceros no debe impedir al titular revocarla.
            # El límite general por IP y la comprobación de sesión siguen activos.
            return
        self.limites.consumir("usuario_minuto", correo)
        if metodo == "POST" and operacion in {"generar", "chat", "regenerar"}:
            self.limites.consumir("generar_correo_hora", correo)
        if metodo == "PUT" and operacion == "recurso":
            self.limites.consumir("editar_correo_minuto", correo)

    def usuario_publico(self, usuario):
        """Cupo por usuario (o correo) en las rutas de ingreso, para no eludirlo rotando la IP."""
        self.limites.consumir("ingresar_usuario_minuto", usuario)

    def registrar(self, ip, actor, operacion, metodo, estado, duracion_ms):
        try:
            if estado == 429:
                try:
                    self.limites.consumir("audit_429_minuto", ip)
                except LimiteExcedido:
                    # No convertir una ráfaga bloqueada en crecimiento ilimitado de bitácora.
                    return
            with closing(self.conexion()) as conn:
                conn.autocommit = True
                conn.execute("set statement_timeout to '2s'")
                conn.execute("insert into acceso_api (operacion,metodo,estado,duracion_ms,ip_hash,actor_hash) "
                             "values (%s,%s,%s,%s,%s,%s)",
                             (operacion, metodo if metodo in {"GET", "POST", "PUT", "DELETE", "HEAD", "PATCH", "OPTIONS"} else "OTRO",
                              estado, min(max(0, duracion_ms), 2147483647),
                              seudonimo(self.secreto, "audit-ip", ip),
                              seudonimo(self.secreto, "audit-actor", actor) if actor else None))
        except Exception as exc:
            # El fallo de bitácora no convierte un guardado ya confirmado en un error reintentable.
            # No imprimir excepciones SQL, cuerpos ni claves del cliente.
            log.warning("No se pudo registrar acceso (%s)", type(exc).__name__)
