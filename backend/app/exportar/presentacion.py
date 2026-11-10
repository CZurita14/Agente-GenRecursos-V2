"""Presentación ordenada de cada herramienta: la misma para revisar y para exportar.

El contenido se guarda en jsonb, que no conserva el orden de las claves, y sus claves
son internas («clase_id», «numero_clase»). Aquí cada herramienta declara qué se muestra,
en qué orden y con qué título, como una lista de bloques:

- texto: {"tipo": "texto", "titulo", "texto", "ruta"}
- lista: {"tipo": "lista", "titulo", "items": [str], "numerada": bool, "ruta"}
- tabla: {"tipo": "tabla", "titulo", "columnas": [str], "filas": [[str]], "rutas": [[ruta | None]]}
- grupo: {"tipo": "grupo", "titulo", "bloques": [...]}

`ruta` es el camino dentro del contenido (claves e índices) del texto que el docente puede
editar (P6c); None si no se edita: herramientas sin IA, valores de listas cerradas
(indicador, momento, RA, nivel) y textos compuestos.

Los cuestionarios (ítems con opciones) no pasan por aquí: tienen su propia vista.
"""
from collections.abc import Callable
import re

NIVELES = {"receptivo": "Receptivo", "resolutivo": "Resolutivo", "reflexivo": "Reflexivo",
           "critico": "Crítico", "cocreativo": "Cocreativo"}
TITULOS = {
    "ideas_clave": "Ideas clave", "relacion_ra": "Relación con el resultado de aprendizaje", "errores_frecuentes": "Errores frecuentes",
    "autocomprobacion": "Autocomprobación", "que_se_pide": "Qué se pide", "como_se_valora": "Cómo se valora",
    "errores_comunes": "Errores comunes", "autochequeo": "Autochequeo", "conexion_ra": "Conexión con el resultado de aprendizaje",
    "preguntas_repaso": "Preguntas de repaso", "respuesta_orientativa": "Respuesta orientativa",
    "que_observar": "Qué observar", "como_prepararse": "Cómo prepararse", "producto_final": "Producto final",
    "politica_ia": "Política de IA", "clase_id": "Clase", "para_subir": "Para subir de nivel",
}
_OCULTAS = {"item_id", "escenario"}  # Datos internos del sistema, no para el estudiante.
SIN_POLITICA = "No indicada en el sílabo"


def nombre_ambito(ambito_id: str) -> str:
    """«M1-S2» → «Momento 1, sesión 2»; «M2» → «Momento 2»; «asignatura» → «Proyecto Formativo»."""
    return "Proyecto Formativo" if ambito_id == "asignatura" else legible(str(ambito_id))


def legible(texto: str) -> str:
    """Códigos internos o del sílabo a nombres completos, también dentro de lo que redacta la IA.

    Solo al mostrar: el contenido guardado no cambia y los identificadores siguen igual.
    """
    texto = re.sub(r"\bM([1-9]\d?)-S([1-9]\d?)\b", r"Momento \1, sesión \2", texto)
    texto = re.sub(r"\bRA([1-9]\d?)\b", r"Resultado de aprendizaje \1", texto)
    texto = re.sub(r"\bM([1-9]\d?)\b", r"Momento \1", texto)
    texto = re.sub(r"\b(los|Los|sus|Sus) RA\b", r"\1 resultados de aprendizaje", texto)
    return re.sub(r"\bRA\b", "resultado de aprendizaje", texto)


def legibles(b: dict) -> dict:
    """Aplica `legible` a un bloque; las rutas de edición no se tocan."""
    salida = dict(b)
    for clave in ("titulo", "texto"):
        if isinstance(salida.get(clave), str):
            salida[clave] = legible(salida[clave])
    for clave in ("items", "columnas"):
        if clave in salida:
            salida[clave] = [legible(x) if isinstance(x, str) else x for x in salida[clave]]
    if "filas" in salida:
        salida["filas"] = [[legible(c) if isinstance(c, str) else c for c in f] for f in salida["filas"]]
    if "bloques" in salida:
        salida["bloques"] = [legibles(x) for x in salida["bloques"]]
    return salida


Ruta = list[str | int]


def _texto(titulo: str, texto, ruta: Ruta | None = None) -> dict:
    return {"tipo": "texto", "titulo": titulo, "texto": str(texto), "ruta": ruta}


def _lista(titulo: str, items, numerada: bool = False, ruta: Ruta | None = None) -> dict:
    return {"tipo": "lista", "titulo": titulo, "items": [str(x) for x in items or []], "numerada": numerada,
            "ruta": ruta}


