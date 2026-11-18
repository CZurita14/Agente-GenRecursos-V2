"""Evalúa el contrato v2.0 y el formato de evaluación. Solo imprime cifras y rutas, nunca textos de sílabos.

Uso: python validar_v2.py <repo V2>
"""
import copy
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import jsonschema

V2 = Path(sys.argv[1])
DOCS = V2 / "docs" / "api-silabo"
sys.path.insert(0, str(V2 / "backend"))
from app.sga import contrato_v2  # noqa: E402
from app.sga.traductor import a_contrato_con_avisos  # noqa: E402
from app.silabo.escala import catalogo, revision_automatica, validar_evaluacion  # noqa: E402
from app.silabo.integridad import SilaboInvalido, cargar_silabo  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from migrar_a_v2 import migrar, plano  # noqa: E402

leer = lambda n: json.loads((DOCS / n).read_text(encoding="utf-8"))
E_SIL, E_EV = leer("silabo-api.v2.schema.json"), leer("evaluacion-silabo.schema.json")
for e in (E_SIL, E_EV):
    jsonschema.Draft202012Validator.check_schema(e)
VS = jsonschema.Draft202012Validator(E_SIL, format_checker=jsonschema.FormatChecker())
VE = jsonschema.Draft202012Validator(E_EV, format_checker=jsonschema.FormatChecker())
errs = lambda v, d: [".".join(map(str, x.absolute_path)) + " :: " + x.validator for x in v.iter_errors(d)]
OK = Counter()


def check(nombre, cond, detalle=""):
    OK["ok" if cond else "FALLA"] += 1
    if not cond:
        print("FALLA", nombre, detalle)


# 1. Ejemplos
completo, minimo, ev = leer("ejemplo-v2-completo.json"), leer("ejemplo-v2-minimo.json"), leer("ejemplo-evaluacion.json")
for n, d in (("completo", completo), ("minimo", minimo)):
    check(f"esquema {n}", not errs(VS, d), errs(VS, d)[:5])
    check(f"reglas {n}", not contrato_v2.reglas(d), contrato_v2.reglas(d))
    try:
        c, avisos = a_contrato_con_avisos(d)
        cargar_silabo(c)
        check(f"sistema {n}", True)
    except SilaboInvalido as e:
        check(f"sistema {n}", False, e.fallos)
    r = revision_automatica(d, fecha="2026-11-18")
    check(f"evaluacion automatica {n} esquema", not errs(VE, r), errs(VE, r)[:5])
    check(f"evaluacion automatica {n} reglas", not validar_evaluacion(r, d), validar_evaluacion(r, d)[:5])
for n in ("ejemplo-minimo.json", "ejemplo-completo.json"):
    check(f"v1 {n} rechazado por v2", bool(errs(VS, leer(n))))
check("ejemplo-evaluacion esquema", not errs(VE, ev), errs(VE, ev)[:5])
check("ejemplo-evaluacion reglas", not validar_evaluacion(ev, completo), validar_evaluacion(ev, completo)[:5])
check("ejemplo-evaluacion completa", ev["completa"] and ev["total"] is not None)
rmin = revision_automatica(minimo, fecha="2026-11-18")
print("minimo automatico:", Counter(str(p["valor"]) for p in rmin["puntos"]))


# 2. Trazabilidad: cada ruta del catálogo existe en el esquema, y cada hoja del esquema se usa
def nodo(esq, n):
    if "$ref" in n:
        n = esq["$defs"][n["$ref"].split("/")[-1]]
    props = dict(n.get("properties", {}))
    for sub in n.get("allOf", []):
        props.update(nodo(esq, sub).get("properties", {}))
    return {**n, "properties": props} if props else n


def existe(ruta):
    n = E_SIL
    for parte in re.sub(r"\[[a-z_=]+\]$", "", ruta).split("."):
        lista = parte.endswith("[]")
        n = nodo(E_SIL, n)["properties"].get(parte.removesuffix("[]"))
        if n is None:
            return False
        if lista:
            n = nodo(E_SIL, n).get("items", {})
    return True


usadas = set()
for p in catalogo()["puntos"]:
    for r in p["rutas"]:
        check(f"ruta {p['codigo']} {r}", existe(r))
        usadas.add(re.sub(r"\[[a-z_=]+\]$", "", r).replace("[]", ""))


def hojas(n, pre=""):
    n = nodo(E_SIL, n)
    if n.get("properties"):
        for k, v in n["properties"].items():
            yield from hojas(v, f"{pre}.{k}" if pre else k)
    elif n.get("type") == "array" and isinstance(n.get("items"), dict) and nodo(E_SIL, n["items"]).get("properties"):
        yield from hojas(n["items"], pre)
    else:
        yield pre


