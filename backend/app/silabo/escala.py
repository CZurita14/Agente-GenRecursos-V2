"""Escala general de evaluación de sílabos (UTI, 23/10/2026) sobre el contrato v2.0.

- `revision_automatica` arma la evaluación inicial de un sílabo v2.0: deduce del JSON los ND
  (componente vacío) y los NA (exclusión declarada con su justificación), marca los pendientes que se
  comprueban sin interpretar texto y deja en null (por valorar) los puntos que necesitan juicio.
- `calcular` aplica la fórmula de la escala: puntos ÷ (aplicables × 5) × peso; NA fuera del
  denominador, ND vale 0; en IV se suman los momentos.
Catálogo: docs/api-silabo/escala-silabo.json. Formato del resultado: evaluacion-silabo.schema.json.
Los avisos y sugerencias nombran rutas del JSON, nunca valores del sílabo.
"""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

CATALOGO = Path(__file__).resolve().parents[3] / "docs" / "api-silabo" / "escala-silabo.json"
INSTRUMENTO = "UTI 23/10/2026"
_IGNORAR = {"aplica", "justificacion_na"}


@lru_cache(maxsize=1)
def catalogo() -> dict:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))


def vacio(valor) -> bool:
    """Sin contenido: None, texto en blanco, lista vacía u objeto cuyos valores (salvo aplica y justificacion_na) están vacíos."""
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    if isinstance(valor, list):
        return all(vacio(v) for v in valor)
    if isinstance(valor, dict):
        return all(vacio(v) for k, v in valor.items() if k not in _IGNORAR)
    return False  # números y booleanos son dato


def _resolver(raiz, ruta: str) -> list:
    """Valores en `ruta` (claves con puntos; `x[]` recorre la lista x)."""
    actuales = [raiz]
    for parte in ruta.split("."):
        lista = parte.endswith("[]")
        clave = parte[:-2] if lista else parte
        siguientes = []
        for a in actuales:
            v = a.get(clave) if isinstance(a, dict) else None
            if lista:
                siguientes.extend(v if isinstance(v, list) else [])
            else:
                siguientes.append(v)
        actuales = siguientes
    return actuales


def _sin_dato(raiz, rutas: list[str]) -> bool:
    return all(vacio(_resolver(raiz, r)) for r in rutas)


def _punto(codigo, valor=None, justificacion="", sugerencia="", pendiente=False, fuente="automatica", **extra):
    return {"codigo": codigo, **extra, "valor": valor, "fuente": fuente, "justificacion": justificacion,
            "sugerencia": sugerencia, "pendiente": pendiente}


def _nd(codigo, rutas, **extra):
    return _punto(codigo, "ND", sugerencia="Sin dato en: " + ", ".join(rutas), **extra)


def _fecha(v):
    try:
        return date.fromisoformat(v) if isinstance(v, str) else None
    except ValueError:
        return None


def _ids_sesion(silabo: dict) -> set[str]:
    ids = set()
    for m in silabo.get("momentos") or []:
        for s in m.get("sesiones") or []:
            ids.add(s.get("id") or f"M{m.get('numero')}-S{s.get('numero')}")
    return ids


def _exclusion(silabo: dict, codigo: str):
    """(aplica, justificacion) del bloque que declara la exclusión de este punto, o None si no tiene."""
    bloques = {"III.5": "sostenibilidad_ods", "III.6": "interculturalidad", "III.7": "internacionalizacion",
               "III.8": "interdisciplinariedad", "III.9": "emprendimiento", "III.10": "educacion_financiera"}
    if codigo in bloques:
        b = (silabo.get("ejes_transversales") or {}).get(bloques[codigo]) or {}
    elif codigo in ("III.19", "III.20"):
        b = silabo.get("pis") or {}
    elif codigo == "V.12":
        b = (silabo.get("evaluacion") or {}).get("credencial") or {}
    else:
        return None
    return b.get("aplica") is not False, (b.get("justificacion_na") or "").strip()


