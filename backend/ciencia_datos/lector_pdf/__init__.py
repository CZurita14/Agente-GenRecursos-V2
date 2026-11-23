"""Lector determinista del sílabo UTI en PDF (spec §7, docs/mapeo-silabo.md)."""
from ciencia_datos.lector_pdf.ensamblar import leer_silabo
from ciencia_datos.lector_pdf.errores import SilaboIlegible

__all__ = ["SilaboIlegible", "leer_silabo"]
