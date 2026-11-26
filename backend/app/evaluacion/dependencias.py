"""Dependencias entre sesiones (prompt institucional §6) (V4-2).

Cada tarea (columna práctico-experimental o autónoma) es **independiente** o **complementaria**: continúa o amplía
un producto previo («versión final del prototipo», «Práctica 2, fase de desarrollo», «a partir del diagnóstico de la
sesión 4»). Para una complementaria se busca su **insumo previo**, en este orden:
1. la sesión, la práctica o el momento que nombra («sesión 4», «Práctica 2», «Momento 2»);
2. el producto que nombra (prototipo, portafolio, programa…), en la sesión anterior más cercana que lo menciona, en
   cualquiera de sus columnas o en sus entregables.

Si no hay origen, o el origen no tiene horas en esa columna, es un **eslabón roto** (§6.3). La cadena del producto del
PF entre momentos (§6.5) no se revisa con reglas (ver `alertas_dependencias`). Reglas deterministas sobre el texto: no
se llama a la IA y los avisos nombran sesiones, nunca texto del sílabo.
"""
import re
from dataclasses import dataclass

from app.silabo.modelo import SilaboUTI

COLUMNAS_TAREA = ("practico", "autonomo")
_ORDEN_COLUMNAS = ("docente", "asincronica", "practico", "autonomo")
NOMBRE_COLUMNA = {"docente": "con el docente", "asincronica": "otras actividades con el docente",
                  "practico": "práctico-experimental", "autonomo": "trabajo autónomo"}


def _r(patron: str) -> re.Pattern:
    return re.compile(patron, re.I)


# Marcadores de una tarea que continúa un producto previo.
_COMPLEMENTARIA = _r(
    r"\bversi[oó]n (corregida|final|mejorada|definitiva|ajustada|actualizada|revisada|2)\b|\b(segunda|nueva) versi[oó]n\b"
    r"|\biteraci[oó]n\b|\bitera(r)?\b|\bajustes?\b(?! (razonables?|dua|curricular))|\bajustar\b|\bmejoras derivadas\b|\b(aplica|aplicaci[oó]n de) (las )?mejoras\b|\bmejorar (el|la|los|las)\b"
    r"|\bincorpora(r|ci[oó]n)?\b(?! (la |de la )?retroalimentaci)|\bfase de (desarrollo|entrega|cierre)\b|\bcontin[uú]a (con|el|la|los|las)\b|\bcontinuar (con|el|la|los|las)\b|\bcontinuaci[oó]n (de|del)\b"
    r"|\b(elaborad|construid|desarrollad|realizad|diseñad|iniciad)[oa]s? (en|durante) (la|el) (sesi[oó]n|momento|pr[aá]ctica)"
    r"|\bpr[aá]ctica \d+,? (entrega|fase)\b|\bcomplet(a|ar) (el|la|los|las) (prototipo|programa|portafolio|informe|modelo|diagn[oó]stico|ficha|mapa|atlas)"
    r"|\ba partir (de|del) (la |el |los |las )?(avance|prototipo|programa|portafolio|informe|modelo|diagn[oó]stico|ficha|"
    r"mapa|resultados|retroalimentaci[oó]n|sesi[oó]n|momento|pr[aá]ctica|versi[oó]n|dataset|script|algoritmo|propuesta|dise[ñn]o)")
# Dependencias que no continúan un producto: lecturas previas y conocimientos previos (§6.2 independiente).
_NO_PRODUCTO = _r(r"\b(lectura previa|prerrequisito|conocimientos previos|bibliograf[ií]a|propuesta de ajuste|ajustes? razonables?)\b")

_SESION = _r(r"\bsesi[oó]n (\d{1,2})\b")
_MOMENTO = _r(r"\bmomento (\d)\b")
_PRACTICA = _r(r"\bpr[aá]ctica (?:de aprendizaje experimental )?(\d{1,2})\b")

