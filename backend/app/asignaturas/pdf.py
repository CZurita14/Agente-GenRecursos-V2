"""Sílabo en PDF para las cuentas locales de la etapa de pruebas (no tienen materias del SGA).

PDF → lector (ciencia_datos.lector_pdf) → JSON del Validador (silabo-api/0.1.0) → el mismo camino que
un sílabo del SGA: reglas del contrato, traducción, validación y `materia_sga`. Así la materia aparece
en «Generar herramientas» igual que una del SGA. Los mensajes nunca llevan texto del sílabo.
"""
import re

from app.sga.proveedor import MateriaSGA
from app.sga.sincronizar import MateriaEstado, _procesar, registrar_materia


class PdfNoDisponible(Exception):
    """El servidor no tiene instalado el lector de PDF (solo se instala para la etapa de pruebas)."""


class SilaboPdfIlegible(Exception):
    pass


class _UnSilabo:
    """Proveedor de una sola materia: entrega el sílabo leído del PDF."""

    def __init__(self, silabo: dict):
        self.silabo = silabo

    def obtener_silabo(self, permiso, materia):
        return self.silabo


def leer(datos: bytes) -> dict:
    if not datos.startswith(b"%PDF-"):
        raise SilaboPdfIlegible("El archivo no es un PDF")
    try:
        from ciencia_datos.lector_pdf.a_v2 import leer_silabo_v2
        from ciencia_datos.migrar_validador import desde_v2
    except ImportError:
        raise PdfNoDisponible("La lectura de sílabos en PDF no está instalada en este servidor") from None
    try:
        return desde_v2(leer_silabo_v2(datos))
    except Exception:  # SilaboIlegible u otra falla del lector: sin su mensaje (podría traer texto del PDF).
        raise SilaboPdfIlegible("No se pudo leer el sílabo: revisa que sea el PDF del sílabo institucional") from None


def importar(conn, correo: str, datos: bytes, servicio) -> MateriaEstado:
    """Importa el sílabo del PDF a la cuenta; volver a subirlo actualiza la misma materia."""
    silabo = leer(datos)
    portada = silabo.get("portada") or {}
    codigo = portada.get("pf_codigo") or ""
    if not re.fullmatch(r"[A-Z0-9-]{5,60}", codigo):
        raise SilaboPdfIlegible("El PDF no tiene el código del Proyecto Formativo")
    materia = MateriaSGA(id_sga=codigo, codigo_pf=codigo, paralelo="1",
                         nombre=str(portada.get("pf_nombre") or codigo)[:200],
                         carrera=str(portada.get("carrera") or "")[:200], estado="ACTIVA")
    estado = _procesar(conn, _UnSilabo(silabo), None, materia, correo, servicio)
    registrar_materia(conn, correo, materia, estado)
    return estado