def _tabla(titulo: str, columnas: list[str], filas, rutas: list[list[Ruta | None]] | None = None) -> dict:
    filas = [[str(c) if c is not None else "" for c in f] for f in filas]
    return {"tipo": "tabla", "titulo": titulo, "columnas": columnas, "filas": filas,
            "rutas": rutas or [[None] * len(f) for f in filas]}


def _grupo(titulo: str, bloques: list[dict]) -> dict:
    return {"tipo": "grupo", "titulo": titulo, "bloques": bloques}


def _fecha(iso) -> str:
    """«2026-10-14» → «14/10/2026»."""
    s = str(iso or "")
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if len(s) >= 10 else s


def _momento(c: dict) -> dict:
    return _texto("Momento", f"Momento {c['momento']} · {c.get('titulo', '')}".rstrip(" ·"))


def _rubrica(indicadores: list[dict], niveles: list[str]) -> dict:
    return _tabla("Rúbrica", ["Indicador", *(NIVELES.get(n, n) for n in niveles)],
                  [[f["indicador"], *(f["descriptores"].get(n, "") for n in niveles)] for f in indicadores])


def _ficha(c: dict) -> list[dict]:
    conceptual, aplicacion = c["conceptual"], c["aplicacion"]
    ejemplo = aplicacion["ejemplo"]
    e = ["aplicacion", "ejemplo"]
    return [
        _lista("Ideas clave", conceptual["ideas_clave"], ruta=["conceptual", "ideas_clave"]),
        _texto("Relación con el resultado de aprendizaje", conceptual["relacion_ra"], ["conceptual", "relacion_ra"]),
        _lista("Errores frecuentes", conceptual["errores_frecuentes"], ruta=["conceptual", "errores_frecuentes"]),
        _grupo("Ejemplo resuelto", [_texto("Enunciado", ejemplo["enunciado"], [*e, "enunciado"]),
                                    _lista("Pasos", ejemplo["pasos"], numerada=True, ruta=[*e, "pasos"]),
                                    _texto("Resultado", ejemplo["resultado"], [*e, "resultado"])]),
        _lista("Autocomprobación", aplicacion["autocomprobacion"], numerada=True,
               ruta=["aplicacion", "autocomprobacion"]),
    ]


def _repaso(c: dict) -> list[dict]:
    r = c["repaso"]
    return [
        *(_grupo(nombre_ambito(s['clase_id']), [_lista("Ideas clave", s["ideas_clave"],
                                                   ruta=["repaso", "sesiones", n, "ideas_clave"])])
          for n, s in enumerate(r["sesiones"])),
        _texto("Conexión con el resultado de aprendizaje", r["conexion_ra"], ["repaso", "conexion_ra"]),
        _lista("Preguntas de repaso", r["preguntas_repaso"], numerada=True, ruta=["repaso", "preguntas_repaso"]),
    ]


def _guia(c: dict) -> list[dict]:
    g = c["guia"]
    return [
        _texto("Qué se pide", g["que_se_pide"], ["guia", "que_se_pide"]),
        _tabla("Cómo se valora", ["Indicador", "Qué observar"],
               [[x["indicador"], x["que_observar"]] for x in g["como_se_valora"]],
               [[None, ["guia", "como_se_valora", n, "que_observar"]] for n in range(len(g["como_se_valora"]))]),
        _lista("Errores comunes", g["errores_comunes"], ruta=["guia", "errores_comunes"]),
        _lista("Autochequeo", g["autochequeo"], numerada=True, ruta=["guia", "autochequeo"]),
    ]


def _caso(c: dict) -> list[dict]:
    caso = c["caso"]
    return [
        _texto("Caso", caso["caso"], ["caso", "caso"]),
        _texto("Se relaciona con", caso["ra"]),
        *(_grupo(f"Pregunta {n + 1} · {NIVELES.get(p['nivel'], p['nivel'])}",
                 [_texto("Pregunta", p["pregunta"], ["caso", "preguntas", n, "pregunta"]),
                  _texto("Respuesta orientativa", p["respuesta_orientativa"],
                         ["caso", "preguntas", n, "respuesta_orientativa"])])
          for n, p in enumerate(caso["preguntas"])),
    ]


def _guia_final(c: dict) -> list[dict]:
    g = c["guia_final"]
    return [
        _tabla("Ruta por momentos", ["Momento", "Aporte al producto final"], [[x["momento"], x["aporte"]] for x in g["ruta"]],
               [[None, ["guia_final", "ruta", n, "aporte"]] for n in range(len(g["ruta"]))]),
        _tabla("Criterios", ["Indicador", "Cómo prepararse"], [[x["indicador"], x["como_prepararse"]] for x in g["criterios"]],
               [[None, ["guia_final", "criterios", n, "como_prepararse"]] for n in range(len(g["criterios"]))]),
        _lista("Recomendaciones", g["recomendaciones"], ruta=["guia_final", "recomendaciones"]),
    ]