def _metodologia(silabo: dict, p: dict, ids: set[str]) -> dict:
    elegidas = [m for m in (silabo.get("metodologias") or {}).get("complementarias") or []
                if m.get("tipo") == p["metodologia"]]
    if not elegidas:
        return _punto(p["codigo"], "NA", justificacion="Metodología no seleccionada por el docente.")
    sin_justificar = any(vacio(m.get("justificacion")) for m in elegidas)
    aplicadas = [i for m in elegidas for i in m.get("aplicada_en") or []]
    faltan = [i for i in aplicadas if i not in ids]
    notas = []
    if sin_justificar:
        notas.append("selección sin decisión pedagógica (justificacion vacía)")
    if not aplicadas:
        notas.append("no se refleja en ninguna actividad (aplicada_en vacía)")
    if faltan:
        notas.append("aplicada_en nombra sesiones que no existen")
    return _punto(p["codigo"], sugerencia="; ".join(notas), pendiente=bool(notas))


def _momento(m: dict, i: int, p: dict) -> dict:
    codigo, numero = p["codigo"], m.get("numero")
    rutas = [r.removeprefix("momentos[].") for r in p["rutas"]]
    if _sin_dato(m, rutas):
        return _nd(codigo, [f"momentos[{i}].{r}" for r in rutas], momento=numero)
    if codigo == "IV.2":
        ini, fin = _fecha(m.get("fecha_inicio")), _fecha(m.get("fecha_fin"))
        fechas = [_fecha(s.get("fecha")) for s in m.get("sesiones") or []]
        fuera = [f for f in fechas if f and ini and fin and not ini <= f <= fin]
        if (ini and fin and ini > fin) or fuera:
            return _punto(codigo, momento=numero, pendiente=True,
                          sugerencia=f"momentos[{i}]: fechas del momento incoherentes con sus sesiones")
    return _punto(codigo, momento=numero)


def _calificacion(silabo: dict) -> dict:
    c = (silabo.get("evaluacion") or {}).get("calificacion") or {}
    if _sin_dato(silabo, ["evaluacion.calificacion"]):
        return _nd("V.10", ["evaluacion.calificacion"])
    suma = sum(x.get("porcentaje") or 0 for x in c.get("componentes") or [])
    if c.get("componentes") and abs(suma - 100) > 1e-9:
        return _punto("V.10", pendiente=True, sugerencia="evaluacion.calificacion.componentes: los porcentajes no suman 100")
    return _punto("V.10")


def revision_automatica(silabo: dict, etapa: str = "inicio", fecha: str | None = None) -> dict:
    """Evaluación inicial (formato evaluacion-silabo.schema.json) de un sílabo v2.0 ya validado."""
    ids = _ids_sesion(silabo)
    ras = {r.get("id"): r for r in silabo.get("resultados_aprendizaje") or []}
    puntos = []
    for p in catalogo()["puntos"]:
        codigo = p["codigo"]
        if p["fuera_del_contrato"]:
            puntos.append(_punto(codigo, fuente="evaluador",
                                 sugerencia="Se valora fuera del sistema: la API no envía este apartado."))
        elif p["repetir_por"] == "ra":
            campo = p["rutas"][0].split(".")[-1]
            for k in range(1, 5):
                ra = f"RA{k}"
                if ra not in ras:
                    if k > 1:
                        puntos.append(_punto(codigo, "NA", ra=ra, justificacion="RA no declarado en el sílabo."))
                    continue
                pos = list(ras).index(ra)
                if vacio(ras[ra].get(campo)):
                    puntos.append(_nd(codigo, [f"resultados_aprendizaje[{pos}].{campo}"], ra=ra))
                else:
                    puntos.append(_punto(codigo, ra=ra))
        elif p["repetir_por"] == "momento":
            for i, m in enumerate(silabo.get("momentos") or []):
                puntos.append(_momento(m, i, p))
        elif "metodologia" in p:
            puntos.append(_metodologia(silabo, p, ids))
        elif (ex := _exclusion(silabo, codigo)) and not ex[0]:
            puntos.append(_punto(codigo, "NA", justificacion=ex[1]))
        elif codigo == "V.10":
            puntos.append(_calificacion(silabo))
        elif _sin_dato(silabo, p["rutas"]):
            puntos.append(_nd(codigo, p["rutas"]))
        else:
            puntos.append(_punto(codigo))
    pf = silabo.get("proyecto_formativo") or {}
    evaluacion = {
        "formato": "1.0",
        "instrumento": INSTRUMENTO,
        "silabo": {"codigo": pf.get("codigo"), "version": pf.get("version")},
        "revision": {"etapa": etapa, "fecha": fecha or date.today().isoformat()},
        "puntos": puntos,
    }
    evaluacion.update(calcular(puntos))
    return evaluacion


