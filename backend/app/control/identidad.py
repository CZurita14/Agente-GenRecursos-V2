"""IP del transporte, o cadena de proxy solo cuando el salto directo es confiable."""
from ipaddress import ip_address, ip_network
import re


class ProxyInvalido(ValueError):
    """No atribuir una cadena no verificable a la cuota de un proxy legítimo."""


def _ip(valor):
    ip = ip_address(valor)
    if ip.version == 6 and ip.scope_id:
        ip = ip_address(ip.packed)
    return ip.ipv4_mapped if ip.version == 6 and ip.ipv4_mapped else ip


def ip_cliente(request, proxies):
    try:
        directa = _ip(request.client.host)
    except (ValueError, AttributeError):
        return "sin-ip"
    redes = [ip_network(p) for p in proxies]

    def confiable(ip):
        return any(ip.version == r.version and ip in r for r in redes)

    if not confiable(directa):
        return str(directa)
    cabecera = request.headers.get("x-forwarded-for", "")
    if not cabecera:
        return str(directa)
    if len(cabecera) > 2048:
        raise ProxyInvalido("Cadena de proxy inválida")
    partes = cabecera.split(",")
    if len(partes) > 10:
        raise ProxyInvalido("Cadena de proxy inválida")
    ultimo = directa
    for valor in reversed(partes):
        try:
            ultimo = _ip(valor.strip())
        except ValueError:
            raise ProxyInvalido("Cadena de proxy inválida") from None
        if not confiable(ultimo):
            # Todo lo que quede a su izquierda fue aportado por un cliente no confiable.
            return str(ultimo)
    return str(ultimo)


_RUTAS = [
    (r"/asignaturas/[^/]+/chat(?:/[^/]+)?", "chat"),
    (r"/asignaturas/[^/]+/recursos/[^/]+/items/[^/]+/regenerar", "regenerar"),
    (r"/salud", "salud"),
    (r"/salud/vivo", "salud.vivo"), (r"/salud/listo", "salud.listo"),
    (r"/auth/codigo", "auth.codigo"),
    (r"/auth/verificar", "auth.verificar"), (r"/auth/yo", "auth.yo"),
    (r"/auth/modo", "auth.modo"), (r"/auth/prueba", "auth.prueba"),
    (r"/auth/salir", "auth.salir"), (r"/silabos", "silabos"),
    (r"/privacidad", "privacidad"), (r"/admin/consumo", "admin.consumo"),
    (r"/asignaturas", "asignaturas"),
    (r"/asignaturas/[^/]+/menu", "asignaturas.menu"),
    (r"/asignaturas/[^/]+/herramientas", "herramientas"),
    (r"/asignaturas/[^/]+/generar", "generar"),
    (r"/asignaturas/[^/]+/trabajos", "trabajos"),
    (r"/asignaturas/[^/]+/recursos", "recursos"),
    (r"/asignaturas/[^/]+/recursos/[^/]+", "recurso"),
    (r"/asignaturas/[^/]+/recursos/[^/]+/validar", "recurso.validar"),
    (r"/asignaturas/[^/]+/recursos/[^/]+/exportar", "recurso.exportar"),
]


def operacion_segura(path):
    """Nunca retornar fragmentos de URL, ni siquiera si la ruta es desconocida."""
    return next((nombre for patron, nombre in _RUTAS if re.fullmatch(patron, path)), "desconocida")