# Productos que suelen pasar de una sesión a otra; la forma base y su patrón (con plural).
PRODUCTOS = {
    # El prototipo del PIS es un insumo de otro proyecto, no de una sesión de este sílabo.
    "prototipo": r"prototipos?\b(?! del (pis|proyecto integrador))", "portafolio": r"portafolios?",
    # Solo el programa informático («el programa en Python», «al programa»), no los programas de gobierno o de estudio.
    "programa": r"(el|al|del|un) programa\b(?! (de|del) )",
    "script": r"scripts?", "aplicación": r"aplicaci[oó]n(es)? (m[oó]vil|web)|\bapp\b",
    "diagnóstico": r"diagn[oó]sticos? (territorial|situacional|del caso|inicial)?", "informe": r"informes?",
    "ficha": r"fichas? (de|del) (an[aá]lisis|observaci[oó]n|caso|lectura)", "mapa": r"mapas?\b(?! (conceptual|mental))",
    "atlas": r"atlas", "algoritmo": r"algoritmos?", "diagrama": r"diagramas?", "dataset": r"dataset|conjunto de datos|base de datos",
    "maqueta": r"maquetas?", "propuesta": r"propuestas?", "diseño": r"dise[ñn]os?\b", "ensayo": r"ensayos?\b",
    "bitácora": r"bit[aá]coras?", "plan": r"\bplan (de (acci[oó]n|intervenci[oó]n|cuidados|negocio|trabajo|mejora))",
    "repositorio": r"repositorios?", "manual": r"manual(es)?\b", "planos": r"planos?\b", "infografía": r"infograf[ií]as?",
    "secuencia": r"secuencias? (did[aá]ctica|de actividades)", "material": r"material(es)? did[aá]ctic",
    "instrumento": r"instrumentos? (de|para) (recolecci[oó]n|evaluaci[oó]n|diagn[oó]stico)",
}
_PRODUCTOS = {k: _r(r"\b" + v) for k, v in PRODUCTOS.items()}


@dataclass(frozen=True)
class Dependencia:
    sesion: str                  # «M3-S4»
    columna: str                 # practico | autonomo
    tipo: str                    # independiente | complementaria
    insumo: str | None = None    # producto o referencia que necesita («prototipo», «Práctica 2», «sesión 4»)
    origen: str | None = None    # «M2-S3/practico», «M2/evidencia» o None
    roto: bool = False           # nombra una sesión, práctica o momento que no existe, o el origen no tiene horas (§6.3)
    revisar: bool = False        # continúa un producto que no aparece en las sesiones anteriores: revísalo


@dataclass(frozen=True)
class _Columna:
    sesion: str
    numero: int                  # número global de la sesión
    momento: int
    columna: str
    texto: str
    horas: float | None


def _columnas(silabo: SilaboUTI) -> list[_Columna]:
    filas = []
    for m in silabo.momentos:
        for s in m.sesiones:
            asincronica = s.docente.asincronica
            datos = {"docente": (s.docente.texto, s.docente.horas),
                     "asincronica": (asincronica.texto, asincronica.horas) if asincronica else ("", None),
                     "practico": (s.practico.texto, s.practico.horas), "autonomo": (s.autonomo.texto, s.autonomo.horas)}
            texto_entregables = " ".join(s.entregables)
            for c in _ORDEN_COLUMNAS:
                texto, horas = datos[c]
                if c == "autonomo" and texto_entregables:
                    texto = f"{texto} {texto_entregables}".strip()
                if texto.strip():
                    filas.append(_Columna(s.id, s.numero, m.numero, c, texto, horas))
    return filas


def productos_de(texto: str) -> list[str]:
    return [k for k, rx in _PRODUCTOS.items() if rx.search(texto)]


def _es_complementaria(texto: str) -> bool:
    """Lecturas previas y prerrequisitos son tareas independientes aunque nombren productos (§6.2)."""
    return bool(_COMPLEMENTARIA.search(texto)) and not _NO_PRODUCTO.search(texto)


def _sin_horas(c: _Columna) -> bool:
    return c.horas is not None and c.horas <= 0