def calcular(puntos: list[dict]) -> dict:
    """Apartados, total y si la evaluación está completa, con la fórmula de la escala."""
    apartados = {}
    for a in catalogo()["apartados"]:
        suyos = [p for p in puntos if p["codigo"].split(".")[0] == a["codigo"]]
        valores = [p["valor"] for p in suyos]
        na = valores.count("NA")
        nd = valores.count("ND")
        por_valorar = sum(v is None for v in valores)
        aplicables = len(valores) - na
        obtenidos = sum(v for v in valores if isinstance(v, int) and not isinstance(v, bool))
        maximo = aplicables * 5
        resultado = None
        if not por_valorar:
            if not maximo:
                raise ValueError(f"apartado {a['codigo']}: sin preguntas aplicables")
            resultado = round(obtenidos / maximo * a["peso"], 2)
        apartados[a["codigo"]] = {
            "peso": a["peso"], "puntos": obtenidos, "maximo": maximo, "aplicables": aplicables, "na": na, "nd": nd,
            "por_valorar": por_valorar, "pendientes": sum(bool(p["pendiente"]) for p in suyos), "resultado": resultado,
        }
    completa = all(a["resultado"] is not None for a in apartados.values())
    total = round(sum(a["resultado"] for a in apartados.values()), 2) if completa else None
    return {"apartados": apartados, "total": total, "completa": completa}


def validar_evaluacion(evaluacion: dict, silabo: dict) -> list[str]:
    """Reglas que el esquema no expresa: puntos completos y sin repetir, y cifras iguales a `calcular`."""
    fallos = []
    momentos = [m.get("numero") for m in silabo.get("momentos") or []]
    esperados = []
    for p in catalogo()["puntos"]:
        if p["repetir_por"] == "ra":
            esperados += [(p["codigo"], f"RA{k}", None) for k in range(1, 5)]
        elif p["repetir_por"] == "momento":
            esperados += [(p["codigo"], None, n) for n in momentos]
        else:
            esperados.append((p["codigo"], None, None))
    ras = {r.get("id") for r in silabo.get("resultados_aprendizaje") or []}
    vistos = [(p["codigo"], p.get("ra"), p.get("momento")) for p in evaluacion.get("puntos", [])]
    for clave in sorted(set(vistos), key=vistos.index):
        if vistos.count(clave) > 1:
            fallos.append(f"puntos {clave}: repetido")
    for clave in esperados:
        if clave not in vistos:
            fallos.append(f"puntos {clave}: falta")
    for clave in vistos:
        if clave not in esperados:
            fallos.append(f"puntos {clave}: no corresponde al sílabo")
    for p in evaluacion.get("puntos", []):
        if p["codigo"] in ("III.12", "III.13"):
            if p.get("ra") in ras and p["valor"] == "NA":
                fallos.append(f"puntos ({p['codigo']}, {p['ra']}): NA en un RA declarado")
            if p.get("ra") not in ras and p["valor"] != "NA":
                fallos.append(f"puntos ({p['codigo']}, {p['ra']}): RA no declarado; debe ser NA")
    calculado = calcular(evaluacion.get("puntos", []))
    for k in ("apartados", "total", "completa"):
        if evaluacion.get(k) != calculado[k]:
            fallos.append(f"{k}: no coincide con el cálculo de la escala")
    return fallos
