"""Compara los sílabos del SGA con sus JSON de referencia (exportados de V1 una sola vez).

Empareja por `proyecto_formativo.codigo`. Ambos lados pasan por `a_contrato`, así que solo
cuentan los campos del contrato. El informe da rutas de campos, nunca valores. Varios
archivos con el mismo código (paralelos) se aceptan si su contrato es idéntico; si difieren,
el error nombra el código.

    python -m app.sga.comparar <dir_sga> <dir_referencia>
"""
import json
import sys
from pathlib import Path

from app.sga.traductor import a_contrato


def _hojas(valor, ruta: str = "") -> dict[str, object]:
    if isinstance(valor, dict) and valor:
        out = {}
        for k, v in valor.items():
            out.update(_hojas(v, f"{ruta}.{k}" if ruta else k))
        return out
    if isinstance(valor, list) and valor:
        out = {}
        for i, v in enumerate(valor):
            out.update(_hojas(v, f"{ruta}[{i}]"))
        return out
    return {ruta: valor}


def _cargar(carpeta: Path) -> dict[str, dict]:
    por_codigo: dict[str, dict] = {}
    for f in sorted(Path(carpeta).glob("*.json")):
        crudo = json.loads(f.read_text(encoding="utf-8"))
        try:
            codigo = crudo["proyecto_formativo"]["codigo"]
        except (KeyError, TypeError):
            raise ValueError(f"{f.name}: proyecto_formativo.codigo: falta") from None
        contrato = a_contrato(crudo)
        # Varios paralelos comparten código: si su contrato es idéntico cuenta una vez.
        if codigo in por_codigo and por_codigo[codigo] != contrato:
            raise ValueError(f"{codigo}: varios archivos con este código y contenido distinto")
        por_codigo[codigo] = contrato
    return por_codigo


def comparar(dir_sga, dir_referencia) -> dict:
    sga, ref = _cargar(dir_sga), _cargar(dir_referencia)
    codigos = {}
    for codigo in sorted(sga.keys() & ref.keys()):
        a, b = _hojas(sga[codigo]), _hojas(ref[codigo])
        todas = a.keys() | b.keys()
        dif = sorted(r for r in todas if r not in a or r not in b or a[r] != b[r])
        codigos[codigo] = {
            "comparados": len(todas),
            "diferentes": dif,
            "coincidencia": round(100.0 * (len(todas) - len(dif)) / len(todas), 2) if todas else 100.0,
        }
    return {"codigos": codigos, "solo_sga": sorted(sga.keys() - ref.keys()),
            "solo_referencia": sorted(ref.keys() - sga.keys())}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("uso: python -m app.sga.comparar <dir_sga> <dir_referencia>")
        return 2
    inf = comparar(*args)
    for codigo, r in inf["codigos"].items():
        print(f"{codigo}: {r['coincidencia']}% de {r['comparados']} campos")
        for ruta in r["diferentes"]:
            print(f"  distinto: {ruta}")
    for c in inf["solo_sga"]:
        print(f"{c}: solo en el SGA")
    for c in inf["solo_referencia"]:
        print(f"{c}: solo en la referencia")
    ok = (all(not r["diferentes"] for r in inf["codigos"].values())
          and not inf["solo_sga"] and not inf["solo_referencia"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