SISTEMA = {"contrato", "facultad", "carrera", "proyecto_formativo.codigo", "proyecto_formativo.version",
           "proyecto_formativo.aprobado", "momentos.numero", "momentos.sesiones.id", "momentos.sesiones.semana_periodo",
           "momentos.sesiones.entregables", "resultados_aprendizaje.id", "pis.aplica", "pis.justificacion_na",
           "metodologias.complementarias.tipo", "metodologias.complementarias.nombre",
           "metodologias.complementarias.justificacion", "metodologias.complementarias.aplicada_en"}
sin_punto = []
for h in hojas(E_SIL):
    if h in SISTEMA or any(h == u or h.startswith(u + ".") for u in usadas):
        continue
    sin_punto.append(h)
check("toda hoja del esquema tiene uso", not sin_punto, sin_punto)

# 3. Casos que el esquema debe rechazar
def mut(f, base=completo, v=VS):
    d = copy.deepcopy(base)
    f(d)
    return bool(errs(v, d))


neg_sil = {
    "eje NA sin justificación": lambda d: d["ejes_transversales"]["emprendimiento"].update(justificacion_na=""),
    "ODS 18": lambda d: d["ejes_transversales"]["sostenibilidad_ods"]["ods"].append(18),
    "ODS repetido": lambda d: d["ejes_transversales"]["sostenibilidad_ods"]["ods"].append(9),
    "clave extra en eje": lambda d: d["ejes_transversales"]["interculturalidad"].update(x=1),
    "tipo internacional inválido": lambda d: d["ejes_transversales"]["internacionalizacion"].update(tipo="viaje"),
    "cinco RA": lambda d: d["resultados_aprendizaje"].extend(copy.deepcopy(d["resultados_aprendizaje"]) * 2),
    "RA5": lambda d: d["resultados_aprendizaje"][1].update(id="RA5"),
    "metodología desconocida": lambda d: d["metodologias"]["complementarias"][0].update(tipo="gamificacion"),
    "otra sin nombre": lambda d: d["metodologias"]["complementarias"].append(
        {"tipo": "otra", "nombre": "", "justificacion": "x", "aplicada_en": []}),
    "aplicada_en mal formado": lambda d: d["metodologias"]["complementarias"][0].update(aplicada_en=["2-1"]),
    "PIS NA sin justificación": lambda d: d["pis"].update(aplica=False),
    "credencial NA sin justificación": lambda d: d["evaluacion"]["credencial"].update(justificacion_na=""),
    "porcentaje 0": lambda d: d["evaluacion"]["calificacion"]["componentes"][0].update(porcentaje=0),
    "rúbrica sin crítico": lambda d: d["momentos"][0]["rubrica"][0]["niveles"].pop("critico"),
    "sesión sin horas": lambda d: d["momentos"][0]["sesiones"][0]["practico"].pop("horas"),
    "hora 7:00": lambda d: d["proyecto_formativo"]["horario"][0].update(inicio="7:00"),
    "falta evaluacion": lambda d: d.pop("evaluacion"),
    "falta prerrequisitos": lambda d: d["proyecto_formativo"].pop("prerrequisitos"),
    "contrato 1.0": lambda d: d.update(contrato="1.0"),
    "perfil docente (sección I)": lambda d: d.update(docente={"correo": "x"}),
    "firmas (sección VII)": lambda d: d.update(firmas=[]),
}
for n, f in neg_sil.items():
    check(f"rechaza: {n}", mut(f))
neg_ev = {
    "NA en III.1": lambda d: next(p for p in d["puntos"] if p["codigo"] == "III.1").update(valor="NA", justificacion="x"),
    "NA sin justificación": lambda d: next(p for p in d["puntos"] if p["codigo"] == "III.9").update(justificacion=""),
    "NA en RA1": lambda d: next(p for p in d["puntos"] if p["codigo"] == "III.12").update(valor="NA", justificacion="x"),
    "III.12 sin ra": lambda d: next(p for p in d["puntos"] if p["codigo"] == "III.12").pop("ra"),
    "IV sin momento": lambda d: next(p for p in d["puntos"] if p["codigo"] == "IV.1").pop("momento"),
    "momento en III.1": lambda d: next(p for p in d["puntos"] if p["codigo"] == "III.1").update(momento=1),
    "I.1 valorado por IA": lambda d: next(p for p in d["puntos"] if p["codigo"] == "I.1").update(fuente="ia"),
    "nivel 6": lambda d: next(p for p in d["puntos"] if p["codigo"] == "II.1").update(valor=6),
    "nivel 0": lambda d: next(p for p in d["puntos"] if p["codigo"] == "II.1").update(valor=0),
    "código inventado": lambda d: d["puntos"][0].update(codigo="III.30"),
    "etapa inválida": lambda d: d["revision"].update(etapa="cierre"),
}
for n, f in neg_ev.items():
    check(f"rechaza evaluación: {n}", mut(f, ev, VE))
