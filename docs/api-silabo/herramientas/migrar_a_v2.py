"""Convierte sílabos del contrato 1.0 al 2.0 (V3: el sistema solo acepta 2.0).

Los campos que la plantilla anterior no tenía quedan vacíos (ND en la escala). Si el sílabo
de origen no declara PIS, el PIS 2.0 queda como no aplicable con su justificación.

Uso: python migrar_a_v2.py <archivo.json>... (reescribe cada archivo en su lugar).
Solo imprime rutas de archivos, nunca textos del sílabo.
"""
import json
import sys
from pathlib import Path

# La conversión vive en el backend (también la usa el lector de PDF): aquí solo el comando.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from ciencia_datos.migrar_v2 import migrar, plano  # noqa: E402,F401


if __name__ == "__main__":
    for ruta in map(Path, sys.argv[1:]):
        j = json.loads(ruta.read_text(encoding="utf-8"))
        if j.get("contrato") == "2.0":
            print("ya es 2.0:", ruta)
            continue
        ruta.write_text(json.dumps(migrar(j, extras=True), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("migrado:", ruta)