def _hoja_ruta(c: dict) -> list[dict]:
    p = c["periodo"]
    return [
        _texto("Proyecto Formativo", f"{c['asignatura']} ({c['codigo']})"),
        _texto("Periodo", f"{p['codigo']} · {_fecha(p['inicio'])} – {_fecha(p['fin'])}"),
        _tabla("Momentos", ["Momento", "Fechas", "Resultados de aprendizaje", "Evidencia", "Política de IA"],
               [[f"{m['numero']}. {m['titulo']}", f"{_fecha(m['fecha_inicio'])} – {_fecha(m['fecha_fin'])}",
                 ", ".join(m["ra"]), m["evidencia"], m.get("politica_ia") or SIN_POLITICA] for m in c["momentos"]]),
        _tabla("Calendario de clases", ["Semana", "Clase", "Fecha", "Contenidos", "Entregables"],
               [[s["numero"], f"Clase {k['numero_clase']} · {nombre_ambito(k['clase_id'])}", _fecha(k["fecha"]),
                 "; ".join(k["contenidos"]), "; ".join(k["entregables"])]
                for s in c["semanas"] for k in s["clases"]]),
        _texto("Producto final", c["producto_final"]),
    ]


def _autoevaluacion(c: dict) -> list[dict]:
    return [
        _texto("Instrucciones", c["instrucciones"]),
        _momento(c),
        _texto("Evidencia", c["evidencia"]),
        _lista("Resultados de aprendizaje", [f"{r['id']}: {r['texto']}" for r in c["ra"]]),
        _rubrica(c["indicadores"], c["niveles"]),
        _texto("Política de IA", c.get("politica_ia") or SIN_POLITICA),
    ]


def _autoevaluacion_final(c: dict) -> list[dict]:
    return [
        _texto("Instrucciones", c["instrucciones"]),
        _texto("Producto final", c["evidencia"]),
        _rubrica(c["indicadores"], c["niveles"]),
        _lista("Política de IA por momento",
               [f"Momento {p['momento']}: {p.get('politica_ia') or SIN_POLITICA}" for p in c["politica_ia"]]),
    ]


def _lista_evidencia(c: dict) -> list[dict]:
    return [
        _momento(c),
        _texto("Evidencia", c["evidencia"]),
        _lista("Entregables", c["entregables"]),
        _tabla("Antes de entregar, verifica", ["Indicador", "Mínimo esperado (nivel resolutivo)"],
               [[x["indicador"], x["referencia_resolutivo"]] for x in c["items"]]),
        _texto("Política de IA", c.get("politica_ia") or SIN_POLITICA),
    ]


def _rubrica_momento(c: dict) -> list[dict]:
    return [
        _momento(c),
        _texto("Evidencia que se evalúa", c["evidencia"]),
        _lista("Resultados de aprendizaje", [f"{r['id']}: {r['texto']}" for r in c["ra"]]),
        _rubrica(c["indicadores"], c["niveles"]),
    ]


def _rubrica_final(c: dict) -> list[dict]:
    return [_texto("Producto final que se evalúa", c["evidencia"]), _rubrica(c["indicadores"], c["niveles"])]


def _practica(c: dict) -> list[dict]:
    p = c["practica"]
    ejercicios = [_grupo(f"Ejercicio {n}", [
        _texto("Enunciado", e["enunciado"], ["practica", "ejercicios", n - 1, "enunciado"]),
        _lista("Pasos", e["pasos"], numerada=True, ruta=["practica", "ejercicios", n - 1, "pasos"]),
        _texto("Resultado esperado", e["resultado_esperado"], ["practica", "ejercicios", n - 1, "resultado_esperado"]),
    ]) for n, e in enumerate(p["ejercicios"], 1)]
    return [_texto("Objetivo", p["objetivo"], ["practica", "objetivo"]), *ejercicios,
            _lista("Errores a evitar", p["errores_a_evitar"], ruta=["practica", "errores_a_evitar"])]


def _tarjetas(c: dict) -> list[dict]:
    return [_tabla("Tarjetas de estudio", ["Frente", "Reverso", "Contenido"],
                   [[t["frente"], t["reverso"], t["contenido"]] for t in c["mazo"]["tarjetas"]],
                   [[["mazo", "tarjetas", k, "frente"], ["mazo", "tarjetas", k, "reverso"], None]
                    for k in range(len(c["mazo"]["tarjetas"]))])]


