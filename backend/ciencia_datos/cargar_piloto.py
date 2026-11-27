"""Carga sílabos piloto (PDF) en la cuenta de un docente del SGA simulado. Solo imprime conteos.

PDF → lector → JSON del Validador (silabo-api/0.1.0) → sga_silabos/<pf_codigo>.json, y la materia
se agrega (sin duplicar) a materias/<usuario>.json. Al ingresar, el docente los ve como suyos y el
sistema los sincroniza y valida igual que los del SGA real.

Uso (desde backend/): python -m ciencia_datos.cargar_piloto <carpeta con PDF> <carpeta del SGA simulado> <usuario>
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

from ciencia_datos.lector_pdf.a_v2 import leer_silabo_v2
from ciencia_datos.lector_pdf.errores import SilaboIlegible
from ciencia_datos.migrar_validador import desde_v2

_USUARIO = re.compile(r"^[a-z0-9._-]{1,64}$")


def materia(silabo: dict) -> dict:
    p = silabo["portada"]
    codigo = p["pf_codigo"]
    partes = codigo.split("-")
    return {"carrera": p.get("carrera", ""), "codigo_pf": codigo, "estado": "ACTIVA",
            "id_sga": partes[3] if len(partes) > 3 else codigo, "nombre": p.get("pf_nombre", ""), "paralelo": "1"}


def cargar(origen: Path, sga: Path, usuario: str) -> Counter:
    if not _USUARIO.match(usuario):
        raise ValueError("usuario no válido")
    c = Counter()
    ruta_materias = sga / "materias" / f"{usuario}.json"
    materias = json.loads(ruta_materias.read_text(encoding="utf-8")) if ruta_materias.exists() else []
    codigos = {m["codigo_pf"] for m in materias}
    (sga / "sga_silabos").mkdir(parents=True, exist_ok=True)
    for pdf in sorted(origen.glob("*.pdf")):
        c["pdf"] += 1
        try:
            silabo = desde_v2(leer_silabo_v2(pdf.read_bytes()))
        except SilaboIlegible:
            c["ilegible"] += 1
            continue
        codigo = silabo["portada"].get("pf_codigo") or ""
        if not re.fullmatch(r"[A-Z0-9-]{5,60}", codigo):
            c["sin_codigo_pf"] += 1
            continue
        (sga / "sga_silabos" / f"{codigo}.json").write_text(json.dumps(silabo, ensure_ascii=False, indent=2),
                                                             encoding="utf-8")
        c["cargado"] += 1
        if codigo in codigos:
            c["materia_ya_existia"] += 1
        else:
            materias.append(materia(silabo))
            codigos.add(codigo)
            c["materia_nueva"] += 1
    ruta_materias.parent.mkdir(parents=True, exist_ok=True)
    ruta_materias.write_text(json.dumps(materias, ensure_ascii=False, indent=2), encoding="utf-8")
    c["materias_en_la_cuenta"] = len(materias)
    return c


if __name__ == "__main__":
    print(dict(cargar(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])))