neg_reglas = {
    "punto repetido": lambda d: d["puntos"].append(copy.deepcopy(d["puntos"][3])),
    "punto faltante": lambda d: d["puntos"].pop(3),
    "total alterado": lambda d: d.update(total=99.0),
    "momento inexistente": lambda d: next(p for p in d["puntos"] if p["codigo"] == "IV.1").update(momento=9),
}
for n, f in neg_reglas.items():
    d = copy.deepcopy(ev)
    f(d)
    check(f"regla de evaluación detecta: {n}", bool(validar_evaluacion(d, completo)))
d = copy.deepcopy(completo)
d["resultados_aprendizaje"][1]["id"] = "RA3"
check("regla: RA con salto", bool(contrato_v2.reglas(d)))
d = copy.deepcopy(completo)
d["metodologias"]["complementarias"][1]["tipo"] = "aprendizaje_basado_problemas"
check("regla: metodología repetida", bool(contrato_v2.reglas(d)))

# 4. Migración de los 51 sílabos reales (v1) al v2 y revisión automática
docs = {}
for carpeta in ("datos_cd/silabos_b26", "datos_cd/silabos_b26b"):
    for f in sorted((V2 / carpeta).rglob("*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        docs[j["proyecto_formativo"]["codigo"]] = j
c = Counter()
por_punto = Counter()
err_tipos = Counter()
metodo_otra = 0
for j in docs.values():
    v2 = migrar(j)
    e = errs(VS, v2)
    c["esquema_ok"] += not e
    for x in e:
        err_tipos[re.sub(r"\.\d+", "[]", x)] += 1
    c["reglas_ok"] += not contrato_v2.reglas(v2)
    metodo_otra += sum(m["tipo"] == "otra" for m in v2["metodologias"]["complementarias"])
    # Mismo sílabo interno por la vía v1 y por la vía v2 (salvo metodologías, que el v2 normaliza)
    crudo1 = copy.deepcopy(v2); crudo1.pop("contrato")
    s1 = cargar_silabo(a_contrato_con_avisos(contrato_v2.a_v1(v2))[0]).model_dump(mode="json")
    s0 = cargar_silabo(a_contrato_con_avisos({k: v for k, v in j.items()})[0]).model_dump(mode="json")
    met0, met1 = s0.pop("metodologias", None), s1.pop("metodologias", None)
    c["igual_interno"] += s0 == s1
    c["metodologias_mismo_conjunto"] += {x.casefold() for x in (met0 or [])} | {"clase invertida"} == {x.casefold() for x in (met1 or [])}
    r = revision_automatica(v2, fecha="2026-11-18")
    c["evaluacion_esquema_ok"] += not errs(VE, r)
    c["evaluacion_reglas_ok"] += not validar_evaluacion(r, v2)
    for p in r["puntos"]:
        por_punto[(p["codigo"], str(p["valor"]), p["pendiente"])] += 1
    # IV.7 informativo: horas de las sesiones frente a horas.total del PF
    h = j["proyecto_formativo"].get("horas")
    if h:
        suma = sum((s["docente"].get("horas") or 0) + ((s["docente"].get("asincronica") or {}).get("horas") or 0)
                   + (s["practico"].get("horas") or 0) + (s["autonomo"].get("horas") or 0)
                   for m in j["momentos"] for s in m["sesiones"])
        c["horas_iguales_total"] += abs(suma - h["total"]) < 0.01
        c["horas_con_dato"] += 1
print("reales", len(docs), dict(c), "metodologias 'otra'", metodo_otra)
if err_tipos:
    print("errores de esquema en la migración:", dict(err_tipos.most_common(10)))
# Resumen por punto: cuántos sílabos quedan en ND, NA, por valorar y pendiente
resumen = {}
for (cod, val, pen), n in por_punto.items():
    r = resumen.setdefault(cod, Counter())
    r[val] += n
    r["pendiente"] += n if pen else 0
orden = [p["codigo"] for p in catalogo()["puntos"]]
for cod in orden:
    print(" ", cod, dict(resumen[cod]))
print("RESULTADO", dict(OK))