def _guia_autonoma(c: dict) -> list[dict]:
    g = c["guia_autonoma"]
    bloques = [_texto("Objetivo", g["objetivo"], ["guia_autonoma", "objetivo"]),
               _texto("Actividad", g["actividad"], ["guia_autonoma", "actividad"]),
               _lista("Pasos", g["pasos"], numerada=True, ruta=["guia_autonoma", "pasos"]),
               _texto("Tiempo estimado", g["tiempo_estimado"], ["guia_autonoma", "tiempo_estimado"]),
               _texto("Para la siguiente clase", g["para_la_siguiente_clase"],
                      ["guia_autonoma", "para_la_siguiente_clase"]),
               _lista("Autochequeo", g["autochequeo"], ruta=["guia_autonoma", "autochequeo"])]
    if g.get("conexion_pis", "").strip():
        bloques.append(_texto("Aporte al PIS", g["conexion_pis"], ["guia_autonoma", "conexion_pis"]))
    return bloques


def _guion(c: dict) -> list[dict]:
    g = c["guion"]
    bloques = [_texto("Objetivo de la sesión", g["objetivo"], ["guion", "objetivo"]),
               _tabla("Desarrollo de la clase", ["Fase", "Minutos", "Docente", "Estudiantes"],
                      [[f["fase"].capitalize(), f["minutos"], f["docente"], f["estudiantes"]] for f in g["fases"]],
                      [[None, None, ["guion", "fases", k, "docente"], ["guion", "fases", k, "estudiantes"]]
                       for k in range(len(g["fases"]))]),
               _lista("Preguntas detonantes", g["preguntas_detonantes"], ruta=["guion", "preguntas_detonantes"])]
    if g.get("conexion_pis", "").strip():
        bloques.append(_texto("Conexión con el PIS", g["conexion_pis"], ["guion", "conexion_pis"]))
    return bloques


VISTAS: dict[str, Callable[[dict], list[dict]]] = {
    "practica_guiada": _practica, "tarjetas": _tarjetas, "guia_autonoma": _guia_autonoma, "guion_clase": _guion,
    "rubrica_momento": _rubrica_momento, "rubrica_final": _rubrica_final,
    "ficha_clase": _ficha, "repaso_momento": _repaso, "guia_evidencia": _guia, "estudio_caso": _caso,
    "guia_producto_final": _guia_final, "hoja_ruta": _hoja_ruta, "autoevaluacion_rubrica": _autoevaluacion,
    "autoevaluacion_final": _autoevaluacion_final, "lista_evidencia": _lista_evidencia,
}


def _titulo(clave: str) -> str:
    return TITULOS.get(clave, clave.replace("_", " ").capitalize())


def _generica(valor, titulo: str = "") -> list[dict]:
    """Respaldo para formas no previstas: claves ordenadas alfabéticamente y títulos legibles."""
    if isinstance(valor, dict):
        bloques = [b for k in sorted(valor) if k not in _OCULTAS and valor[k] not in (None, "", [], {})
                   for b in _generica(valor[k], _titulo(k))]
        return [_grupo(titulo, bloques)] if titulo else bloques
    if isinstance(valor, list):
        if all(not isinstance(x, (dict, list)) for x in valor):
            return [_lista(titulo, valor)]
        return [_grupo(f"{titulo} {n}".strip(), _generica(x)) for n, x in enumerate(valor, 1)]
    return [_texto(titulo, valor)]


def sin_respuestas(b: dict) -> dict:
    """Quita las respuestas orientativas de un bloque, también dentro de grupos anidados."""
    if b.get("tipo") != "grupo":
        return b
    return {**b, "bloques": [sin_respuestas(x) for x in b["bloques"] if x.get("titulo") != "Respuesta orientativa"]}


def es_quiz(contenido) -> bool:
    return isinstance(contenido, list) and bool(contenido) and all(isinstance(i, dict) and "opciones" in i for i in contenido)


def presentar(herramienta: str, contenido) -> list[dict]:
    """Bloques ordenados de la herramienta; [] para cuestionarios (vista propia)."""
    if es_quiz(contenido):
        return []
    vista = VISTAS.get(herramienta)
    if vista and isinstance(contenido, dict):
        try:
            return [legibles(b) for b in vista(contenido)]
        except (KeyError, TypeError, AttributeError):
            pass  # Contenido editado o de un esquema anterior: se muestra igual, sin perder nada.
    return [legibles(b) for b in _generica(contenido)]
