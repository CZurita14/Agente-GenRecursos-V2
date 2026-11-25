"""Contexto del momento que escribe el docente: validación determinista y material para generar.

El material del momento es lo que reciben los pedidos de las herramientas de un momento y de
sus clases: el contexto validado del docente y, salvo para la propia guía, la guía de estudio
validada. Se toma como instantánea al encolar, igual que el sílabo.
"""
import re

MIN_CARACTERES, MAX_CARACTERES = 40, 6000
MAX_MATERIAL = 24000  # caracteres (≈ 6 000 tokens): la guía entra resumida por apartados.

_CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TELEFONO = re.compile(r"(?<!\d)(?:\+?593[\s-]?)?0?9\d{8}(?!\d)|(?<!\d)0[2-7]\d{7}(?!\d)")
_CEDULA = re.compile(r"(?<!\d)\d{10}(?!\d)")
_ETIQUETA = re.compile(r"<\s*/?\s*[a-zA-Z_][\w-]*[^>]*>")
_ORDEN = re.compile(r"\b(ignora|olvida|omite|desobedece)\b.{0,40}\b(instrucciones|reglas|indicaciones)\b"
                    r"|\b(system prompt|prompt del sistema|act[uú]a como)\b", re.I)
_RESOLVER = re.compile(r"\b(resuelve|redacta|responde|haz)\b.{0,40}\b(evidencia|entregable|examen|evaluaci[oó]n"
                       r"|tarea)\b", re.I)


class ContextoInvalido(ValueError):
    def __init__(self, motivos: list[str]):
        super().__init__("; ".join(motivos))
        self.motivos = motivos


def validar_contexto(texto: str) -> tuple[str, list[str]]:
    """Normaliza y comprueba el contexto; devuelve (texto, controles superados) o lanza ContextoInvalido."""
    limpio = "\n".join(" ".join(l.split()) for l in (texto or "").replace("\r", "").split("\n")).strip()
    limpio = re.sub(r"\n{3,}", "\n\n", limpio)
    motivos = []
    if len(limpio) < MIN_CARACTERES:
        motivos.append(f"El contexto es muy corto (mínimo {MIN_CARACTERES} caracteres).")
    if len(limpio) > MAX_CARACTERES:
        motivos.append(f"El contexto supera {MAX_CARACTERES} caracteres.")
    if _CORREO.search(limpio) or _TELEFONO.search(limpio) or _CEDULA.search(limpio):
        motivos.append("Quita datos personales (correos, teléfonos o cédulas): no se envían al modelo.")
    if _ETIQUETA.search(limpio):
        motivos.append("Quita las etiquetas entre < >: el contexto es texto plano.")
    if _ORDEN.search(limpio):
        motivos.append("El contexto no puede dar órdenes al sistema (p. ej., «ignora las instrucciones»).")
    if _RESOLVER.search(limpio):
        motivos.append("El contexto no puede pedir que se resuelvan las evidencias o evaluaciones del momento.")
    if motivos:
        raise ContextoInvalido(motivos)
    return limpio, ["extensión", "sin datos personales", "texto plano", "sin órdenes al sistema",
                    "respeta la integridad académica"]


def resumen_guia(contenido: dict) -> str:
    """La guía validada como material: objetivos, glosario y la teoría de cada apartado."""
    partes = []
    intro = contenido.get("introduccion") or {}
    if intro.get("objetivos"):
        partes.append("Objetivos: " + "; ".join(intro["objetivos"]))
    if intro.get("glosario"):
        partes.append("Glosario: " + "; ".join(f"{t['termino']}: {t['definicion']}" for t in intro["glosario"]))
    for clave in ("desarrollo_1", "desarrollo_2"):
        for a in (contenido.get(clave) or {}).get("apartados", []):
            partes.append(f"{a['titulo']}: {a['desarrollo']} Puntos clave: {'; '.join(a.get('puntos_clave', []))}")
    aplicacion = contenido.get("aplicacion") or {}
    if aplicacion.get("vinculacion_practica"):
        partes.append("Vinculación con la práctica: " + aplicacion["vinculacion_practica"])
    return " ".join(partes)


def armar_material(contexto_docente: str, guia: dict | None) -> str:
    partes = []
    if contexto_docente.strip():
        partes.append("Contexto del docente: " + contexto_docente.strip())
    if guia:
        partes.append("Guía de estudio validada del momento: " + resumen_guia(guia))
    material = " ".join(partes)
    return material if len(material) <= MAX_MATERIAL else material[:MAX_MATERIAL].rsplit(" ", 1)[0] + " …"


def material_momento(conn, asignatura_id, ambito_tipo: str, ambito_id: str, herramienta: str) -> str:
    """Material del momento del ámbito (momento o clase); vacío en el ámbito de asignatura."""
    from app.momentos.trazabilidad import numero_momento
    n = numero_momento(ambito_id) if ambito_tipo in ("momento", "clase") else None
    if n is None:
        return ""
    fila = conn.execute("select texto from momento_contexto where asignatura_id=%s and momento=%s",
                        (asignatura_id, n)).fetchone()
    guia = None
    if herramienta != "guia_estudio":
        g = conn.execute("select contenido from recurso where asignatura_id=%s and ambito_id=%s and "
                         "herramienta='guia_estudio' and validado_por is not null order by validado_en desc limit 1",
                         (asignatura_id, f"M{n}")).fetchone()
        guia = g["contenido"] if g else None
    return armar_material(fila["texto"] if fila else "", guia)
