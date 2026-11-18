"""Convierte sílabos del contrato 1.0 al 2.0 (V3: el sistema solo acepta 2.0).

Los campos que la plantilla anterior no tenía quedan vacíos (ND en la escala). Si el sílabo
de origen no declara PIS, el PIS 2.0 queda como no aplicable con su justificación.

Uso: python migrar_a_v2.py <archivo.json>... (reescribe cada archivo en su lugar).
Solo imprime rutas de archivos, nunca textos del sílabo.
"""
import copy
import json
import sys
import unicodedata
from pathlib import Path

TIPO = [("clase invertida", None), ("problemas", "aprendizaje_basado_problemas"), ("retos", "aprendizaje_basado_retos"),
        ("servicio", "aprendizaje_servicio"), ("cooperativo", "aprendizaje_cooperativo"), ("caso", "estudio_caso"),
        ("cocreacion", "cocreacion_dialogo_saberes"), ("rutinas", "rutinas_destrezas_pensamiento")]
CONOCIDAS = {"contrato", "facultad", "carrera", "periodo", "proyecto_formativo", "competencia_perfil", "competencia_pf",
             "metacompetencia", "resultados_aprendizaje", "problema", "pis", "metodologias", "momentos",
             "rubrica_producto_final", "bibliografia"}
SIN_PIS = "El sílabo de origen (contrato 1.0) no declara PIS."


def plano(x: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", x.lower()) if unicodedata.category(ch) != "Mn")


def migrar(j: dict, *, extras: bool = False) -> dict:
    """Sílabo 1.0 → 2.0. Con `extras` conserva las claves ajenas al contrato (p. ej. el crudo del SGA,
    que el traductor limpia) y los campos derivados de las sesiones; sin él, deja solo el contrato."""
    eje = lambda **x: {"aplica": True, "descripcion": "", "justificacion_na": "", **x}  # noqa: E731
    pf = copy.deepcopy(j["proyecto_formativo"])
    pf.setdefault("uoc", ""); pf.setdefault("modalidad", ""); pf.setdefault("creditos", None)
    pf.setdefault("horas", None); pf.setdefault("horario", [])
    pf.update(formacion="", prerrequisitos=[], correquisitos=[])
    comp = []
    for nombre in j.get("metodologias", []):
        tipo = next((t for k, t in TIPO if k in plano(nombre)), "otra")
        if tipo:
            comp.append({"tipo": tipo, "nombre": nombre, "justificacion": "", "aplicada_en": []})
    pis = j.get("pis")
    pis_v2 = ({"aplica": True, "nombre": pis.get("nombre", ""), "descripcion": "", "aporte": pis.get("aporte", ""),
               "justificacion_na": ""} if isinstance(pis, dict) and pis else
              {"aplica": False, "nombre": "", "descripcion": "", "aporte": "", "justificacion_na": SIN_PIS})
    momentos = copy.deepcopy(j["momentos"])
    for m in momentos:
        m.setdefault("recursos", "")
        if not extras:
            for s in m["sesiones"]:
                for k in ("id", "semana_periodo", "entregables"):
                    s.pop(k, None)
    v2 = {
        "contrato": "2.0", "facultad": j["facultad"], "carrera": j["carrera"], "periodo": j["periodo"],
        "proyecto_formativo": pf, "competencia_perfil": j["competencia_perfil"],
        "competencia_pf": j.get("competencia_pf", ""), "metacompetencia": j.get("metacompetencia", ""),
        "habilidades_blandas": [],
        "ejes_transversales": {"sostenibilidad_ods": eje(ods=[]), "interculturalidad": eje(),
                               "internacionalizacion": eje(tipo=None, actores="", actividad="", producto=""),
                               "interdisciplinariedad": eje(disciplinas=[]), "emprendimiento": eje(),
                               "educacion_financiera": eje()},
        "inclusion": {"barreras": "", "apoyos": ""}, "contribucion_perfil": "",
        "resultados_aprendizaje": j["resultados_aprendizaje"], "problema": j["problema"],
        "pis": pis_v2,
        "metodologias": {"clase_invertida": {"antes": "", "durante": "", "despues": ""}, "complementarias": comp},
        "momentos": momentos, "rubrica_producto_final": j.get("rubrica_producto_final", []),
        "evaluacion": {"proceso": {"inicial": "", "seguimiento": "", "final": ""},
                       "agentes": {"autoevaluacion": "", "coevaluacion": "", "heteroevaluacion": ""},
                       "retroalimentacion": "", "metacompetencia": "", "gobernanza_ia": "",
                       "calificacion": {"componentes": [], "reglas": ""}, "mejora": "",
                       "credencial": {"aplica": True, "nombre": "", "desempeno": "", "evidencias": "", "criterios": "",
                                      "justificacion_na": ""}},
        "bibliografia": {"basica": (j.get("bibliografia") or {}).get("basica", []),
                         "complementaria": (j.get("bibliografia") or {}).get("complementaria", [])},
    }
    if extras:
        v2.update({k: copy.deepcopy(v) for k, v in j.items() if k not in CONOCIDAS})
    return v2


if __name__ == "__main__":
    for ruta in map(Path, sys.argv[1:]):
        j = json.loads(ruta.read_text(encoding="utf-8"))
        if j.get("contrato") == "2.0":
            print("ya es 2.0:", ruta)
            continue
        ruta.write_text(json.dumps(migrar(j, extras=True), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("migrado:", ruta)
