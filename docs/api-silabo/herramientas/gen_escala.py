"""Genera docs/api-silabo/escala-silabo.json (catálogo de la escala) y evaluacion-silabo.schema.json.

Fuente: el texto extraído del docx de la escala (escala.txt). Las rutas al contrato v2.0 se declaran aquí.
Uso: python gen_escala.py <escala.txt> <carpeta docs/api-silabo>
"""
import json
import re
import sys
from pathlib import Path

texto = Path(sys.argv[1]).read_text(encoding="utf-8")
destino = Path(sys.argv[2])

# Filas de preguntas: "III.12 Título¿Pregunta? | M3 · M4 · C | ____ |"
filas = re.findall(r"^((?:I|II|III|IV|V|VI|VII)\.\d+) (.+?)(¿.+?\?) \| (.+?) \| ____", texto, re.M)
assert len(filas) == 60, len(filas)

APARTADOS = {
    "I": ("Perfil del docente", 5),
    "II": ("Presentación del proyecto formativo", 5),
    "III": ("Mapa de formación", 20),
    "IV": ("Momentos del proyecto formativo", 30),
    "V": ("Evaluación", 30),
    "VI": ("Bibliografía", 5),
    "VII": ("Firmas de responsabilidad", 5),
}
PF = "proyecto_formativo"
MC = "metodologias.complementarias"
RUTAS = {
    "I.1": [], "VII.1": [],
    "II.1": ["periodo", f"{PF}.nombre", f"{PF}.uoc", f"{PF}.creditos", f"{PF}.horas", f"{PF}.nivel", f"{PF}.modalidad",
             f"{PF}.formacion", f"{PF}.horario", f"{PF}.prerrequisitos", f"{PF}.correquisitos"],
    "III.1": ["competencia_perfil"], "III.2": ["competencia_pf"], "III.3": ["metacompetencia"],
    "III.4": ["habilidades_blandas"],
    "III.5": ["ejes_transversales.sostenibilidad_ods"], "III.6": ["ejes_transversales.interculturalidad"],
    "III.7": ["ejes_transversales.internacionalizacion"], "III.8": ["ejes_transversales.interdisciplinariedad"],
    "III.9": ["ejes_transversales.emprendimiento"], "III.10": ["ejes_transversales.educacion_financiera"],
    "III.11": ["inclusion.barreras", "inclusion.apoyos"],
    "III.12": ["resultados_aprendizaje[].texto"], "III.13": ["resultados_aprendizaje[].evidencia"],
    "III.14": ["resultados_aprendizaje"], "III.15": ["contribucion_perfil"],
    "III.16": ["problema.descripcion"], "III.17": ["problema.reto"], "III.18": ["problema.producto_final"],
    "III.19": ["pis.nombre", "pis.descripcion"], "III.20": ["pis.aporte"],
    "III.21": ["metodologias.clase_invertida.antes", "metodologias.clase_invertida.durante",
               "metodologias.clase_invertida.despues"],
    "IV.1": ["momentos[].titulo"], "IV.2": ["momentos[].fecha_inicio", "momentos[].fecha_fin"],
    "IV.3": ["momentos[].ra"], "IV.4": ["momentos[].evidencia"],
    "IV.5": ["momentos[].sesiones[].numero", "momentos[].sesiones[].fecha"],
    "IV.6": ["momentos[].sesiones[].docente"],
    "IV.7": ["momentos[].sesiones[].docente.horas", "momentos[].sesiones[].practico.horas",
             "momentos[].sesiones[].autonomo.horas"],
    "IV.8": ["momentos[].sesiones[].practico"], "IV.9": ["momentos[].sesiones[].autonomo"],
    "IV.10": ["momentos[].sesiones[].contenidos"], "IV.11": ["momentos[].recursos"],
    "IV.12": ["momentos[].politica_ia"], "IV.13": ["momentos[].rubrica"],
    "IV.14": ["momentos[].rubrica[].indicador"], "IV.15": ["momentos[].rubrica[].niveles"],
    "V.1": ["rubrica_producto_final"],
    "V.2": ["rubrica_producto_final[].indicador"],
    "V.3": ["rubrica_producto_final[].indicador"], "V.4": ["rubrica_producto_final[].niveles"],
    "V.5": ["evaluacion.proceso"], "V.6": ["evaluacion.agentes"], "V.7": ["evaluacion.retroalimentacion"],
    "V.8": ["evaluacion.metacompetencia"], "V.9": ["evaluacion.gobernanza_ia"], "V.10": ["evaluacion.calificacion"],
    "V.11": ["evaluacion.mejora"], "V.12": ["evaluacion.credencial"],
    "VI.1": ["bibliografia.basica", "bibliografia.complementaria"],
}
METODO = {"III.22": "aprendizaje_basado_problemas", "III.23": "aprendizaje_basado_retos",
          "III.24": "aprendizaje_servicio", "III.25": "aprendizaje_cooperativo", "III.26": "estudio_caso",
          "III.27": "cocreacion_dialogo_saberes", "III.28": "rutinas_destrezas_pensamiento", "III.29": "otra"}
