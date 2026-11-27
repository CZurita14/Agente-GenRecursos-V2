"""Contrato definitivo del sílabo: el JSON del Validador de Sílabos (`silabo-api/0.1.0`), tal cual.

Documento de referencia: «Estructura JSON para el Validador de Sílabos y PIS» (24/11/2026). El
Generador no cambia ese contrato: lo lleva a su forma interna (la misma que producía el contrato
2.0), de modo que el contexto, los prompts, el plan y el menú —y con ellos las herramientas— no
cambian. Lo que el validador deja vacío (`null`, "" o []) sigue vacío: nunca se rellena con 0.

- `reglas`: lo mínimo que el Generador necesita para generar, con rutas del validador. El resto lo
  diagnostica el validador (más de 4 RA, metacompetencia fuera del catálogo...) y no impide generar.
- `a_interno`: forma interna (lista blanca de campos: lo que no está aquí no pasa, p. ej. datos personales).
- `a_v2`: forma del contrato 2.0 para la Escala general de evaluación (`app.silabo.escala`).
Nunca muta la entrada ni falla con tipos raros: lo que no reconoce lo deja para la validación.
"""
import re
import unicodedata

from app.sga import contrato_v2

VERSION = "silabo-api/0.1.0"
BLOQUES = ("documento", "portada", "presentacion", "mapa", "momentos", "rubrica_producto_final")
_HORARIO = re.compile(r"^\s*([^\d\s]+)\s+(\d{1,2}:\d{2})\s+a\s+(\d{1,2}:\d{2})\s*$")
_EJES = (("sostenibilidad_ods", "SOSTENIBILIDAD"), ("interculturalidad", "INTERCULTURALIDAD"),
         ("internacionalizacion", "INTERNACIONALIZACION"), ("interdisciplinariedad", "INTERDISCIPLINARIEDAD"),
         ("emprendimiento", "EMPRENDIMIENTO"), ("educacion_financiera", "EDUCACION FINANCIERA"))
_TIPOS = (("clase invertida", None), ("problemas", "aprendizaje_basado_problemas"), ("retos", "aprendizaje_basado_retos"),
          ("servicio", "aprendizaje_servicio"), ("cooperativo", "aprendizaje_cooperativo"), ("caso", "estudio_caso"),
          ("cocreacion", "cocreacion_dialogo_saberes"), ("rutinas", "rutinas_destrezas_pensamiento"))


def es_validador(crudo) -> bool:
    return isinstance(crudo, dict) and crudo.get("contrato") == VERSION


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _t(x) -> str:
    return x if isinstance(x, str) else ""


def _plano(texto: str) -> str:
    sin = "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn")
    return " ".join(sin.lower().split())


def reglas(crudo: dict) -> list[str]:
    """Requisitos para generar (rutas del validador, nunca valores)."""
    fallos = [f"{k}: falta" for k in BLOQUES if k not in crudo]
    portada, pres, mapa = _d(crudo.get("portada")), _d(crudo.get("presentacion")), _d(crudo.get("mapa"))
    for campo, que in (("pf_codigo", "el código del PF"), ("pf_nombre", "el nombre del PF"), ("carrera", "la carrera"),
                       ("periodo_codigo", "el código del periodo"), ("periodo_inicio", "el inicio del periodo"),
                       ("periodo_fin", "el fin del periodo")):
        if "portada" in crudo and not _t(portada.get(campo)).strip():
            fallos.append(f"portada.{campo}: el Generador necesita {que}")
    if "presentacion" in crudo and not isinstance(pres.get("nivel"), int):
        fallos.append("presentacion.nivel: el Generador necesita el nivel")
    if "mapa" in crudo:
        ras = _l(mapa.get("resultados_aprendizaje"))
        if not ras:
            fallos.append("mapa.resultados_aprendizaje: el Generador necesita al menos un resultado de aprendizaje")
        vistos = set()
        for i, r in enumerate(ras):
            rid = _d(r).get("id")
            if rid in vistos:
                fallos.append(f"mapa.resultados_aprendizaje[{i}].id: repetido")
            vistos.add(rid)
    if "momentos" in crudo:
        momentos = _l(crudo.get("momentos"))
        if not momentos:
            fallos.append("momentos: el Generador necesita al menos un momento")
        for i, m in enumerate(momentos):
            if not _l(_d(m).get("sesiones")):
                fallos.append(f"momentos[{i}].sesiones: el Generador necesita al menos una sesión")
    return fallos


