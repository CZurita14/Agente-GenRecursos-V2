"""Validación cruzada: contrato 2.0 del Generador ↔ silabo-api/0.1.0 del Validador de Sílabos.

Uso (desde la raíz del repo V2, con jsonschema): python docs/api-silabo/validador/cruce_contratos.py
Solo imprime conteos y rutas de campos, nunca textos de los sílabos.

1. Mapa estructural campo por campo entre los dos esquemas.
2. Generador → Validador: los sílabos reales en 2.0 se convierten y se validan con el esquema del validador.
3. Validador → Generador: el ejemplo del validador se convierte y pasa esquema, reglas y entrada al sistema.
4. Ida y vuelta: lo que se pierde al pasar por el otro contrato.
"""
import copy
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import jsonschema

V2 = Path(__file__).resolve().parents[3]
DOCS = V2 / "docs" / "api-silabo"
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(V2 / "backend"))
from app.sga import contrato_v2  # noqa: E402

leer = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
ESQ_GEN = leer(DOCS / "silabo-api.v2.schema.json")
ESQ_VAL = leer(AQUI / "silabo-api-0.1.0.derivado.schema.json")
VG = jsonschema.Draft202012Validator(ESQ_GEN, format_checker=jsonschema.FormatChecker())
VV = jsonschema.Draft202012Validator(ESQ_VAL, format_checker=jsonschema.FormatChecker())

EJES = [("sostenibilidad_ods", "Sostenibilidad - ODS"), ("interculturalidad", "Interculturalidad"),
        ("internacionalizacion", "Internacionalización"), ("interdisciplinariedad", "Interdisciplinariedad"),
        ("emprendimiento", "Emprendimiento"), ("educacion_financiera", "Educación financiera")]
TIPOS = [("clase invertida", None), ("problemas", "aprendizaje_basado_problemas"), ("retos", "aprendizaje_basado_retos"),
         ("servicio", "aprendizaje_servicio"), ("cooperativo", "aprendizaje_cooperativo"), ("caso", "estudio_caso"),
         ("cocreacion", "cocreacion_dialogo_saberes"), ("rutinas", "rutinas_destrezas_pensamiento")]


