"""Prueba de calidad, tercera ronda: mismo sílabo y mismo modelo (Qwen3-8B), generador mejorado.

Cambios frente a la ronda 2:
1. Plantillas por nivel (en especial "crítico": evaluar una conclusión o decisión con un error sembrado).
2. Distractores desde errores típicos: cada opción incorrecta declara el error que representa.
3. Revisor opción por opción: juzga cada opción como verdadera o falsa por separado, razonando;
   el ítem es válido solo si hay exactamente una opción verdadera y es la clave.
4. Sobregeneración: 12 ítems por clase; se eligen los 8 mejores respetando 2/3/2/1 por nivel.

Uso:
    .venv/Scripts/python pruebas/prueba_calidad_v3.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prueba_calidad import CLASES, ESQUEMA_FICHA, SALIDA, contexto  # noqa: E402
from prueba_calidad_v2 import (REGLAS, escenario_calculado, llamar, ultimo_json,  # noqa: E402
                               verificar)

# 12 ítems generados (6 lotes de 2: con 4 el modelo a veces entra en un bucle de espacios y corta el JSON)
# → 8 elegidos: 2 receptivo, 3 resolutivo, 2 reflexivo, 1 crítico.
LOTES = [["receptivo", "resolutivo"], ["reflexivo", "critico"],
         ["receptivo", "resolutivo"], ["reflexivo", "critico"],
         ["receptivo", "resolutivo"], ["resolutivo", "reflexivo"]]
TAM_LOTE = 2
PENALIZACION = 1.05  # sin ella el modelo entra en bucles de espacios en la salida guiada
CUPO = {"receptivo": 2, "resolutivo": 3, "reflexivo": 2, "critico": 1}

PLANTILLAS = """Plantillas por nivel (obligatorias):
- receptivo: una situación breve y una pregunta para RECONOCER el concepto o procedimiento que corresponde. Nunca preguntes por un dato que esté escrito en el contexto.
- resolutivo: APLICAR un procedimiento a la situación (elegir y ejecutar el método adecuado a las condiciones dadas, o leer correctamente un resultado para decidir).
- reflexivo: INTERPRETAR un resultado o relacionar dos hechos de la situación (por qué ocurre, qué implica, qué no se puede concluir).
- critico: presenta la CONCLUSIÓN o DECISIÓN de un profesional ficticio que contiene UN error concreto (sobregeneralizar, confundir no rechazar H0 con aceptarla, inferir causa de una asociación, priorizar sin criterio, ignorar un supuesto o una norma). La pregunta pide evaluarla; la opción correcta identifica exactamente ese error. Las incorrectas aprueban la conclusión o señalan un "error" inexistente.
Distractores: cada opción incorrecta representa un error típico distinto y plausible para un estudiante de este nivel; decláralo en "error_que_representa". La correcta lleva "error_que_representa": "ninguno"."""


def esquema_lote(n: int) -> dict:
    opcion = {"type": "object", "properties": {
        "texto": {"type": "string"}, "justificacion": {"type": "string"}, "error_que_representa": {"type": "string"}},
        "required": ["texto", "justificacion", "error_que_representa"]}
    item = {"type": "object", "properties": {
        "nivel": {"type": "string", "enum": ["receptivo", "resolutivo", "reflexivo", "critico"]},
        "ra": {"type": "string"}, "foco": {"type": "string"}, "contexto": {"type": "string"},
        "pregunta": {"type": "string", "minLength": 25},
        "opciones": {"type": "array", "minItems": 4, "maxItems": 4, "items": opcion},
        "correcta": {"type": "integer", "minimum": 0, "maximum": 3},
        "razonamiento": {"type": "array", "items": {"type": "string"}}},
        "required": ["nivel", "ra", "foco", "contexto", "pregunta", "opciones", "correcta", "razonamiento"]}
    return {"type": "object", "properties": {"items": {"type": "array", "minItems": n, "maxItems": n, "items": item}},
            "required": ["items"]}


ESQUEMA_FOCOS = {"type": "object", "properties": {"focos": {"type": "array", "minItems": 12, "maxItems": 12,
    "items": {"type": "string"}}}, "required": ["focos"]}


def revisar(it: dict, encabezado: str) -> dict:
    """Juzga cada opción por separado (sin conocer la clave) y razonando."""
    opciones = "\n".join(f"{k}) {o['texto']}" for k, o in enumerate(it["opciones"]))
    pedido = (f"{encabezado}\n\nCONTEXTO: {it['contexto']}\nPREGUNTA: {it['pregunta']}\nOPCIONES:\n{opciones}\n\n"
              "Juzga CADA opción por separado: ¿es una respuesta correcta y técnicamente exacta a la pregunta? "
              "Sé estricto con la redacción. Razona y al final responde SOLO un objeto JSON: "
              '{"veredictos": [{"opcion": 0, "correcta": true/false, "motivo": "..."}, ... 4 en total], '
              '"nivel_real": "receptivo|resolutivo|reflexivo|critico"}')
    texto, uso, seg = llamar([{"role": "user", "content": pedido}], pensar=True, max_tokens=6500, temperatura=0.6)
    try:
        v = ultimo_json(texto)
        verdaderas = [x["opcion"] for x in v["veredictos"] if x["correcta"]]
        v["valido"] = verdaderas == [it["correcta"]]
        v["opciones_verdaderas"] = verdaderas
    except Exception as e:  # noqa: BLE001
        v = {"error": str(e), "valido": False}
    v["segundos"], v["tokens"] = seg, uso.get("completion_tokens")
    return v


def elegir(items: list[dict]) -> list[dict]:
    """Los 8 mejores respetando el cupo por nivel: primero válidos para el revisor y sin fallos de verificación."""
    elegidos = []
    for nivel, cupo in CUPO.items():
        candidatos = [i for i in items if i["nivel_pedido"] == nivel]
        candidatos.sort(key=lambda i: (not i["revision"]["valido"], len(i["fallos"])))
        elegidos += candidatos[:cupo]
    return elegidos


def probar(clave: str, c: dict) -> dict:
    ctx = contexto(c)
    cuantitativa = bool(c["software"])
    calculado, hechos = escenario_calculado() if cuantitativa else ("", [])
    bloque_calc = (f"\n\nRESULTADOS CALCULADOS (exactos, úsalos tal cual):\n{calculado}\n"
                   f"Conclusiones correctas de esos resultados:\n- " + "\n- ".join(hechos)) if cuantitativa else ""
    sistema = ("Eres el agente de la Facultad de Ingenierías de la Universidad Indoamérica. Generas herramientas de "
               "estudio para estudiantes universitarios usando SOLO la información del sílabo que se te da.\n"
               + REGLAS + "\n" + PLANTILLAS)
    niveles = [n for lote in LOTES for n in lote]
    r = {"clase": clave, "version": 3, "calculado": calculado}

    pedido = (f"{ctx}{bloque_calc}\n\nPropón 12 focos de evaluación DISTINTOS para esta clase, derivados de sus "
              f"contenidos, actividades, clases anteriores del momento y la rúbrica, en este orden de niveles: "
              f"{', '.join(niveles)}.")
    texto, _, seg = llamar([{"role": "system", "content": sistema}, {"role": "user", "content": pedido}],
                           ESQUEMA_FOCOS, "focos", max_tokens=1500, penalizacion=PENALIZACION)
    focos = json.loads(texto)["focos"]
    print(f"  {clave}: focos en {seg} s", flush=True)

    todos, previos = [], []
    for k, lote in enumerate(LOTES):
        plan = "\n".join(f"{j + 1}. nivel {n} · foco: {focos[k * TAM_LOTE + j]}" for j, n in enumerate(lote))
        pedido = f"{ctx}{bloque_calc}\n\nGenera {len(lote)} ítems, uno por línea de este plan:\n{plan}"
        if previos:
            pedido += "\nYa existen estas preguntas; no las repitas:\n- " + "\n- ".join(p["pregunta"][:120] for p in previos)
        for intento in range(3):  # JSON inválido o cortado → reintento
            texto, uso, seg = llamar([{"role": "system", "content": sistema}, {"role": "user", "content": pedido}],
                                     esquema_lote(len(lote)), "cuestionario", max_tokens=3000, penalizacion=PENALIZACION,
                                     temperatura=0.4 + 0.1 * intento)
            try:
                items = json.loads(texto)["items"]
                break
            except json.JSONDecodeError:
                print(f"  {clave}: lote {k + 1} con JSON inválido, reintento {intento + 1}", flush=True)
        else:
            raise RuntimeError(f"lote {k + 1} sin JSON válido tras 3 intentos")
        fallos = verificar(items, lote, previos)
        for it, n, f in zip(items, lote, fallos):
            it["nivel_pedido"], it["fallos"] = n, f
        todos += items
        print(f"  {clave}: lote {k + 1} en {seg} s, {uso.get('total_tokens')} tokens; fallos {sum(map(bool, fallos))}",
              flush=True)

    encabezado = f"{c['asignatura']} ({c['nivel']}.º nivel).{bloque_calc}"
    for n, it in enumerate(todos, 1):
        it["revision"] = revisar(it, encabezado)
        rv = it["revision"]
        print(f"    ítem {n} ({it['nivel_pedido']}): válido={rv['valido']} verdaderas={rv.get('opciones_verdaderas')} "
              f"clave={it['correcta']} ({rv['segundos']} s)", flush=True)

    r["generados"] = todos
    r["elegidos"] = [todos.index(i) for i in elegir(todos)]
    texto, uso, seg = llamar([{"role": "system", "content": sistema}, {"role": "user", "content":
        f"{ctx}{bloque_calc}\n\nGenera la FICHA DE ESTUDIO de la clase {c['clase']['id']}: ideas clave, un ejemplo "
        f"resuelto paso a paso ({'con los RESULTADOS CALCULADOS, citando sus números' if cuantitativa else 'con una organización ficticia distinta del caso del PIS'}), "
        f"errores frecuentes, relación con el RA y 3 preguntas de autocomprobación."}], ESQUEMA_FICHA, "ficha", penalizacion=PENALIZACION)
    r["ficha"] = {"contenido": json.loads(texto), "segundos": seg}
    print(f"  {clave}: ficha en {seg} s; elegidos {r['elegidos']}", flush=True)
    return r


def main() -> int:
    SALIDA.mkdir(exist_ok=True)
    resultados = [probar(k, c) for k, c in CLASES.items()]
    archivo = SALIDA / f"{datetime.now():%Y%m%d-%H%M}-v3.json"
    archivo.write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Resultados: {archivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