def _metacompetencia(mapa: dict) -> str:
    marcadas = [_t(_d(m).get("texto")) for m in _l(mapa.get("metacompetencias")) if _d(m).get("marcada") is True]
    if not marcadas:
        return ""
    oficial = contrato_v2.metacompetencia_oficial(marcadas[0])
    return oficial if oficial else marcadas[0]


def _horario(franjas) -> list[dict]:
    salida = []
    for f in _l(franjas):
        m = _HORARIO.match(_t(f))
        if m:
            salida.append({"dia": _plano(m.group(1)), "inicio": m.group(2).zfill(5), "fin": m.group(3).zfill(5)})
    return salida


def _horas(pres: dict):
    claves = {"total": "horas_total", "contacto": "horas_contacto", "autonomo": "horas_autonomo", "practico": "horas_practico"}
    valores = {k: pres.get(v) for k, v in claves.items()}
    # El objeto interno va completo o no va: una hora vacía en el validador deja las horas sin dato.
    return valores if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valores.values()) else None


def _actividad(a, asincronica=None) -> dict:
    a = _d(a)
    salida = {"texto": _t(a.get("actividad")), "horas": a.get("horas") if isinstance(a.get("horas"), (int, float)) else None}
    if isinstance(asincronica, dict):
        salida["asincronica"] = _actividad(asincronica)
    return salida


def _filas(filas) -> list[dict]:
    return [{"indicador": _t(_d(f).get("indicador")),
             "niveles": {k: _t(_d(_d(f).get("niveles")).get(k)) for k in ("receptivo", "resolutivo", "reflexivo", "critico", "cocreativo")}}
            for f in _l(filas)]


def a_interno(crudo: dict) -> dict:
    """Forma interna del sílabo (la del contrato 1.0/2.0 ya adaptado), solo con los campos que usa el Generador."""
    doc, portada, pres, mapa = (_d(crudo.get(k)) for k in ("documento", "portada", "presentacion", "mapa"))
    generado = _t(doc.get("generado"))[:10] or None
    pis = {"nombre": _t(mapa.get("pis_nombre")), "aporte": _t(mapa.get("pis_aporte"))}
    interno = {
        "facultad": _t(portada.get("facultad")), "carrera": _t(portada.get("carrera")),
        "periodo": {"codigo": _t(portada.get("periodo_codigo")), "inicio": portada.get("periodo_inicio"),
                    "fin": portada.get("periodo_fin")},
        "proyecto_formativo": {
            "nombre": _t(portada.get("pf_nombre")), "codigo": _t(portada.get("pf_codigo")),
            "version": _t(doc.get("version")) or _t(portada.get("version")),
            # La fecha de aprobación no interviene en la generación; si el validador no la trae se usa la del JSON.
            "aprobado": portada.get("fecha_aprobacion") or generado,
            "uoc": _t(pres.get("uoc")), "nivel": pres.get("nivel"), "modalidad": _t(pres.get("modalidad")),
            "creditos": pres.get("creditos") if isinstance(pres.get("creditos"), (int, float)) else None,
            "horas": _horas(pres), "horario": _horario(pres.get("horario_contacto"))},
        "competencia_perfil": _t(mapa.get("competencia_perfil")), "competencia_pf": _t(mapa.get("competencia_pf")),
        "metacompetencia": _metacompetencia(mapa),
        "resultados_aprendizaje": [{"id": _t(_d(r).get("id")), "texto": _t(_d(r).get("texto")),
                                    "evidencia": _t(_d(r).get("evidencia"))} for r in _l(mapa.get("resultados_aprendizaje"))],
        "problema": {"descripcion": _t(mapa.get("problema")), "reto": _t(mapa.get("pregunta_reto")),
                     "producto_final": _t(mapa.get("evidencia_central"))},
        "metodologias": [_t(m) for m in _l(mapa.get("metodologias")) if _t(m)],
        "momentos": [{
            "numero": _d(m).get("numero"), "titulo": _t(_d(m).get("titulo")),
            "fecha_inicio": _d(m).get("fecha_inicio"), "fecha_fin": _d(m).get("fecha_fin"),
            "ra": [_t(x) for x in _l(_d(m).get("ra_referidos"))], "evidencia": _t(_d(m).get("evidencia")),
            "recursos": _t(_d(m).get("recursos")), "politica_ia": _t(_d(m).get("politica_ia")),
            "rubrica": _filas(_d(_d(m).get("rubrica")).get("filas")),
            "sesiones": [{
                "numero": _d(s).get("numero"), "fecha": _d(s).get("fecha_inicio"),
                "contenidos": [_t(c) for c in _l(_d(s).get("contenidos"))],
                "docente": _actividad(_d(s).get("docente"), _d(s).get("docente_asincronica")),
                "practico": _actividad(_d(s).get("practico")), "autonomo": _actividad(_d(s).get("autonomo")),
            } for s in _l(_d(m).get("sesiones"))],
        } for m in _l(crudo.get("momentos"))],
        "rubrica_producto_final": _filas(_d(crudo.get("rubrica_producto_final")).get("filas")),
        "bibliografia": {"basica": [_t(x) for x in _l(_d(crudo.get("bibliografia")).get("basica"))],
                         "complementaria": [_t(x) for x in _l(_d(crudo.get("bibliografia")).get("complementaria"))]},
    }
    if pis["nombre"].strip() or pis["aporte"].strip():
        interno["pis"] = pis
    return interno


