"""Genera los ejemplos del contrato v2.0 y el ejemplo de evaluación. Uso: python gen_ejemplos_v2.py <repo V2>"""
import copy
import json
import sys
from pathlib import Path

V2 = Path(sys.argv[1])
DOCS = V2 / "docs" / "api-silabo"
sys.path.insert(0, str(V2 / "backend"))
from app.silabo.escala import calcular, revision_automatica  # noqa: E402

def guardar(nombre, d):
    (DOCS / nombre).write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

v1 = json.loads((DOCS / "ejemplo-completo.json").read_text(encoding="utf-8"))

# ---------------- completo: todos los apartados con dato ----------------
c = {"contrato": "2.0"}
c.update({k: copy.deepcopy(v1[k]) for k in ("facultad", "carrera", "periodo", "proyecto_formativo")})
c["proyecto_formativo"].update(formacion="Grado", prerrequisitos=["Fundamentos de programación"], correquisitos=[])
c["competencia_perfil"] = v1["competencia_perfil"]
c["competencia_pf"] = v1["competencia_pf"]
c["metacompetencia"] = v1["metacompetencia"]
c["habilidades_blandas"] = ["Trabajo colaborativo", "Comunicación asertiva con usuarios", "Autorregulación"]
c["ejes_transversales"] = {
    "sostenibilidad_ods": {"aplica": True, "ods": [9, 11],
                           "descripcion": "La base de datos reduce la pérdida de registros de la cooperativa.",
                           "justificacion_na": ""},
    "interculturalidad": {"aplica": True, "descripcion": "Se recogen los términos que usan los socios para nombrar sus datos.",
                          "justificacion_na": ""},
    "internacionalizacion": {"aplica": True, "tipo": "clase_espejo", "actores": "Docente de una universidad aliada",
                             "actividad": "Clase espejo sobre modelado de datos comunitarios",
                             "producto": "Informe comparado de modelos",
                             "descripcion": "Contraste de casos con otra universidad.", "justificacion_na": ""},
    "interdisciplinariedad": {"aplica": True, "disciplinas": ["Contabilidad", "Gestión comunitaria"],
                              "descripcion": "Contabilidad define los datos financieros que se registran.",
                              "justificacion_na": ""},
    "emprendimiento": {"aplica": False, "descripcion": "",
                       "justificacion_na": "El PF no prevé propuestas de valor; se trabaja en el PIS del nivel siguiente."},
    "educacion_financiera": {"aplica": True, "descripcion": "Se estima el costo de mantener la base de datos.",
                             "justificacion_na": ""},
}
c["inclusion"] = ("Barreras: estudiantes sin computador propio. Apoyos: laboratorio abierto y materiales "
                  "accesibles en el aula virtual.")
c["contribucion_perfil"] = "El PF desarrolla el diseño de soluciones de información que pide el perfil de egreso."
c["resultados_aprendizaje"] = copy.deepcopy(v1["resultados_aprendizaje"])
c["problema"] = copy.deepcopy(v1["problema"])
c["pis"] = {"aplica": True, "nombre": v1["pis"]["nombre"],
            "descripcion": "Los PF del nivel construyen juntos el sistema de información de la cooperativa.",
            "aporte": v1["pis"]["aporte"] + " Entrega en la semana 8, coordinada con Programación web.",
            "justificacion_na": ""}
