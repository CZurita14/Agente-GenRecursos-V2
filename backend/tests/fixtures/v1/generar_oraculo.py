"""Genera el oráculo de equivalencia con el código de la V1 (solo lectura).

Uso, con la V1 como directorio de trabajo (su `app/` es el que se importa):
    cd <V1>/backend && python <V2>/backend/tests/fixtures/v1/generar_oraculo.py --salida <ruta>.json

Lee `tests/fixtures/silabo_datos.json` de la V1, lo valida con `SilaboUTI` de la V1 y
escribe las huellas de todo lo que el sistema produce a partir del sílabo.
No lee `Silabos/`. No usa red ni LLM.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import app  # noqa: E402

V1_BACKEND = Path.cwd().resolve()
if Path(app.__file__).resolve().parent != V1_BACKEND / "app" or V1_BACKEND.parent.name != "Agente-GeneradorRecursos":
    sys.exit(f"El módulo app no es el de la V1: {app.__file__}")

from app.agentes.facultades import cargar_catalogo, cargar_perfiles, enrutar, estilo_para  # noqa: E402
from app.agentes.planificador import perfil_por_nivel, planificar  # noqa: E402
from app.agentes.workers.base import REGLAS_COMUNES  # noqa: E402
from app.agentes.workers.definiciones import DEFINICIONES  # noqa: E402
from app.herramientas.sin_ia import HERRAMIENTAS_SIN_IA, generar_sin_ia  # noqa: E402
from app.llm.prompts import Sello, construir_prompt  # noqa: E402
from app.silabo.contexto import contexto_por_id  # noqa: E402
from app.silabo.menu import construir_menu  # noqa: E402
from app.silabo.modelo import SilaboUTI  # noqa: E402
from ciencia_datos.corpus import fragmentos  # noqa: E402

REPO = V1_BACKEND.parent
CATALOGO = cargar_catalogo(REPO / "kb" / "catalogo.yaml")
PERFILES = cargar_perfiles(REPO / "agentes")


def ambitos(s):
    return (["asignatura"] + [f"M{m.numero}" for m in s.momentos]
            + [x.id for m in s.momentos for x in m.sesiones])


def huellas(s) -> dict:
    perfil = PERFILES[enrutar(s.facultad, CATALOGO, PERFILES)]
    estilo = estilo_para(perfil, s.carrera)
    out = {"contexto": {}, "prompt": {}, "plan": {}, "requisitos": {}, "sin_ia": {}}
    for a in ambitos(s):
        c = contexto_por_id(s, a)
        out["contexto"][a] = c.model_dump(mode="json")
        msgs = construir_prompt(sello=Sello(c.codigo_pf, c.clase_id, c.fecha), instrucciones=REGLAS_COMUNES,
                                contexto=c, estilo=estilo, ya_generado=[], pedido="(pedido)",
                                salida_max=3500, contar=lambda m: 0)
        out["prompt"][a] = [m["content"] for m in msgs]
        tipo = "asignatura" if a == "asignatura" else "momento" if a.startswith("M") and "-" not in a else "clase"
        for h, dfn in DEFINICIONES.items():
            if dfn.ambito == tipo:
                out["requisitos"][f"{h}@{a}"] = dfn.requisitos(c)
        if tipo in ("clase", "momento"):
            out["plan"][a] = [[p.model_dump() for p in lote]
                              for lote in planificar(c, 12, perfil_por_nivel(c.nivel), escenarios=estilo.escenarios)]
        for h, t in HERRAMIENTAS_SIN_IA.items():
            if t == tipo:
                try:
                    out["sin_ia"][f"{h}@{a}"] = generar_sin_ia(h, s, a)
                except ValueError:
                    out["sin_ia"][f"{h}@{a}"] = "ValueError"
    out["menu"] = [x.model_dump(mode="json") for x in construir_menu(s)]
    out["entrenamiento"] = [(f.tipo, f.momento, f.texto) for f in fragmentos(s)]
    out["agente"] = enrutar(s.facultad, CATALOGO, PERFILES)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--salida", required=True)
    args = p.parse_args()
    s = SilaboUTI.model_validate_json((V1_BACKEND / "tests/fixtures/silabo_datos.json").read_bytes())
    h = huellas(s)
    Path(args.salida).write_text(
        json.dumps(h, sort_keys=True, default=str, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("generado con V1", app.__file__, {k: (len(v) if hasattr(v, "__len__") else 1) for k, v in h.items()})
