"""Sílabo en el contrato 2.0 directo desde el PDF (plantilla anterior o 2026)."""
import json

from ciencia_datos.lector_pdf.ensamblar import leer_crudo
from ciencia_datos.lector_pdf.errores import SilaboIlegible
from ciencia_datos.migrar_v2 import migrar


def leer_silabo_v2(datos: bytes) -> dict:
    """PDF → contrato 2.0 (JSON serializable). SilaboIlegible sin texto del PDF ante cualquier falla."""
    try:
        crudo, apartados = leer_crudo(datos)
        return json.loads(json.dumps(migrar(crudo, apartados=apartados), default=str, ensure_ascii=False))
    except SilaboIlegible:
        raise
    except Exception:
        raise SilaboIlegible("El sílabo tiene un formato que no se pudo leer.") from None