c["metodologias"] = {
    "clase_invertida": {"antes": "Leen y ven un video corto antes de cada sesión.",
                        "durante": "Prueba breve de comprensión y aplicación al caso.",
                        "despues": "Reflexión escrita sobre lo que cambiarían del modelo."},
    "complementarias": [
        {"tipo": "aprendizaje_basado_problemas", "nombre": "Aprendizaje basado en problemas (ABP)",
         "justificacion": "El problema de la cooperativa guía el modelado.", "aplicada_en": ["M1-S1", "M2-S4"]},
        {"tipo": "estudio_caso", "nombre": "Estudio de caso",
         "justificacion": "El caso de inventario muestra errores típicos de cardinalidad.", "aplicada_en": ["M1-S2"]},
    ],
}
c["momentos"] = copy.deepcopy(v1["momentos"])
c["rubrica_producto_final"] = copy.deepcopy(v1["rubrica_producto_final"])
c["evaluacion"] = {
    "proceso": {"inicial": "Diagnóstico de modelado en la sesión 1.", "seguimiento": "Revisión del diagrama y de la base.",
                "final": "Defensa del producto con la cooperativa."},
    "agentes": {"autoevaluacion": "Lista de cotejo al cierre de cada momento.",
                "coevaluacion": "Revisión entre parejas del diagrama.",
                "heteroevaluacion": "Rúbrica del docente para cada evidencia."},
    "retroalimentacion": "Comentarios escritos con nivel alcanzado y una mejora concreta por evidencia.",
    "metacompetencia": "Bitácora de decisiones éticas sobre los datos de terceros.",
    "gobernanza_ia": "Declaración del uso de IA y contraste de sus respuestas con la documentación.",
    "calificacion": {"componentes": [{"nombre": "Evidencia del momento 1", "porcentaje": 30, "momento": 1},
                                     {"nombre": "Evidencia del momento 2", "porcentaje": 30, "momento": 2},
                                     {"nombre": "Producto final", "porcentaje": 40, "momento": None}],
                     "reglas": "Nota sobre 10; cada evidencia se califica con su rúbrica."},
    "mejora": "Los resultados por RA se revisan con la coordinación al final del periodo.",
    "credencial": {"aplica": False, "nombre": "", "desempeno": "", "evidencias": "", "criterios": "",
                   "justificacion_na": "El PF no forma parte de una microcredencial."},
}
c["bibliografia"] = copy.deepcopy(v1["bibliografia"])
guardar("ejemplo-v2-completo.json", c)

# ---------------- mínimo: claves obligatorias, con ND y NA ----------------
m = copy.deepcopy(c)
m["proyecto_formativo"] = {k: m["proyecto_formativo"][k] for k in ("codigo", "nombre", "version", "aprobado", "nivel")}
m["proyecto_formativo"].update(uoc="", modalidad="", formacion="", creditos=None, horas=None, horario=[],
                               prerrequisitos=[], correquisitos=[])
m["competencia_pf"] = ""
m["metacompetencia"] = ""
m["habilidades_blandas"] = []
for k in m["ejes_transversales"]:
    m["ejes_transversales"][k] = {"aplica": False, "descripcion": "", "justificacion_na": "No pertinente al PF."}
m["ejes_transversales"]["sostenibilidad_ods"]["ods"] = []
m["ejes_transversales"]["interdisciplinariedad"]["disciplinas"] = []
m["ejes_transversales"]["internacionalizacion"].update(tipo=None, actores="", actividad="", producto="")
m["inclusion"] = ""
m["contribucion_perfil"] = ""
m["resultados_aprendizaje"] = [{"id": "RA1", "texto": c["resultados_aprendizaje"][0]["texto"], "evidencia": ""}]
m["pis"] = {"aplica": False, "nombre": "", "descripcion": "", "aporte": "", "justificacion_na": "El PF no forma parte de un PIS."}
m["metodologias"] = {"clase_invertida": {"antes": "", "durante": "", "despues": ""}, "complementarias": []}
mo = m["momentos"][0]
mo.update(ra=["RA1"], evidencia="", politica_ia="", recursos="", rubrica=[])
mo["sesiones"] = [mo["sesiones"][0]]
m["momentos"] = [mo]
m["rubrica_producto_final"] = []
m["evaluacion"] = {"proceso": {"inicial": "", "seguimiento": "", "final": ""},
                   "agentes": {"autoevaluacion": "", "coevaluacion": "", "heteroevaluacion": ""},
                   "retroalimentacion": "", "metacompetencia": "", "gobernanza_ia": "",
                   "calificacion": {"componentes": [], "reglas": ""}, "mejora": "",
                   "credencial": m["evaluacion"]["credencial"]}
m["bibliografia"] = {"basica": [], "complementaria": []}
guardar("ejemplo-v2-minimo.json", m)

# ---------------- evaluación de ejemplo: revisión automática + valoración ----------------
ev = revision_automatica(c, etapa="inicio", fecha="2026-11-18")
niveles = iter([3, 4, 3, 2, 4, 3, 5, 3, 4, 2, 3, 4, 3, 3, 4, 2, 3] * 10)
for p in ev["puntos"]:
    if p["valor"] is None:
        p["valor"] = next(niveles)
        p["fuente"] = "evaluador" if p["codigo"] in ("I.1", "VII.1") else "ia"
        if p["valor"] <= 2:
            p["sugerencia"] = (p["sugerencia"] + "; " if p["sugerencia"] else "") + "Precisar el componente con criterios verificables."
ev.update(calcular(ev["puntos"]))
ev["sugerencias_generales"] = "Ejemplo ilustrativo: los niveles no corresponden a una revisión real."
guardar("ejemplo-evaluacion.json", ev)
print("total", ev["total"], {k: v["resultado"] for k, v in ev["apartados"].items()})