def plano(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn").split())


def errores(validador, d):
    return sorted({"/".join(str(p) for p in e.absolute_path if not isinstance(p, int)) + " :: " + e.validator
                   for e in validador.iter_errors(d)})


# ------------------------------------------------------------------ 1. Generador (2.0) → Validador (0.1.0)
SIN_FUENTE = Counter()  # campos del validador que el contrato 2.0 no puede llenar


def a_validador(g: dict) -> dict:
    pf, h = g["proyecto_formativo"], g["proyecto_formativo"].get("horas") or {}
    SIN_FUENTE.update(["documento.id", "documento.estado", "documento.generado", "presentacion.horario_practico",
                       "momentos[].totales", "momentos[].rubrica.ra_citados (texto en la cabecera de la rúbrica)",
                       "momentos[].rubrica.evidencia", "rubrica_producto_final.evidencia",
                       "momentos[].sesiones[].fecha_fin (rango de fechas)"])
    meta = contrato_v2.metacompetencia_oficial(g.get("metacompetencia")) or ""
    return {
        "contrato": "silabo-api/0.1.0",
        "documento": {"id": pf["codigo"], "version": pf["version"], "estado": "aprobado", "generado": "2026-11-24T00:00:00-05:00"},
        "portada": {"carrera": g["carrera"], "periodo_codigo": g["periodo"]["codigo"], "periodo_inicio": g["periodo"]["inicio"],
                    "periodo_fin": g["periodo"]["fin"], "pf_nombre": pf["nombre"], "pf_codigo": pf["codigo"],
                    "facultad": g["facultad"], "version": pf["version"], "fecha_aprobacion": pf.get("aprobado")},
        "presentacion": {"nombre": pf["nombre"], "creditos": pf.get("creditos"), "horas_total": h.get("total"),
                         "horas_contacto": h.get("contacto"), "horas_practico": h.get("practico"), "horas_autonomo": h.get("autonomo"),
                         "periodo": g["periodo"]["codigo"], "nivel": pf["nivel"],
                         "prerrequisitos": pf["prerrequisitos"], "correquisitos": pf["correquisitos"],
                         "uoc": pf.get("uoc"), "modalidad": pf.get("modalidad"), "nivel_formacion": pf.get("formacion"),
                         "horario_contacto": [f"{x['dia'].capitalize()} {x['inicio']} a {x['fin']}" for x in pf.get("horario", [])]},
        "mapa": {
            "competencia_perfil": g["competencia_perfil"], "competencia_pf": g["competencia_pf"],
            "contribucion_perfil": g["contribucion_perfil"],
            "metacompetencias": [{"texto": m, "marcada": m == meta} for m in contrato_v2.METACOMPETENCIAS],
            "habilidades_blandas": g["habilidades_blandas"],
            "ejes_transversales": [{"eje": nombre, "como_se_evidencia": g["ejes_transversales"][k]["descripcion"]}
                                   for k, nombre in EJES if g["ejes_transversales"][k]["descripcion"]],
            "inclusion": g["inclusion"],
            "resultados_aprendizaje": copy.deepcopy(g["resultados_aprendizaje"]),
            "problema": g["problema"]["descripcion"], "pregunta_reto": g["problema"]["reto"],
            "evidencia_central": g["problema"]["producto_final"],
            "pis_nombre": g["pis"]["nombre"], "pis_aporte": g["pis"]["aporte"],
            "metodologias": [contrato_v2.CLASE_INVERTIDA] + [
                m["nombre"] or contrato_v2.NOMBRE_METODOLOGIA.get(m["tipo"], m["tipo"]) for m in g["metodologias"]["complementarias"]],
        },
        "momentos": [{
            "numero": m["numero"], "titulo": m["titulo"], "fecha_inicio": m["fecha_inicio"], "fecha_fin": m["fecha_fin"],
            "ra_referidos": m["ra"], "evidencia": m["evidencia"],
            "sesiones": [{
                "numero": s["numero"], "fecha_inicio": s["fecha"], "fecha_fin": s["fecha"],
                "docente": {"actividad": s["docente"]["texto"], "horas": s["docente"]["horas"]},
                "docente_asincronica": ({"actividad": s["docente"]["asincronica"]["texto"],
                                         "horas": s["docente"]["asincronica"].get("horas")} if s["docente"].get("asincronica") else None),
                "practico": {"actividad": s["practico"]["texto"], "horas": s["practico"]["horas"]},
                "autonomo": {"actividad": s["autonomo"]["texto"], "horas": s["autonomo"]["horas"]},
                "contenidos": s["contenidos"]} for s in m["sesiones"]],
            "totales": {"docente": None, "practico": None, "autonomo": None},  # el 2.0 no los trae
            "politica_ia": m["politica_ia"], "recursos": m["recursos"],
            "rubrica": {"evidencia": None, "ra_citados": [], "filas": copy.deepcopy(m["rubrica"])}} for m in g["momentos"]],
        "rubrica_producto_final": {"evidencia": None, "filas": copy.deepcopy(g["rubrica_producto_final"])},
        "bibliografia": copy.deepcopy(g["bibliografia"]),
    }


# ------------------------------------------------------------------ 2. Validador (0.1.0) → Generador (2.0)
_HORARIO = re.compile(r"^\s*(\w+)\s+(\d{1,2}:\d{2})\s+a\s+(\d{1,2}:\d{2})\s*$")


def a_generador(v: dict) -> tuple[dict, list[str]]:
    perdidas = []
    p, pr, mp = v["portada"], v["presentacion"], v["mapa"]
    marcadas = [m["texto"] for m in mp.get("metacompetencias") or [] if m.get("marcada")]
    if len(marcadas) > 1:
        perdidas.append("mapa.metacompetencias: más de una marcada; el 2.0 guarda una")
    ejes = {k: {"aplica": True, "descripcion": "", "justificacion_na": ""} for k, _ in EJES}
    ejes["sostenibilidad_ods"]["ods"] = []
    ejes["internacionalizacion"].update(tipo=None, actores="", actividad="", producto="")
    ejes["interdisciplinariedad"]["disciplinas"] = []
    for e in mp.get("ejes_transversales") or []:
        k = next((k for k, n in EJES if plano(n).split(" - ")[0] in plano(e["eje"]) or plano(e["eje"]) in plano(n)), None)
        if k is None:
            perdidas.append("mapa.ejes_transversales[].eje: eje fuera de los 6 del 2.0")
            continue
        ejes[k]["descripcion"] = e.get("como_se_evidencia") or ""
    comp = []
    for nombre in mp.get("metodologias") or []:
        tipo = next((t for k, t in TIPOS if k in plano(nombre)), "otra")
        if tipo:
            comp.append({"tipo": tipo, "nombre": nombre, "justificacion": "", "aplicada_en": []})
    horario = []
    for x in pr.get("horario_contacto") or []:
        m = _HORARIO.match(x)
        if m:
            horario.append({"dia": plano(m.group(1)), "inicio": m.group(2).zfill(5), "fin": m.group(3).zfill(5)})
        else:
            perdidas.append("presentacion.horario_contacto: franja sin el formato «Día HH:MM a HH:MM»")
    if pr.get("horario_practico"):
        perdidas.append("presentacion.horario_practico: el 2.0 no tiene horario práctico")
    momentos = []
    for m in v.get("momentos") or []:
        sesiones = []
        for s in m.get("sesiones") or []:
            if s.get("fecha_fin") not in (None, s.get("fecha_inicio")):
                perdidas.append("momentos[].sesiones[].fecha_fin: el 2.0 tiene una sola fecha por sesión")
            asin = s.get("docente_asincronica")
            sesiones.append({
                "numero": s["numero"], "fecha": s.get("fecha_inicio"), "contenidos": s.get("contenidos") or [],
                "docente": {"texto": s["docente"].get("actividad") or "", "horas": s["docente"].get("horas") or 0,
                            **({"asincronica": {"texto": asin.get("actividad") or "", "horas": asin.get("horas") or 0}} if asin else {})},
                "practico": {"texto": s["practico"].get("actividad") or "", "horas": s["practico"].get("horas") or 0},
                "autonomo": {"texto": s["autonomo"].get("actividad") or "", "horas": s["autonomo"].get("horas") or 0}})
        if any(x is not None for x in (m.get("totales") or {}).values()):
            perdidas.append("momentos[].totales: el 2.0 no los guarda (los recalcularía desde las sesiones)")
        rb = m.get("rubrica") or {}
        if rb.get("ra_citados"):
            perdidas.append("momentos[].rubrica.ra_citados: el 2.0 no guarda los RA de la cabecera de la rúbrica")
        if rb.get("evidencia") and rb.get("evidencia") != m.get("evidencia"):
            perdidas.append("momentos[].rubrica.evidencia: distinta de la evidencia del momento; el 2.0 no la guarda")
        momentos.append({"numero": m["numero"], "titulo": m.get("titulo") or "", "fecha_inicio": m.get("fecha_inicio"),
                         "fecha_fin": m.get("fecha_fin"), "ra": m.get("ra_referidos") or [], "evidencia": m.get("evidencia") or "",
                         "politica_ia": m.get("politica_ia") or "", "recursos": m.get("recursos") or "",
                         "rubrica": rb.get("filas") or [], "sesiones": sesiones})
    rpf = v.get("rubrica_producto_final") or {}
    if rpf.get("evidencia") and rpf.get("evidencia") != mp.get("evidencia_central"):
        perdidas.append("rubrica_producto_final.evidencia: distinta de evidencia_central; el 2.0 no la guarda")
    perdidas += ["documento.id/estado/generado: el 2.0 no tiene bloque documento"]
    vacio = lambda *ks: dict.fromkeys(ks, "")  # noqa: E731
    g = {
        "contrato": "2.0", "facultad": p.get("facultad") or "", "carrera": p.get("carrera") or "",
        "periodo": {"codigo": p.get("periodo_codigo") or "", "inicio": p.get("periodo_inicio"), "fin": p.get("periodo_fin")},
        "proyecto_formativo": {
            "codigo": p.get("pf_codigo") or "", "nombre": p.get("pf_nombre") or "", "version": v["documento"]["version"],
            "aprobado": p.get("fecha_aprobacion"), "nivel": pr.get("nivel"), "uoc": pr.get("uoc") or "",
            "modalidad": pr.get("modalidad") or "", "formacion": pr.get("nivel_formacion") or "", "creditos": pr.get("creditos"),
            "horas": ({"total": pr.get("horas_total"), "contacto": pr.get("horas_contacto"), "autonomo": pr.get("horas_autonomo"),
                       "practico": pr.get("horas_practico")} if pr.get("horas_total") is not None else None),
            "horario": horario, "prerrequisitos": pr.get("prerrequisitos") or [], "correquisitos": pr.get("correquisitos") or []},
        "competencia_perfil": mp.get("competencia_perfil") or "", "competencia_pf": mp.get("competencia_pf") or "",
        "metacompetencia": marcadas[0] if marcadas else "", "habilidades_blandas": mp.get("habilidades_blandas") or [],
        "ejes_transversales": ejes, "inclusion": mp.get("inclusion") or "", "contribucion_perfil": mp.get("contribucion_perfil") or "",
        "resultados_aprendizaje": mp.get("resultados_aprendizaje") or [],
        "problema": {"descripcion": mp.get("problema") or "", "reto": mp.get("pregunta_reto") or "",
                     "producto_final": mp.get("evidencia_central") or ""},
        "pis": {"aplica": True, "nombre": mp.get("pis_nombre") or "", "descripcion": "", "aporte": mp.get("pis_aporte") or "",
                "justificacion_na": ""},
        "metodologias": {"clase_invertida": vacio("antes", "durante", "despues"), "complementarias": comp},
        "momentos": momentos, "rubrica_producto_final": rpf.get("filas") or [],
        "evaluacion": {"proceso": vacio("inicial", "seguimiento", "final"),
                       "agentes": vacio("autoevaluacion", "coevaluacion", "heteroevaluacion"),
                       "retroalimentacion": "", "metacompetencia": "", "gobernanza_ia": "",
                       "calificacion": {"componentes": [], "reglas": ""}, "mejora": "",
                       "credencial": {"aplica": True, **vacio("nombre", "desempeno", "evidencias", "criterios", "justificacion_na")}},
        "bibliografia": {"basica": (v.get("bibliografia") or {}).get("basica") or [],
                         "complementaria": (v.get("bibliografia") or {}).get("complementaria") or []},
    }
    return g, perdidas


# ------------------------------------------------------------------ ejecución
def main():
    from ciencia_datos.migrar_v2 import migrar
    from app.sga.traductor import a_contrato_con_avisos
    from app.silabo.integridad import SilaboInvalido, cargar_silabo

    lotes = {"Ingeniería 2026 (PDF → 2.0)": [leer(f) for f in sorted((V2 / "datos_cd/silabos_b26c_v2").glob("*.json"))],
             "corpus B26 anterior (1.0 → 2.0)": [migrar(leer(f)) for d in ("datos_cd/silabos_b26", "datos_cd/silabos_b26b")
                                               for f in sorted((V2 / d).rglob("*.json"))],
             "ejemplos 2.0": [leer(DOCS / "ejemplo-v2-completo.json"), leer(DOCS / "ejemplo-v2-minimo.json")]}
    print("== 2. Generador → Validador (esquema derivado del validador)")
    for nombre, lote in lotes.items():
        ok, fallos = 0, Counter()
        for g in lote:
            e = errores(VV, a_validador(g))
            ok += not e
            fallos.update(e)
        print(f"  {nombre}: {ok}/{len(lote)} válidos", dict(fallos.most_common(6)) if fallos else "")
    print("  campos del validador sin fuente en el 2.0:", sorted(SIN_FUENTE))

    print("== 3. Validador → Generador")
    ej = leer(AQUI / "silabo-api-0.1.0.ejemplo.json")
    print("  ejemplo del validador en su propio esquema:", errores(VV, ej) or "válido")
    g, perdidas = a_generador(ej)
    print("  esquema 2.0:", errores(VG, g) or "válido", "| reglas 2.0:", contrato_v2.reglas(g) or "cumple")
    try:
        contrato, avisos = a_contrato_con_avisos(g)
        cargar_silabo(contrato)
        print("  entra al sistema: sí", "| avisos:", avisos)
    except SilaboInvalido as ex:
        print("  entra al sistema: NO", ex.fallos[:5])
    print("  información del validador que el 2.0 no conserva:", sorted(set(perdidas)))
    # Variantes del mismo ejemplo con los campos que el validador declara opcionales y el 2.0 exige
    for quitar in ("portada.facultad", "portada.fecha_aprobacion", "momentos[].recursos", "bibliografia"):
        v = copy.deepcopy(ej)
        if quitar == "momentos[].recursos":
            for m in v["momentos"]:
                m.pop("recursos", None)
        elif "." in quitar:
            b, k = quitar.split(".")
            v[b].pop(k, None)
        else:
            v.pop(quitar, None)
        e_val = errores(VV, v)
        g2, _ = a_generador(v)
        print(f"  sin {quitar}: validador {'acepta' if not e_val else 'rechaza'} | 2.0 {errores(VG, g2) or 'acepta'}")

    print("== 3b. Casos límite: ¿los dos contratos deciden lo mismo?")
    def caso(nombre, cambio):
        v = copy.deepcopy(ej)
        cambio(v)
        g3, _ = a_generador(v)
        e_g = errores(VG, g3) + [f"regla: {x}" for x in contrato_v2.reglas(g3)]
        print(f"  {nombre}: validador {'acepta' if not errores(VV, v) else 'rechaza'} | 2.0 {'acepta' if not e_g else 'rechaza ' + str(e_g[:2])}")
    ra = ej["mapa"]["resultados_aprendizaje"][0]
    caso("5 resultados de aprendizaje", lambda v: v["mapa"].__setitem__("resultados_aprendizaje",
         [{**ra, "id": f"RA{i}"} for i in range(1, 6)]))
    caso("RA numerados RA1, RA3", lambda v: v["mapa"]["resultados_aprendizaje"][1].__setitem__("id", "RA3"))
    caso("tabla de RA vacía", lambda v: v["mapa"].__setitem__("resultados_aprendizaje", []))
    caso("nivel 13", lambda v: v["presentacion"].__setitem__("nivel", 13))
    caso("sin momentos", lambda v: v.__setitem__("momentos", []))
    caso("momento sin sesiones", lambda v: v["momentos"][0].__setitem__("sesiones", []))
    caso("horas de una sesión vacías (null)", lambda v: v["momentos"][0]["sesiones"][0]["docente"].__setitem__("horas", None))
    caso("créditos vacíos (null)", lambda v: v["presentacion"].__setitem__("creditos", None))
    caso("horas totales vacías (null)", lambda v: v["presentacion"].__setitem__("horas_total", None))
    caso("fecha de sesión vacía (null)", lambda v: v["momentos"][0]["sesiones"][0].__setitem__("fecha_inicio", None))
    caso("política de IA vacía (null)", lambda v: v["momentos"][1].__setitem__("politica_ia", None))
    caso("metacompetencia fuera del catálogo", lambda v: v["mapa"]["metacompetencias"][4].__setitem__("texto", "Otra metacompetencia"))
    caso("dos metacompetencias marcadas", lambda v: v["mapa"]["metacompetencias"][0].__setitem__("marcada", True))
    caso("eje fuera de los 6", lambda v: v["mapa"]["ejes_transversales"].append({"eje": "Género", "como_se_evidencia": "x"}))
    caso("clave no prevista en la raíz", lambda v: v.__setitem__("docente", "x"))
    caso("código PF con otra forma", lambda v: v["portada"].__setitem__("pf_codigo", "PF-123"))

    print("== 4. Ida y vuelta Generador → Validador → Generador (campos que cambian)")
    cambios = Counter()
    for g in lotes["Ingeniería 2026 (PDF → 2.0)"] + lotes["ejemplos 2.0"]:
        vuelta, _ = a_generador(a_validador(g))
        def comparar(a, b, ruta=""):
            if isinstance(a, dict) and isinstance(b, dict):
                for k in set(a) | set(b):
                    comparar(a.get(k), b.get(k), f"{ruta}.{k}" if ruta else k)
            elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
                for x, y in zip(a, b):
                    comparar(x, y, ruta + "[]")
            elif a != b:
                cambios[ruta] += 1
        comparar(g, vuelta)
    for k, n in sorted(cambios.items()):
        print(f"  {k}: {n}")


if __name__ == "__main__":
    main()
