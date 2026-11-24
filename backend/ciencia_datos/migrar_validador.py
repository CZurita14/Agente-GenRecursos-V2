"""Sílabo del contrato 2.0 → JSON del Validador de Sílabos (`silabo-api/0.1.0`). Herramienta de datos.

Sirve para pasar al contrato definitivo los sílabos y fixtures que estaban en 2.0. Lo que el 2.0
no tiene se envía vacío, como pide el validador (`null` o []): `momentos[].totales`, los RA citados y
la evidencia de cada rúbrica, el horario práctico y el rango de fechas de la sesión (una sola fecha).
`documento` se arma con el código, la versión y la fecha de aprobación del PF.
"""
import copy

from app.sga import contrato_v2

_EJES = (("sostenibilidad_ods", "Sostenibilidad - ODS"), ("interculturalidad", "Interculturalidad"),
         ("internacionalizacion", "Internacionalización"), ("interdisciplinariedad", "Interdisciplinariedad"),
         ("emprendimiento", "Emprendimiento"), ("educacion_financiera", "Educación financiera"))
CONOCIDAS = set(contrato_v2.RAIZ_OBLIGATORIA)


def _act(a: dict) -> dict:
    return {"actividad": a.get("texto", ""), "horas": a.get("horas")}


def desde_v2(g: dict, *, extras: bool = False) -> dict:
    """Con `extras` conserva las claves ajenas al contrato (p. ej. datos privados falsos de las pruebas)."""
    pf, h = g["proyecto_formativo"], g["proyecto_formativo"].get("horas") or {}
    meta = contrato_v2.metacompetencia_oficial(g.get("metacompetencia")) or ""
    v = {
        "contrato": "silabo-api/0.1.0",
        "documento": {"id": pf["codigo"], "version": pf["version"], "estado": "aprobado",
                      "generado": f"{pf.get('aprobado') or g['periodo']['inicio']}T00:00:00-05:00"},
        "portada": {"carrera": g["carrera"], "periodo_codigo": g["periodo"]["codigo"], "periodo_inicio": g["periodo"]["inicio"],
                    "periodo_fin": g["periodo"]["fin"], "pf_nombre": pf["nombre"], "pf_codigo": pf["codigo"],
                    "facultad": g["facultad"], "version": pf["version"], "fecha_aprobacion": pf.get("aprobado")},
        "presentacion": {"nombre": pf["nombre"], "creditos": pf.get("creditos"), "horas_total": h.get("total"),
                         "horas_contacto": h.get("contacto"), "horas_practico": h.get("practico"),
                         "horas_autonomo": h.get("autonomo"), "periodo": g["periodo"]["codigo"], "nivel": pf["nivel"],
                         "prerrequisitos": list(pf.get("prerrequisitos", [])), "correquisitos": list(pf.get("correquisitos", [])),
                         "uoc": pf.get("uoc", ""), "modalidad": pf.get("modalidad", ""), "nivel_formacion": pf.get("formacion", ""),
                         "horario_contacto": [f"{x['dia'].capitalize()} {x['inicio']} a {x['fin']}" for x in pf.get("horario", [])],
                         "horario_practico": []},
        "mapa": {
            "competencia_perfil": g["competencia_perfil"], "competencia_pf": g["competencia_pf"],
            "contribucion_perfil": g["contribucion_perfil"],
            "metacompetencias": [{"texto": m, "marcada": m == meta} for m in contrato_v2.METACOMPETENCIAS],
            "habilidades_blandas": list(g["habilidades_blandas"]),
            "ejes_transversales": [{"eje": n, "como_se_evidencia": g["ejes_transversales"][k]["descripcion"]}
                                   for k, n in _EJES if g["ejes_transversales"][k]["descripcion"]],
            "inclusion": g["inclusion"],
            "resultados_aprendizaje": copy.deepcopy(g["resultados_aprendizaje"]),
            "problema": g["problema"]["descripcion"], "pregunta_reto": g["problema"]["reto"],
            "evidencia_central": g["problema"]["producto_final"],
            "pis_nombre": g["pis"]["nombre"] if g["pis"].get("aplica", True) else "",
            "pis_aporte": g["pis"]["aporte"] if g["pis"].get("aplica", True) else "",
            "metodologias": contrato_v2.a_v1({"metodologias": g["metodologias"]})["metodologias"],
        },
        "momentos": [{
            "numero": m["numero"], "titulo": m["titulo"], "fecha_inicio": m["fecha_inicio"], "fecha_fin": m["fecha_fin"],
            "ra_referidos": list(m["ra"]), "evidencia": m["evidencia"],
            "sesiones": [dict({
                "numero": s["numero"], "fecha_inicio": s["fecha"], "fecha_fin": s["fecha"],
                "docente": _act(s["docente"]),
                "docente_asincronica": _act(s["docente"]["asincronica"]) if s["docente"].get("asincronica") else None,
                "practico": _act(s["practico"]), "autonomo": _act(s["autonomo"]), "contenidos": list(s["contenidos"])},
                **({k: copy.deepcopy(x) for k, x in s.items() if k not in
                    {"numero", "fecha", "docente", "practico", "autonomo", "contenidos"}} if extras else {}))
                for s in m["sesiones"]],
            "totales": {"docente": None, "practico": None, "autonomo": None},
            "politica_ia": m["politica_ia"], "recursos": m.get("recursos", ""),
            "rubrica": {"evidencia": None, "ra_citados": [], "filas": copy.deepcopy(m["rubrica"])}} for m in g["momentos"]],
        "rubrica_producto_final": {"evidencia": None, "filas": copy.deepcopy(g["rubrica_producto_final"])},
        "bibliografia": copy.deepcopy(g["bibliografia"]),
    }
    if extras:
        v.update({k: copy.deepcopy(x) for k, x in g.items() if k not in CONOCIDAS})
    return v
