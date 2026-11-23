"""PDF de sílabos → JSON del contrato 2.0, en lote. Solo imprime conteos, nunca texto.

Uso (desde backend/): python -m ciencia_datos.lector_pdf.lote <carpeta con PDF> <carpeta de salida>
Lee los PDF de la carpeta (sin subcarpetas). Cada sílabo queda en <salida>/<n>.json.
"""
import json
import sys
from collections import Counter
from pathlib import Path

from ciencia_datos.lector_pdf.a_v2 import leer_silabo_v2
from ciencia_datos.lector_pdf.errores import SilaboIlegible


def main(origen: Path, destino: Path) -> Counter:
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
        (destino / f"{i:03d}.json").write_text(json.dumps(v2, ensure_ascii=False, indent=2), encoding="utf-8")
    return c


if __name__ == "__main__":
    print(dict(main(Path(sys.argv[1]), Path(sys.argv[2]))))
