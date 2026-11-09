"""Prueba de calidad: ¿alcanza el sílabo para generar herramientas de nivel universitario?

Genera, con el servidor de IA de la universidad (Qwen3-8B) y SOLO con texto del
sílabo, un cuestionario de 8 ítems y una ficha de clase para dos clases reales;
aplica las verificaciones deterministas del spec (§10.1) y el revisor a ciegas
(§10.2). Guarda todo en pruebas/resultados/<fecha>.json para la revisión humana.

Uso:
    .venv/Scripts/python pruebas/prueba_calidad.py
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
import urllib.request
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

URL = "http://172.16.8.69:8000/v1/chat/completions"
MODELO = "Qwen/Qwen3-8B-AWQ"
SALIDA = Path(__file__).resolve().parent / "resultados"
random.seed(7)

# ─── Contexto: SOLO texto del sílabo (transcrito tal cual del PDF) ───────────

CLASES = {
    "datos_M3S4": {
        "asignatura": "Análisis de Datos y Estadística para Ingeniería", "carrera": "Software", "nivel": 3,
        "competencia_pf": "Analiza datos estructurados provenientes de bases de datos organizacionales mediante "
            "métodos estadísticos, para fundamentar la toma de decisiones estratégicas en la resolución de problemas "
            "de ingeniería, garantizando la integridad de la información con actuación ética, pensamiento sociocrítico "
            "y comunicación efectiva de los resultados.",
        "problema": "En Ecuador crece la dependencia de servicios digitales; en el primer semestre de 2025 EcuCERT "
            "reportó 220.228 direcciones IP con incidentes o vulnerabilidades. El PIS aborda casos de monitoreo de "
            "seguridad digital con datos controlados o simulados.",
        "reto": "¿Cómo estructurar y modelar estadísticamente los datos de eventos de red para fundamentar el motor "
            "lógico y predictivo de una solución de software orientada al monitoreo de la seguridad digital en Ecuador?",
        "momento": "Momento 3: Resolución del Problema - Inferencia Estadística para la Detección de Anomalías",
        "ra": {"RA3": "Contrasta hipótesis operativas y estima parámetros poblacionales utilizando estadística "
            "inferencial clásica (pruebas paramétricas y ANOVA), para validar el comportamiento de los datos y "
            "fundamentar las decisiones algorítmicas."},
        "evidencia": "Definición Inferencial de Umbrales de Seguridad: documento técnico que utiliza pruebas de "
            "hipótesis e intervalos de confianza (procesados en JASP) para diferenciar estadísticamente picos de "
            "tráfico normales de posibles ataques (ej. DDoS) y justifica numéricamente los valores de corte del algoritmo.",
        "clase": {
            "fecha": "jueves 29/10/2026", "id": "M3-S4",
            "contenidos": ["Hipótesis estadísticas"],
            "docente": "Sobre pruebas de hipótesis y análisis de varianza (ANOVA).",
            "practico": "Ejecución de pruebas T y ANOVA clásicas en JASP. Uso de Numiqo para verificar estadísticos "
                "críticos (Z o F) de forma manual.",
            "autonomo": "Redacción del reporte argumentando la elección de las pruebas estadísticas.",
            "clases_previas": "Lógica del muestreo, estimación de parámetros e intervalos de confianza; formulación "
                "de H0/H1, valor p y verificación de supuestos (Shapiro-Wilk, Levene).",
        },
        "rubrica": [
            ("Aplicación de pruebas de hipótesis e intervalos de confianza en JASP",
             "Resolutivo: aplica correctamente las pruebas de hipótesis y calcula los intervalos de confianza en JASP. "
             "Reflexivo: analiza los resultados explicando la relación entre los intervalos y el comportamiento de la red. "
             "Crítico: evalúa la idoneidad de las pruebas seleccionadas, validando el rigor metodológico."),
            ("Diferenciación estadística de tráfico normal vs. posibles ataques",
             "Resolutivo: establece la diferencia estadística entre picos normales y posibles ataques. "
             "Reflexivo: argumenta los criterios técnicos y estadísticos que diferencian un pico legítimo de un ataque. "
             "Crítico: juzga la precisión de la diferenciación anticipando falsos positivos o negativos."),
        ],
        "politica_ia": "Se permite IA generativa como asistente metodológico para interpretar estadísticos de prueba; "
            "el estudiante audita críticamente las interpretaciones y asume la autoría total del reporte.",
        "entregables": ["Reporte que argumenta la elección de las pruebas estadísticas (trabajo autónomo)",
                        "Evidencia del momento: umbrales de seguridad del proyecto"],
        "software": ["JASP", "Numiqo"],
    },
    "tic_M3S1": {
        "asignatura": "Tecnologías de la Información en Ingeniería", "carrera": "Software", "nivel": 2,
        "competencia_pf": "(vacía en el sílabo) Competencia del perfil de egreso: diseña la estructura y la "
            "arquitectura de sistemas de software, definiendo la disposición de los componentes de hardware y software "
            "y la comunicación entre ellos, para garantizar el correcto funcionamiento.",
        "problema": "En Ecuador crece la dependencia de servicios digitales; EcuCERT identificó 36 sistemas vulnerables "
            "en Ambato. El PIS aborda soluciones de monitoreo y gestión de la seguridad digital con casos asignados.",
        "reto": "Avanzar desde el diseño lógico de soluciones hacia su implementación funcional: procesar datos, aplicar "
            "reglas de decisión, identificar condiciones anómalas y registrar eventos de seguridad.",
        "momento": "Momento 3: Resolución / implementación del problema del contexto",
        "ra": {"RA2": "Mejora los procesos de ingeniería a través de las tecnologías de la información.",
               "RA3": "Evalúa soluciones de tecnología de la información para la ingeniería."},
        "evidencia": "Informe de evaluación de seguridad y viabilidad de la configuración tecnológica seleccionada para "
            "el PIS, con identificación de riesgos, matriz de controles y recomendaciones de mejora técnica, ética y legal.",
        "clase": {
            "fecha": "jueves 22/10/2026", "id": "M3-S1",
            "contenidos": ["Ciberseguridad en ingeniería",
                           "Casos de estudio de uso de tecnologías de la información en ingeniería"],
            "docente": "Recuperación de las configuraciones tecnológicas seleccionadas; explicación de amenazas, "
                "vulnerabilidades y riesgos; análisis de confidencialidad, integridad y disponibilidad; estudio guiado "
                "de un incidente de seguridad digital; identificación de controles preventivos y correctivos; reflexión "
                "sobre su aplicación al caso del PIS. Asincrónico: recursos sobre amenazas digitales, gestión de "
                "accesos, respaldos, actualizaciones y protección de datos; preguntas para relacionar vulnerabilidades "
                "con controles.",
            "practico": "(sin horas práctico-experimentales en esta clase)",
            "autonomo": "TAREA 3 – Análisis de un incidente de seguridad digital: descripción de un incidente real "
                "documentado o simulado; identificación de activos, amenazas, vulnerabilidades y consecuencias; relación "
                "con confidencialidad, integridad y disponibilidad; propuesta de controles aplicables al contexto del PIS.",
            "clases_previas": "Ecosistema TI (hardware, software, sistemas operativos, almacenamiento, conectividad); "
                "criterios para evaluar y seleccionar soluciones TI; matriz de decisión.",
        },
        "rubrica": [
            ("Identificación y valoración de riesgos (amenazas, vulnerabilidades e impactos)",
             "Resolutivo: identifica activos, amenazas y vulnerabilidades; organiza los riesgos por probabilidad e impacto. "
             "Reflexivo: relaciona amenazas, vulnerabilidades y consecuencias con confidencialidad, integridad y "
             "disponibilidad e interpreta niveles de riesgo. Crítico: evalúa riesgos con criterios de probabilidad e "
             "impacto, prioriza situaciones críticas y argumenta consecuencias para la continuidad."),
            ("Selección de controles de seguridad",
             "Resolutivo: propone controles básicos (autenticación, respaldo, actualización, protección de datos). "
             "Reflexivo: relaciona cada control con amenazas y vulnerabilidades específicas. Crítico: justifica "
             "controles por eficacia, costo, viabilidad y protección de datos, y prioriza acciones."),
        ],
        "politica_ia": "Se permite la IA como apoyo para identificar riesgos, comparar controles y consultar conceptos; "
            "los hallazgos se verifican con fuentes técnicas y normativas; no se introducen credenciales ni datos "
            "personales en herramientas externas.",
        "entregables": ["TAREA 3: análisis de un incidente de seguridad digital del contexto del PIS",
                        "Evidencia del momento: informe de evaluación de seguridad de la configuración del PIS"],
        "software": [],
    },
}

# Perfil Fundamentación (niveles 1-3 de la malla, spec §6.2): 8 ítems = 2 lotes de 4.
LOTES = [["receptivo", "resolutivo", "resolutivo", "reflexivo"],
         ["receptivo", "resolutivo", "reflexivo", "critico"]]

REGLAS = """Reglas obligatorias:
- Nivel universitario. Desde "resolutivo", el enunciado parte de una situación profesional concreta (datos, sistema, caso), no de una definición.
- Usa como contexto el problema del territorio y el PIS cuando encaje, con datos FICTICIOS declarados como tales.
- 4 opciones, exactamente 1 correcta. Cada distractor responde a un error conceptual o de procedimiento real; prohibido "todas las anteriores" y "ninguna de las anteriores".
- Cada opción lleva una justificación: por qué es correcta o por qué alguien la elegiría y en qué se equivoca.
- Desde "reflexivo": al menos dos pasos de razonamiento, listados en "razonamiento".
- No resuelvas ni des borradores de los entregables de la asignatura (tareas, reportes, evidencias del momento): trabaja los mismos contenidos con otros casos y otros datos.
- Escala de niveles: receptivo (reconocer, describir), resolutivo (aplicar un procedimiento en una situación nueva), reflexivo (analizar, relacionar, explicar), critico (evaluar con criterios, justificar decisiones).
- Español neutro y técnico."""


def contexto(c: dict) -> str:
    rub = "\n".join(f"- {i}: {d}" for i, d in c["rubrica"])
    ras = "\n".join(f"- {k}: {v}" for k, v in c["ra"].items())
    k = c["clase"]
    return f"""ASIGNATURA: {c['asignatura']} · carrera {c['carrera']} · {c['nivel']}.º nivel