def _origen(actual: _Columna, previas: list[_Columna], silabo: SilaboUTI) -> tuple[str | None, str | None, bool, bool]:
    """(insumo, origen, roto, revisar) de una tarea complementaria.

    Roto solo con una referencia explícita que no existe o un origen sin horas. Si el producto no aparece antes, se
    pide revisar: buscar por el nombre del producto es una señal débil (el sílabo puede nombrarlo de otra forma).
    """
    texto = actual.texto
    if (m := _SESION.search(texto)) and int(m.group(1)) < actual.numero:
        n = int(m.group(1))
        candidatas = [c for c in previas if c.numero == n]
        if candidatas:
            # La columna de la sesión de origen que comparte producto con la tarea; si no, la última con texto.
            mismo = [c for c in candidatas if set(productos_de(c.texto)) & set(productos_de(texto))]
            c = (mismo or candidatas)[-1]
            return f"sesión {n}", f"{c.sesion}/{c.columna}", _sin_horas(c), False
        return f"sesión {n}", None, True, False
    if (m := _MOMENTO.search(texto)) and int(m.group(1)) < actual.momento:
        n = int(m.group(1))
        existe = any(x.numero == n and x.evidencia.strip() for x in silabo.momentos)
        return f"Momento {n}", f"M{n}/evidencia" if existe else None, not existe, False
    if m := _PRACTICA.search(texto):
        n = m.group(1)
        propia = _r(rf"\bpr[aá]ctica (?:de aprendizaje experimental )?{n}\b")
        anteriores = [c for c in previas if propia.search(c.texto)]
        if anteriores:
            c = anteriores[0]  # Donde empieza la práctica.
            return f"Práctica {n}", f"{c.sesion}/{c.columna}", _sin_horas(c), False
    antes = [c for c in previas if c.sesion != actual.sesion]
    misma = [c for c in previas if c.sesion == actual.sesion]
    for grupo in (antes, misma):
        for producto in productos_de(texto):
            rx = _PRODUCTOS[producto]
            for c in reversed(grupo):
                if rx.search(c.texto):
                    return producto, f"{c.sesion}/{c.columna}", _sin_horas(c), False
    # Sin origen reconocible: se pide revisar (con o sin producto nombrado), nunca se afirma que esté roto.
    productos = productos_de(texto)
    return (productos[0] if productos else None), None, False, True


def dependencias(silabo: SilaboUTI) -> list[Dependencia]:
    """Una por tarea (columna práctico-experimental o autónoma con texto), en orden del sílabo."""
    columnas = _columnas(silabo)
    salida = []
    for k, c in enumerate(columnas):
        if c.columna not in COLUMNAS_TAREA:
            continue
        if not _es_complementaria(c.texto):
            salida.append(Dependencia(c.sesion, c.columna, "independiente"))
            continue
        insumo, origen, roto, revisar = _origen(c, columnas[:k], silabo)
        salida.append(Dependencia(c.sesion, c.columna, "complementaria", insumo, origen, roto, revisar))
    return salida


def legible(clave: str) -> str:
    sesion, columna = clave.split("/")
    if columna == "evidencia":
        return f"la evidencia del {sesion.replace('M', 'Momento ')}"
    m = re.fullmatch(r"M(\d+)-S(\d+)", sesion)
    return f"Momento {m.group(1)}, sesión {m.group(2)} ({NOMBRE_COLUMNA.get(columna, columna)})" if m else clave


def alertas_dependencias(silabo: SilaboUTI, deps: list[Dependencia] | None = None) -> list[str]:
    """§6.3: eslabones rotos de las tareas. Nombran sesiones, no texto del sílabo.

    La cadena entre evidencias de momentos (§6.5) no se revisa con reglas: en el corpus B26 la señal salía en más de
    la mitad de las transiciones y no distinguía cadenas rotas de evidencias redactadas sin repetir el producto.
    """
    deps = dependencias(silabo) if deps is None else deps
    alertas = []
    for d in deps:
        if not d.roto:
            continue
        if d.origen:
            alertas.append(f"{d.sesion} ({NOMBRE_COLUMNA[d.columna]}): continúa «{d.insumo}» de {legible(d.origen)}, "
                           "que no tiene horas en esa columna (§6.3).")
        else:
            alertas.append(f"{d.sesion} ({NOMBRE_COLUMNA[d.columna]}): se apoya en la {d.insumo}, que no existe en el "
                           "sílabo; corrige la referencia o agrega la actividad que produce el insumo (§6.3).")
    revisar = [f"{d.sesion} ({NOMBRE_COLUMNA[d.columna]})" for d in deps if d.revisar]
    if revisar:
        alertas.append("Revisa el insumo previo de estas tareas, que continúan un producto sin un origen claro en las "
                       f"sesiones anteriores: {', '.join(revisar)} (§6.1).")
    return alertas
