"""PDF de sílabos → JSON del contrato 2.0, en lote. Solo imprime conteos, nunca texto.

Uso (desde backend/): python -m ciencia_datos.lector_pdf.lote <carpeta con PDF> <carpeta de salida> [--2.0]
Por omisión escribe el JSON del Validador (silabo-api/0.1.0), el contrato definitivo; con --2.0, el contrato 2.0.
Lee los PDF de la carpeta (sin subcarpetas). Cada sílabo queda en <salida>/<n>.json.
"""
import json
import sys
from collections import Counter
from pathlib import Path

from ciencia_datos.lector_pdf.a_v2 import leer_silabo_v2
from ciencia_datos.lector_pdf.errores import SilaboIlegible
from ciencia_datos.migrar_validador import desde_v2


def main(origen: Path, destino: Path, formato_v2: bool = False) -> Counter:
    destino.mkdir(parents=True, exist_ok=True)
    c = Counter()
    for i, pdf in enumerate(sorted(origen.glob("*.pdf")), 1):
        c["pdf"] += 1
        try:
            v2 = leer_silabo_v2(pdf.read_bytes())
        except SilaboIlegible:
            c["ilegible"] += 1
            continue
        c["convertido"] += 1
        if not formato_v2:
            v2 = desde_v2(v2)
        (destino / f"{i:03d}.json").write_text(json.dumps(v2, ensure_ascii=False, indent=2), encoding="utf-8")
    return c


if __name__ == "__main__":
    print(dict(main(Path(sys.argv[1]), Path(sys.argv[2]), "--2.0" in sys.argv[3:])))
