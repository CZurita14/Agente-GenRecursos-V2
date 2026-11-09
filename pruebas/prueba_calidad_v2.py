"""Prueba de calidad, segunda ronda: mismo sílabo, generador corregido.

Cambios frente a prueba_calidad.py (ronda 1):
1. Esquema con campo "pregunta" separado; verificación de que termine en "?" y no
   contenga las opciones.
2. Un foco de evaluación distinto por ítem, derivado de la clase y su rúbrica.
3. "El código calcula, la IA redacta": en clases cuantitativas, Python calcula los
   resultados (t, F, p, Levene, Shapiro-Wilk, IC) y el modelo solo redacta.
4. Revisor con razonamiento real: piensa en texto libre y al final da el JSON.
5. Integridad: los casos usan organizaciones ficticias distintas del caso del PIS.

Uso:
    .venv/Scripts/python pruebas/prueba_calidad_v2.py
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

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prueba_calidad import CLASES, ESQUEMA_FICHA, LOTES, MODELO, SALIDA, URL, contexto  # noqa: E402

random.seed(11)

REGLAS = """Reglas obligatorias:
- Nivel universitario. Desde "resolutivo", el ítem parte de una situación profesional concreta con datos.
- El caso del PIS y del problema del territorio es el trabajo del estudiante: NO lo uses como caso. Usa organizaciones ficticias distintas del mismo sector (otra empresa, hospital, cooperativa, colegio) y decláralas ficticias.
- "pregunta" es una pregunta completa que termina en "?" y NO incluye las opciones.
- 4 opciones sin letras ni numeración, exactamente 1 correcta. Cada distractor responde a un error conceptual o de procedimiento real; prohibido "todas las anteriores" y "ninguna de las anteriores".
- Cada opción lleva su justificación.
- Desde "reflexivo": al menos dos pasos de razonamiento en "razonamiento".
- Si se te entregan RESULTADOS CALCULADOS, úsalos tal cual; no inventes otros números.
- No resuelvas ni des borradores de los entregables de la asignatura.
- Niveles: receptivo (reconocer, describir), resolutivo (aplicar un procedimiento a una situación nueva), reflexivo (analizar, relacionar, interpretar resultados), critico (evaluar con criterios, juzgar decisiones o conclusiones).
- Español neutro y técnico."""

NIVELES = [n for lote in LOTES for n in lote]


# ─── 3. El código calcula ────────────────────────────────────────────────────

def escenario_calculado() -> tuple[str, list[str]]:
    """Tráfico (Mbps) de tres segmentos de red de una cooperativa ficticia; resultados exactos."""
    rng = np.random.default_rng(29)
    a, b, c = rng.normal(118, 14, 30), rng.normal(121, 14, 30), rng.normal(139, 15, 30)
    sw = [stats.shapiro(x).pvalue for x in (a, b, c)]
    lev = stats.levene(a, b, c)
    anova = stats.f_oneway(a, b, c)
    f_crit = stats.f.ppf(0.95, 2, 87)
    t_ab = stats.ttest_ind(a, b)
    ic_c = stats.t.interval(0.95, 29, loc=c.mean(), scale=stats.sem(c))
    tabla = (f"Cooperativa de ahorro ficticia 'Coop. Andina': tráfico de red en Mbps, 30 mediciones por segmento.\n"
             f"Segmento A (oficinas): media {a.mean():.1f}, desv. {a.std(ddof=1):.1f}\n"
             f"Segmento B (cajeros): media {b.mean():.1f}, desv. {b.std(ddof=1):.1f}\n"
             f"Segmento C (servidores web): media {c.mean():.1f}, desv. {c.std(ddof=1):.1f}\n"
             f"Shapiro-Wilk p: A={sw[0]:.3f}, B={sw[1]:.3f}, C={sw[2]:.3f}\n"
             f"Levene: estadístico={lev.statistic:.2f}, p={lev.pvalue:.3f}\n"
             f"ANOVA de un factor: F(2, 87)={anova.statistic:.2f}, p={anova.pvalue:.2g}; F crítico (α=0,05)={f_crit:.2f}\n"
             f"Prueba t A vs B (varianzas iguales): t(58)={t_ab.statistic:.2f}, p={t_ab.pvalue:.3f}\n"
             f"IC 95 % de la media de C: [{ic_c[0]:.1f}; {ic_c[1]:.1f}]")
    hechos = [
        f"Normalidad: todos los p de Shapiro-Wilk {'superan' if min(sw) > 0.05 else 'NO todos superan'} 0,05.",
        f"Homogeneidad de varianzas: Levene p={lev.pvalue:.3f} {'> 0,05, se asume homogeneidad' if lev.pvalue > 0.05 else '< 0,05, no se asume'}.",
        f"ANOVA: F={anova.statistic:.2f} {'>' if anova.statistic > f_crit else '<'} F crítico {f_crit:.2f}; "
        f"{'se rechaza' if anova.pvalue < 0.05 else 'no se rechaza'} H0 de medias iguales.",
        f"El ANOVA no dice qué segmentos difieren; para eso hace falta una prueba post hoc (por ejemplo, Tukey).",
        f"t A vs B: p={t_ab.pvalue:.3f} {'< 0,05, diferencia significativa' if t_ab.pvalue < 0.05 else '> 0,05, sin evidencia de diferencia'}.",
        f"El IC 95 % de C no contiene la media de A ({a.mean():.1f}).",
    ]
    return tabla, hechos


# ─── Cliente ─────────────────────────────────────────────────────────────────

def llamar(mensajes, esquema=None, nombre="salida", pensar=False, max_tokens=3500, temperatura=0.4,
           penalizacion=None):
    cuerpo = {"model": MODELO, "messages": mensajes, "max_tokens": max_tokens, "temperature": temperatura,
              "chat_template_kwargs": {"enable_thinking": pensar}}
    if penalizacion:  # evita el bucle de espacios de la salida guiada por esquema (medido el 2026-10-20)
        cuerpo["repetition_penalty"] = penalizacion
    if esquema:
        cuerpo["response_format"] = {"type": "json_schema", "json_schema": {"name": nombre, "schema": esquema}}
    inicio = time.time()
    req = urllib.request.Request(URL, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json"})
    datos = json.load(urllib.request.urlopen(req, timeout=900))
    texto = datos["choices"][0]["message"]["content"] or ""
    return texto, datos.get("usage", {}), round(time.time() - inicio, 1)


def ultimo_json(texto: str) -> dict:
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S)
    bloques = re.findall(r"\{.*\}", texto, flags=re.S)
    return json.loads(bloques[-1])


# ─── Esquemas ────────────────────────────────────────────────────────────────

ESQUEMA_FOCOS = {"type": "object", "properties": {"focos": {"type": "array", "minItems": 8, "maxItems": 8,
    "items": {"type": "object", "properties": {
        "foco": {"type": "string"}, "usa_resultados_calculados": {"type": "boolean"}},
        "required": ["foco", "usa_resultados_calculados"]}}}, "required": ["focos"]}


def esquema_lote(n: int) -> dict:
    item = {"type": "object", "properties": {
        "nivel": {"type": "string", "enum": ["receptivo", "resolutivo", "reflexivo", "critico"]},
        "ra": {"type": "string"},
        "foco": {"type": "string"},
        "contexto": {"type": "string"},
        "pregunta": {"type": "string", "minLength": 25},
        "opciones": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "object", "properties": {
            "texto": {"type": "string"}, "justificacion": {"type": "string"}}, "required": ["texto", "justificacion"]}},
        "correcta": {"type": "integer", "minimum": 0, "maximum": 3},
        "razonamiento": {"type": "array", "items": {"type": "string"}}},
        "required": ["nivel", "ra", "foco", "contexto", "pregunta", "opciones", "correcta", "razonamiento"]}
    return {"type": "object", "properties": {"items": {"type": "array", "minItems": n, "maxItems": n, "items": item}},
            "required": ["items"]}


# ─── 1. Verificación determinista ampliada ───────────────────────────────────

PROHIBIDAS = re.compile(r"todas las anteriores|ninguna de las anteriores", re.I)
LETRA = re.compile(r"^\s*[A-Da-d1-4][\)\.:-]\s")


def verificar(items: list[dict], niveles: list[str], previos: list[dict]) -> list[list[str]]:
    fallos = []
    for it, pedido in zip(items, niveles):
        f = []
        p = it["pregunta"].strip()
        if not p.endswith("?"):
            f.append("la pregunta no termina en '?'")
        if any(o["texto"].strip()[:25].lower() in p.lower() for o in it["opciones"] if len(o["texto"]) > 10):
            f.append("la pregunta contiene una opción")
        if any(LETRA.match(o["texto"]) for o in it["opciones"]):
            f.append("opciones con letra o número")
        if len({o["texto"].strip().lower() for o in it["opciones"]}) < 4:
            f.append("opciones duplicadas")
        if any(PROHIBIDAS.search(o["texto"]) for o in it["opciones"]):
            f.append("frase prohibida")
        if it["nivel"] != pedido:
            f.append(f"nivel {it['nivel']} ≠ pedido {pedido}")
        if pedido != "receptivo" and len(it["contexto"].split()) < 15:
            f.append("sin contexto profesional")
        if pedido in ("reflexivo", "critico") and len(it["razonamiento"]) < 2:
            f.append("menos de 2 pasos de razonamiento")
        for m, otro in enumerate(previos):
            if SequenceMatcher(None, p.lower(), otro["pregunta"].lower()).ratio() >= 0.75:
                f.append(f"casi duplicado del ítem {m + 1}")
        fallos.append(f)
        previos.append(it)
    return fallos


# ─── Prueba ──────────────────────────────────────────────────────────────────

def probar(clave: str, c: dict) -> dict:
    ctx = contexto(c)
    cuantitativa = bool(c["software"])
    calculado, hechos = escenario_calculado() if cuantitativa else ("", [])
    bloque_calc = (f"\n\nRESULTADOS CALCULADOS (exactos, úsalos tal cual):\n{calculado}\n"
                   f"Conclusiones correctas de esos resultados:\n- " + "\n- ".join(hechos)) if cuantitativa else ""
    sistema = ("Eres el agente de la Facultad de Ingenierías de la Universidad Indoamérica. Generas herramientas de "
               "estudio para estudiantes universitarios usando SOLO la información del sílabo que se te da.\n" + REGLAS)
    r = {"clase": clave, "version": 2, "calculado": calculado, "hechos": hechos, "lotes": []}

    # 2. Focos distintos por ítem
    pedido_focos = (f"{ctx}{bloque_calc}\n\nPropón 8 focos de evaluación DISTINTOS entre sí para esta clase, "
                    f"derivados de sus contenidos, actividades, clases anteriores del momento y los indicadores de la "
                    f"rúbrica. Deben corresponder, en orden, a estos niveles: {', '.join(NIVELES)}. ")
    if cuantitativa:
        pedido_focos += "Al menos 4 deben usar los resultados calculados."
    texto, uso, seg = llamar([{"role": "system", "content": sistema}, {"role": "user", "content": pedido_focos}],
                             ESQUEMA_FOCOS, "focos", max_tokens=1500)
    focos = json.loads(texto)["focos"]
    r["focos"] = focos
    print(f"  {clave}: focos en {seg} s", flush=True)

    previos: list[dict] = []
    for inicio, niveles in ((0, LOTES[0]), (4, LOTES[1])):
        asignados = focos[inicio:inicio + len(niveles)]
        lista = "\n".join(f"{k + 1}. nivel {n} · foco: {f['foco']}" for k, (n, f) in enumerate(zip(niveles, asignados)))
        pedido = f"{ctx}{bloque_calc}\n\nGenera {len(niveles)} ítems, uno por línea de este plan:\n{lista}"
        if previos:
            pedido += "\nYa existen estas preguntas; no las repitas:\n- " + "\n- ".join(p["pregunta"][:140] for p in previos)
        texto, uso, seg = llamar([{"role": "system", "content": sistema}, {"role": "user", "content": pedido}],
                                 esquema_lote(len(niveles)), "cuestionario")
        items = json.loads(texto)["items"]
        ver = verificar(items, niveles, previos)
        r["lotes"].append({"niveles": niveles, "items": items, "uso": uso, "segundos": seg, "verificacion": ver})
        print(f"  {clave}: lote en {seg} s, {uso.get('total_tokens')} tokens; fallos {sum(map(bool, ver))}", flush=True)

    # 4. Revisor con razonamiento: texto libre + JSON final, opciones barajadas y sin clave
    for lote in r["lotes"]:
        lote["revision"] = []
        for it in lote["items"]:
            orden = list(range(4))
            random.shuffle(orden)
            opciones = "\n".join(f"{k}) {it['opciones'][i]['texto']}" for k, i in enumerate(orden))
            pedido = (f"{c['asignatura']} ({c['nivel']}.º nivel).{bloque_calc}\n\nResuelve este ítem como experto. "
                      f"Razona paso a paso y al final responde SOLO un objeto JSON con las claves: respuesta (0-3), "
                      f"otra_opcion_defendible (true/false), nivel_real (receptivo|resolutivo|reflexivo|critico), "
                      f"motivo (una línea).\n\nCONTEXTO: {it['contexto']}\nPREGUNTA: {it['pregunta']}\nOPCIONES:\n{opciones}")
            texto, uso, seg = llamar([{"role": "user", "content": pedido}], pensar=True, max_tokens=6000,
                                     temperatura=0.6)
            try:
                v = ultimo_json(texto)
                v["coincide_con_clave"] = orden[int(v["respuesta"])] == it["correcta"]
            except Exception as e:  # noqa: BLE001
                v = {"error": str(e), "coincide_con_clave": None}
            v["segundos"], v["tokens"] = seg, uso.get("completion_tokens")
            lote["revision"].append(v)
            print(f"    revisor: coincide={v['coincide_con_clave']} defendible={v.get('otra_opcion_defendible')} "
                  f"({seg} s, {v['tokens']} tokens)", flush=True)

    # Ficha
    texto, uso, seg = llamar([{"role": "system", "content": sistema}, {"role": "user", "content":
        f"{ctx}{bloque_calc}\n\nGenera la FICHA DE ESTUDIO de la clase {c['clase']['id']}: ideas clave, un ejemplo "
        f"resuelto paso a paso ({'con los RESULTADOS CALCULADOS, citando sus números' if cuantitativa else 'con una organización ficticia distinta del caso del PIS'}), "
        f"errores frecuentes, relación con el RA y 3 preguntas de autocomprobación."}], ESQUEMA_FICHA, "ficha")
    r["ficha"] = {"contenido": json.loads(texto), "uso": uso, "segundos": seg}
    print(f"  {clave}: ficha en {seg} s", flush=True)
    return r


def main() -> int:
    SALIDA.mkdir(exist_ok=True)
    resultados = [probar(k, c) for k, c in CLASES.items()]
    archivo = SALIDA / f"{datetime.now():%Y%m%d-%H%M}-v2.json"
    archivo.write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Resultados: {archivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