COMPETENCIA: {c['competencia_pf']}
PROBLEMA DEL TERRITORIO: {c['problema']}
RETO: {c['reto']}
{c['momento']}
RESULTADOS DE APRENDIZAJE:
{ras}
EVIDENCIA DEL MOMENTO: {c['evidencia']}
CLASE {k['id']} ({k['fecha']}):
- Contenidos: {'; '.join(k['contenidos'])}
- Con el docente: {k['docente']}
- Práctico-experimental: {k['practico']}
- Trabajo autónomo: {k['autonomo']}
- Clases anteriores del momento: {k['clases_previas']}
RÚBRICA DEL MOMENTO (indicadores):
{rub}
POLÍTICA DE IA DEL MOMENTO: {c['politica_ia']}
ENTREGABLES QUE NO SE DEBEN RESOLVER: {'; '.join(c['entregables'])}"""


# ─── Esquemas (spec §8.2) ────────────────────────────────────────────────────

def esquema_lote(niveles: list[str]) -> dict:
    item = {
        "type": "object",
        "properties": {
            "nivel": {"type": "string", "enum": ["receptivo", "resolutivo", "reflexivo", "critico"]},
            "ra": {"type": "string"},
            "contenido": {"type": "string"},
            "contexto": {"type": "string"},
            "enunciado": {"type": "string"},
            "opciones": {"type": "array", "minItems": 4, "maxItems": 4, "items": {
                "type": "object",
                "properties": {"texto": {"type": "string"}, "justificacion": {"type": "string"}},
                "required": ["texto", "justificacion"]}},
            "correcta": {"type": "integer", "minimum": 0, "maximum": 3},
            "razonamiento": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["nivel", "ra", "contenido", "contexto", "enunciado", "opciones", "correcta", "razonamiento"],
    }
    return {"type": "object", "properties": {"items": {"type": "array", "minItems": len(niveles),
                                                         "maxItems": len(niveles), "items": item}},
            "required": ["items"]}


ESQUEMA_FICHA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "objetivo": {"type": "string"},
        "ideas_clave": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "string"}},
        "ejemplo_resuelto": {"type": "object", "properties": {
            "situacion": {"type": "string"},
            "pasos": {"type": "array", "minItems": 3, "maxItems": 7, "items": {"type": "string"}},
            "conclusion": {"type": "string"}}, "required": ["situacion", "pasos", "conclusion"]},
        "errores_frecuentes": {"type": "array", "minItems": 3, "maxItems": 4, "items": {"type": "string"}},
        "relacion_con_el_ra": {"type": "string"},
        "preguntas_autocomprobacion": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "string"}},
    },
    "required": ["titulo", "objetivo", "ideas_clave", "ejemplo_resuelto", "errores_frecuentes",
                 "relacion_con_el_ra", "preguntas_autocomprobacion"],
}

ESQUEMA_REVISOR = {
    "type": "object",
    "properties": {
        "respuesta": {"type": "integer", "minimum": 0, "maximum": 3},
        "otra_opcion_defendible": {"type": "boolean"},
        "nivel_real": {"type": "string", "enum": ["receptivo", "resolutivo", "reflexivo", "critico"]},
        "resuelve_un_entregable": {"type": "boolean"},
        "motivo": {"type": "string"},
    },
    "required": ["respuesta", "otra_opcion_defendible", "nivel_real", "resuelve_un_entregable", "motivo"],
}


# ─── Cliente ─────────────────────────────────────────────────────────────────

def llamar(mensajes, esquema, nombre, pensar=False, max_tokens=3500, temperatura=0.4):
    cuerpo = {"model": MODELO, "messages": mensajes, "max_tokens": max_tokens, "temperature": temperatura,
              "response_format": {"type": "json_schema", "json_schema": {"name": nombre, "schema": esquema}},
              "chat_template_kwargs": {"enable_thinking": pensar}}
    inicio = time.time()
    req = urllib.request.Request(URL, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"})
    datos = json.load(urllib.request.urlopen(req, timeout=600))
    msg = datos["choices"][0]["message"]["content"]
    contenido = re.sub(r"<think>.*?</think>", "", msg or "", flags=re.S).strip()
    return json.loads(contenido), datos.get("usage", {}), round(time.time() - inicio, 1)


# ─── Verificación determinista (spec §10.1) ─────────────────────────────────

PROHIBIDAS = re.compile(r"todas las anteriores|ninguna de las anteriores", re.I)


def verificar(items: list[dict], niveles_pedidos: list[str]) -> list[list[str]]:
    fallos = []
    for n, (it, pedido) in enumerate(zip(items, niveles_pedidos)):
        f = []
        textos = [o["texto"].strip().lower() for o in it["opciones"]]
        if len(set(textos)) < 4:
            f.append("opciones duplicadas")
        if any(PROHIBIDAS.search(o["texto"]) for o in it["opciones"]):
            f.append("frase prohibida")
        if it["nivel"] != pedido:
            f.append(f"nivel {it['nivel']} ≠ pedido {pedido}")
        if pedido != "receptivo" and len(it["contexto"].split()) < 15:
            f.append("sin contexto profesional")
        if pedido in ("reflexivo", "critico") and len(it["razonamiento"]) < 2:
            f.append("menos de 2 pasos de razonamiento")
        for m, otro in enumerate(items[:n]):
            if SequenceMatcher(None, it["enunciado"], otro["enunciado"]).ratio() >= 0.8:
                f.append(f"casi duplicado del ítem {m + 1}")
        fallos.append(f)
    return fallos


# ─── Prueba ──────────────────────────────────────────────────────────────────

def probar(clave: str, c: dict) -> dict:
    ctx = contexto(c)
    sistema = ("Eres el agente de la Facultad de Ingenierías de la Universidad Indoamérica. Generas herramientas de "
               "estudio para estudiantes universitarios usando SOLO la información del sílabo que se te da.\n" + REGLAS)
    resultado = {"clase": clave, "contexto": ctx, "lotes": [], "ficha": None}
    previos: list[str] = []
    for niveles in LOTES:
        pedido = (f"{ctx}\n\nGenera {len(niveles)} ítems de opción múltiple para la clase {c['clase']['id']}, "
                  f"en este orden de niveles: {', '.join(niveles)}. RA: {', '.join(c['ra'])}.")
        if previos:
            pedido += "\nNo repitas estos enunciados ya generados:\n- " + "\n- ".join(p[:140] for p in previos)
        datos, uso, seg = llamar([{"role": "system", "content": sistema}, {"role": "user", "content": pedido}],
                                 esquema_lote(niveles), "cuestionario")
        items = datos["items"]
        previos += [i["enunciado"] for i in items]
        resultado["lotes"].append({"niveles": niveles, "items": items, "uso": uso, "segundos": seg,
                                   "verificacion": verificar(items, niveles)})
        print(f"  {clave}: lote de {len(items)} ítems en {seg} s, {uso.get('total_tokens')} tokens", flush=True)

    # Revisor a ciegas: opciones barajadas, sin clave ni justificaciones.
    for lote in resultado["lotes"]:
        lote["revision"] = []
        for it in lote["items"]:
            orden = list(range(4))
            random.shuffle(orden)
            opciones = "\n".join(f"{k}) {it['opciones'][i]['texto']}" for k, i in enumerate(orden))
            pedido = (f"{ctx}\n\nResuelve este ítem como un experto. Indica la opción correcta (0-3), si alguna otra "
                      f"opción es también defendible, el nivel cognitivo real del ítem y si el ítem resuelve alguno de "
                      f"los entregables listados.\n\nCONTEXTO DEL ÍTEM: {it['contexto']}\nENUNCIADO: {it['enunciado']}\n"
                      f"OPCIONES:\n{opciones}")
            datos, uso, seg = llamar([{"role": "system", "content": "Eres un revisor académico riguroso."},
                                      {"role": "user", "content": pedido}],
                                     ESQUEMA_REVISOR, "revision", pensar=True, max_tokens=4000, temperatura=0)
            datos["coincide_con_clave"] = orden[datos["respuesta"]] == it["correcta"]
            datos["segundos"] = seg
            lote["revision"].append(datos)
            print(f"    revisor: coincide={datos['coincide_con_clave']} defendible={datos['otra_opcion_defendible']} "
                  f"({seg} s)", flush=True)

    datos, uso, seg = llamar(
        [{"role": "system", "content": sistema},
         {"role": "user", "content": f"{ctx}\n\nGenera la FICHA DE ESTUDIO de la clase {c['clase']['id']}: ideas "
                                     f"clave, un ejemplo resuelto paso a paso con datos ficticios (distinto de los "
                                     f"entregables), errores frecuentes, relación con el RA y 3 preguntas de "
                                     f"autocomprobación."}],
        ESQUEMA_FICHA, "ficha")
    resultado["ficha"] = {"contenido": datos, "uso": uso, "segundos": seg}
    print(f"  {clave}: ficha en {seg} s", flush=True)
    return resultado


def main() -> int:
    SALIDA.mkdir(exist_ok=True)
    resultados = [probar(k, c) for k, c in CLASES.items()]
    archivo = SALIDA / f"{datetime.now():%Y%m%d-%H%M}.json"
    archivo.write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Resultados: {archivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