def a_v2(crudo: dict) -> dict:
    """Forma del contrato 2.0 para la escala de evaluación. Lo que el validador no tiene queda vacío (ND)."""
    i = a_interno(crudo)
    mapa = _d(crudo.get("mapa"))
    pres = _d(crudo.get("presentacion"))
    vacio = lambda *ks: dict.fromkeys(ks, "")  # noqa: E731
    ejes = {k: {"aplica": True, "descripcion": "", "justificacion_na": ""} for k, _ in _EJES}
    ejes["sostenibilidad_ods"]["ods"] = []
    ejes["internacionalizacion"].update(tipo=None, actores="", actividad="", producto="")
    ejes["interdisciplinariedad"]["disciplinas"] = []
    for e in _l(mapa.get("ejes_transversales")):
        nombre = _plano(_t(_d(e).get("eje"))).upper()
        clave = next((k for k, r in _EJES if r in nombre), None)
        if clave:
            ejes[clave]["descripcion"] = _t(_d(e).get("como_se_evidencia"))
    complementarias = []
    for nombre in i["metodologias"]:
        tipo = next((t for k, t in _TIPOS if k in _plano(nombre)), "otra")
        if tipo:
            complementarias.append({"tipo": tipo, "nombre": nombre, "justificacion": "", "aplicada_en": []})
    pf = dict(i["proyecto_formativo"], formacion=_t(pres.get("nivel_formacion")),
              prerrequisitos=[_t(x) for x in _l(pres.get("prerrequisitos"))],
              correquisitos=[_t(x) for x in _l(pres.get("correquisitos"))])
    momentos = []
    for m in i["momentos"]:
        momentos.append({**m, "sesiones": [{
            **s, "docente": {**s["docente"], "horas": s["docente"]["horas"] or 0},
            "practico": {**s["practico"], "horas": s["practico"]["horas"] or 0},
            "autonomo": {**s["autonomo"], "horas": s["autonomo"]["horas"] or 0}} for s in m["sesiones"]]})
    return {
        "contrato": contrato_v2.VERSION, "facultad": i["facultad"], "carrera": i["carrera"], "periodo": i["periodo"],
        "proyecto_formativo": pf, "competencia_perfil": i["competencia_perfil"], "competencia_pf": i["competencia_pf"],
        "metacompetencia": i["metacompetencia"], "habilidades_blandas": [_t(x) for x in _l(mapa.get("habilidades_blandas"))],
        "ejes_transversales": ejes, "inclusion": _t(mapa.get("inclusion")),
        "contribucion_perfil": _t(mapa.get("contribucion_perfil")),
        "resultados_aprendizaje": i["resultados_aprendizaje"], "problema": i["problema"],
        "pis": {"aplica": True, "nombre": _t(mapa.get("pis_nombre")), "descripcion": "", "aporte": _t(mapa.get("pis_aporte")),
                "justificacion_na": ""},
        "metodologias": {"clase_invertida": vacio("antes", "durante", "despues"), "complementarias": complementarias},
        "momentos": momentos, "rubrica_producto_final": i["rubrica_producto_final"],
        "evaluacion": {"proceso": vacio("inicial", "seguimiento", "final"),
                       "agentes": vacio("autoevaluacion", "coevaluacion", "heteroevaluacion"),
                       "retroalimentacion": "", "metacompetencia": "", "gobernanza_ia": "",
                       "calificacion": {"componentes": [], "reglas": ""}, "mejora": "",
                       "credencial": {"aplica": True, **vacio("nombre", "desempeno", "evidencias", "criterios", "justificacion_na")}},
        "bibliografia": i["bibliografia"],
    }