for c, t in METODO.items():
    RUTAS[c] = [f"{MC}[tipo={t}]"]
NA = {"III.5", "III.6", "III.7", "III.8", "III.9", "III.10", "III.12", "III.13", "III.19", "III.20", "V.12", *METODO}
POR_RA = {"III.12", "III.13"}

puntos = []
for codigo, titulo, pregunta, refs in filas:
    ap = codigo.split(".")[0]
    puntos.append({
        "codigo": codigo,
        "apartado": ap,
        "titulo": titulo.strip(" /"),
        "pregunta": pregunta.strip(),
        "referentes": [r.strip() for r in refs.split("·")],
        "rutas": RUTAS[codigo],
        "repetir_por": "ra" if codigo in POR_RA else ("momento" if ap == "IV" else None),
        "admite_na": codigo in NA,
        "fuera_del_contrato": not RUTAS[codigo],
        **({"metodologia": METODO[codigo]} if codigo in METODO else {}),
    })
assert set(RUTAS) == {p["codigo"] for p in puntos}

niveles = re.findall(r"^(\d) (Receptivo|Resolutivo|Reflexivo|Crítico|Cocreativo) \| ([^0-9|].+)$", texto, re.M)
catalogo = {
    "instrumento": "Escala general de evaluación de sílabos",
    "version": "UTI 23/10/2026",
    "niveles": [{"valor": int(v), "nombre": n.lower(), "descriptor": d.strip()} for v, n, d in niveles],
    "codigos": {
        "ND": "No documentado: ausencia comprobada del componente. Vale cero y cuenta en el máximo.",
        "NA": "No aplica: exclusión curricular justificada. Sale del máximo. Solo en los puntos con admite_na y con justificación.",
    },
    "calculo": "Resultado del apartado = puntos obtenidos ÷ (preguntas aplicables × 5) × peso. NA se excluye del denominador; ND vale 0. En IV se suman los puntos de todos los momentos (75 por momento sin NA). Total = suma de los siete apartados.",
    "apartados": [{"codigo": k, "nombre": n, "peso": p} for k, (n, p) in APARTADOS.items()],
    "puntos": puntos,
}
assert len(catalogo["niveles"]) == 5 and sum(a["peso"] for a in catalogo["apartados"]) == 100
(destino / "escala-silabo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# --- esquema del resultado de la evaluación --------------------------------------------------
codigos = [p["codigo"] for p in puntos]
sin_na = [c for c in codigos if c not in NA]
momento_cods = [c for c in codigos if c.startswith("IV.")]
otros = [c for c in codigos if c not in POR_RA and c not in momento_cods]
ap_res = {
    "type": "object", "additionalProperties": False,
    "required": ["peso", "puntos", "maximo", "aplicables", "na", "nd", "por_valorar", "pendientes", "resultado"],
    "properties": {
        "peso": {"type": "number"},
        "puntos": {"type": "integer", "minimum": 0},
        "maximo": {"type": "integer", "minimum": 0, "description": "aplicables × 5"},
        "aplicables": {"type": "integer", "minimum": 0},
        "na": {"type": "integer", "minimum": 0},
        "nd": {"type": "integer", "minimum": 0},
        "por_valorar": {"type": "integer", "minimum": 0},
        "pendientes": {"type": "integer", "minimum": 0},
        "resultado": {"type": ["number", "null"], "minimum": 0,
                      "description": "puntos ÷ maximo × peso, redondeado a 2 decimales. null mientras haya puntos por valorar."},
    },
}
esquema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://uti.edu.ec/generador-recursos/evaluacion-silabo.schema.json",
    "title": "Resultado de la Escala general de evaluación de sílabos · formato 1.0",
    "description": "Valoración de un sílabo con la escala (catálogo en escala-silabo.json). Un punto por pregunta; III.12 y III.13 una vez por RA declarado (o NA para RA2 a RA4 no declarados); IV.1 a IV.15 una vez por momento. No guarda nombres de personas.",
    "type": "object",
    "additionalProperties": False,
    "required": ["formato", "instrumento", "silabo", "revision", "puntos", "apartados", "total", "completa"],
    "properties": {
        "formato": {"const": "1.0"},
        "instrumento": {"const": "UTI 23/10/2026"},
        "silabo": {
            "type": "object", "additionalProperties": False, "required": ["codigo", "version"],
            "properties": {"codigo": {"type": "string", "minLength": 1}, "version": {"type": "string", "minLength": 1}},
        },
        "revision": {
            "type": "object", "additionalProperties": False, "required": ["etapa", "fecha"],
            "properties": {"etapa": {"enum": ["inicio", "seguimiento", "final"]}, "fecha": {"type": "string", "format": "date"}},
        },
        "puntos": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/punto"}},
        "apartados": {
            "type": "object", "additionalProperties": False, "required": list(APARTADOS),
            "properties": {k: {"$ref": "#/$defs/apartado"} for k in APARTADOS},
        },
        "total": {"type": ["number", "null"], "minimum": 0, "maximum": 100,
                  "description": "Suma de los resultados de I a VII. null mientras la evaluación no esté completa."},
        "completa": {"type": "boolean", "description": "true cuando ningún punto queda por valorar (valor null)."},
        "sugerencias_generales": {"type": "string"},
    },
    "$defs": {
        "apartado": ap_res,
        "punto": {
            "type": "object", "additionalProperties": False,
            "required": ["codigo", "valor", "fuente", "justificacion", "sugerencia", "pendiente"],
            "properties": {
                "codigo": {"enum": codigos},
                "ra": {"type": "string", "pattern": "^RA[1-4]$"},
                "momento": {"type": "integer", "minimum": 1},
                "valor": {"oneOf": [{"type": "integer", "minimum": 1, "maximum": 5}, {"enum": ["ND", "NA"]}, {"type": "null"}],
                          "description": "Nivel 1 a 5, ND (vale 0), NA (fuera del máximo) o null (por valorar)."},
                "fuente": {"enum": ["automatica", "ia", "evaluador"],
                           "description": "automatica: ND o NA que se deducen del JSON; ia: nivel propuesto por el modelo; evaluador: confirmado por una persona."},
                "justificacion": {"type": "string", "description": "Obligatoria no vacía cuando valor es NA."},
                "sugerencia": {"type": "string", "description": "Sugerencia para mejorar (columna de la escala)."},
                "pendiente": {"type": "boolean", "description": "Queda pendiente de aclarar (p. ej. metodología elegida sin actividad)."},
            },
            "allOf": [
                {"if": {"properties": {"valor": {"const": "NA"}}, "required": ["valor"]},
                 "then": {"properties": {"codigo": {"enum": sorted(NA, key=codigos.index)}, "justificacion": {"minLength": 1}}}},
                {"if": {"properties": {"codigo": {"enum": sorted(POR_RA, key=codigos.index)}}},
                 "then": {"required": ["ra"], "not": {"required": ["momento"]}}},
                {"if": {"properties": {"codigo": {"enum": momento_cods}}},
                 "then": {"required": ["momento"], "not": {"required": ["ra"]}}},
                {"if": {"properties": {"codigo": {"enum": otros}}},
                 "then": {"allOf": [{"not": {"required": ["ra"]}}, {"not": {"required": ["momento"]}}]}},
                {"if": {"properties": {"codigo": {"enum": sorted(POR_RA, key=codigos.index)}, "valor": {"const": "NA"}},
                        "required": ["valor"]},
                 "then": {"properties": {"ra": {"not": {"const": "RA1"}}}}},
                {"if": {"properties": {"codigo": {"enum": ["I.1", "VII.1"]}, "valor": {"type": "integer"}}, "required": ["valor"]},
                 "then": {"properties": {"fuente": {"const": "evaluador"}}}},
            ],
        },
    },
}
(destino / "evaluacion-silabo.schema.json").write_text(json.dumps(esquema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("puntos", len(puntos), "admiten NA", len(NA), "fuera del contrato", sum(p["fuera_del_contrato"] for p in puntos))
