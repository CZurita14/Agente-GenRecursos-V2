"""¿Cambian las herramientas al consumir el JSON del Validador (silabo-api/0.1.0) en lugar del 2.0?

Para cada sílabo real compara, por los dos caminos (2.0 directo y 2.0 → validador → sistema), las
mismas huellas que la prueba de equivalencia con la V1: contexto de cada clase, momento y asignatura,
prompts completos, plan de preguntas, requisitos de cada herramienta, herramientas sin IA, menú,
fragmentos de entrenamiento y agente. Solo imprime conteos y rutas, nunca textos.

Uso (desde backend/, con el entorno del backend): python ../docs/api-silabo/validador/equivalencia_herramientas.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "backend"))
from ciencia_datos.migrar_v2 import migrar  # noqa: E402
from ciencia_datos.migrar_validador import desde_v2  # noqa: E402
from app.sga.traductor import a_contrato  # noqa: E402
from app.silabo.integridad import SilaboInvalido, cargar_silabo  # noqa: E402
from tests.test_equivalencia_v1 import huellas, normalizar  # noqa: E402


def planos(d, ruta=""):
    if isinstance(d, dict):
        for k, v in d.items():
            yield from planos(v, f"{ruta}.{k}" if ruta else str(k))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            yield from planos(v, f"{ruta}[{i}]")
    else:
        yield ruta, d


def main():
    leer = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    lotes = {
        "Ingeniería 2026": [leer(f) for f in sorted((RAIZ / "datos_cd/silabos_b26c_v2").glob("*.json"))],
        "corpus B26 anterior": [migrar(leer(f)) for d in ("datos_cd/silabos_b26", "datos_cd/silabos_b26b")
                                for f in sorted((RAIZ / d).rglob("*.json"))],
        "ejemplos 2.0": [leer(RAIZ / "docs/api-silabo" / n) for n in ("ejemplo-v2-completo.json", "ejemplo-v2-minimo.json")],
    }
    total_entradas = 0
    for nombre, lote in lotes.items():
        iguales = distintos = no_entran = 0
        rutas = Counter()
        for g in lote:
            try:
                a = normalizar(huellas(cargar_silabo(a_contrato(g))))
            except SilaboInvalido:
                no_entran += 1
                try:  # Debe fallar igual por los dos caminos.
                    cargar_silabo(a_contrato(desde_v2(g)))
                    rutas["entra por el validador y no por el 2.0"] += 1
                except SilaboInvalido:
                    pass
                continue
            b = normalizar(huellas(cargar_silabo(a_contrato(desde_v2(g)))))
            pa, pb = dict(planos(a)), dict(planos(b))
            total_entradas += len(pa)
            dif = {k for k in set(pa) | set(pb) if pa.get(k) != pb.get(k)}
            if dif:
                distintos += 1
                rutas.update({k.split("[")[0].split(".")[0] + "." + k.split(".")[1] if "." in k else k for k in dif})
            else:
                iguales += 1
        print(f"{nombre}: {iguales} idénticos, {distintos} con diferencias, {no_entran} no entran por ninguno de los dos "
              f"(de {len(lote)})", dict(rutas) if rutas else "")
    print("entradas comparadas:", total_entradas)


if __name__ == "__main__":
    main()
