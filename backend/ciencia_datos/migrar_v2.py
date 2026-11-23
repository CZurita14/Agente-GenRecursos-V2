"""Sílabo 1.0 → contrato 2.0. Sin dependencias pesadas: lo usan el lector de PDF y las herramientas de docs/.

Lo que el sílabo no trae queda vacío (ND en la escala). Lo que la plantilla 2026 sí trae
(`leer_apartados_2026`) llena sus claves. La plantilla no tiene columna de justificación de NA,
así que un eje sin fila queda `aplica: true` y vacío (ND), nunca NA.
"""
import copy
import unicodedata

TIPO = [("clase invertida", None), ("problemas", "aprendizaje_basado_problemas"), ("retos", "aprendizaje_basado_retos"),
        ("servicio", "aprendizaje_servicio"), ("cooperativo", "aprendizaje_cooperativo"), ("caso", "estudio_caso"),
        ("cocreacion", "cocreacion_dialogo_saberes"), ("rutinas", "rutinas_destrezas_pensamiento")]
CONOCIDAS = {"contrato", "facultad", "carrera", "periodo", "proyecto_formativo", "competencia_perfil", "competencia_pf",
             "metacompetencia", "resultados_aprendizaje", "problema", "pis", "metodologias", "momentos",
             "rubrica_producto_final", "bibliografia"}
SIN_PIS = "El sílabo de origen (contrato 1.0) no declara PIS."
_EJES = ("sostenibilidad_ods", "interculturalidad", "internacionalizacion", "interdisciplinariedad", "emprendimiento",
         "educacion_financiera")
_EXTRA_EJE = {"sostenibilidad_ods": {"ods": []}, "internacionalizacion": {"tipo": None, "actores": "", "actividad": "",
                                                                          "producto": ""},
              "interdisciplinariedad": {"disciplinas": []}}


def plano(x: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", x.lower()) if unicodedata.category(ch) != "Mn")


def _eje(clave: str, leido: dict | None) -> dict:
    eje = {"aplica": True, "descripcion": "", "justificacion_na": "", **copy.deepcopy(_EXTRA_EJE.get(clave, {}))}
    eje.update({k: v for k, v in (leido or {}).items() if k in eje})
    return eje


def migrar(j: dict, *, apartados: dict | None = None, extras: bool = False) -> dict:
    """Sílabo 1.0 → 2.0. `apartados` son los de la plantilla 2026 (`leer_apartados_2026`). Con `extras`
    conserva las claves ajenas al contrato y los campos derivados de las sesiones."""
    a = apartados or {}
    pf = copy.deepcopy(j["proyecto_formativo"])
    pf.setdefault("uoc", ""); pf.setdefault("modalidad", ""); pf.setdefault("creditos", None)
    pf.setdefault("horas", None); pf.setdefault("horario", [])
    pf.update(formacion=a.get("formacion", ""), prerrequisitos=a.get("prerrequisitos", []),
              correquisitos=a.get("correquisitos", []))
    comp = []
    for nombre in j.get("metodologias", []):
        tipo = next((t for k, t in TIPO if k in plano(nombre)), "otra")
        if tipo:
            comp.append({"tipo": tipo, "nombre": nombre, "justificacion": "", "aplicada_en": []})
    pis = j.get("pis")
    pis_v2 = ({"aplica": True, "nombre": pis.get("nombre", ""), "descripcion": "", "aporte": pis.get("aporte", ""),
               "justificacion_na": ""} if isinstance(pis, dict) and any(pis.values()) else
              {"aplica": False, "nombre": "", "descripcion": "", "aporte": "", "justificacion_na": SIN_PIS})
    momentos = copy.deepcopy(j["momentos"])
    for m in momentos:
        m.setdefault("recursos", "")
        if not extras:
            for s in m["sesiones"]:
                for k in ("id", "semana_periodo", "entregables"):
                    s.pop(k, None)
    ejes = a.get("ejes", {})
    v2 = {
        "contrato": "2.0", "facultad": j["facultad"], "carrera": j["carrera"], "periodo": j["periodo"],
        "proyecto_formativo": pf, "competencia_perfil": j["competencia_perfil"],
        "competencia_pf": j.get("competencia_pf", ""), "metacompetencia": j.get("metacompetencia", ""),
        "habilidades_blandas": a.get("habilidades_blandas", []),
        "ejes_transversales": {k: _eje(k, ejes.get(k)) for k in _EJES},
        # La plantilla 2026 trae un solo texto de inclusión: va en `barreras` hasta que el contrato lo unifique.
        "inclusion": {"barreras": a.get("inclusion", ""), "apoyos": ""},
        "contribucion_perfil": a.get("contribucion_perfil", ""),
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
