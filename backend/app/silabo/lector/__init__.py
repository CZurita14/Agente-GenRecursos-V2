"""Lector determinista del sílabo UTI en PDF (spec §7, docs/mapeo-silabo.md)."""
from app.silabo.lector.ensamblar import leer_silabo
from app.silabo.lector.errores import SilaboIlegible

__all__ = ["SilaboIlegible", "leer_silabo"]
