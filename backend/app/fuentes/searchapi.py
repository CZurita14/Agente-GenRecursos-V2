"""Fuentes web de la guía de estudio con SearchAPI (Google Scholar). Solo para la guía.

Las bases se parametrizan por perfil (agentes/<perfil>.yaml, `fuentes_bibliograficas`). Todas se
consultan por Google Scholar, que da el enlace directo, los autores, la revista y el año (lo que
pide la norma IEEE); el motor «google» devuelve enlaces de redirección cifrados y no se usa.
Scopus no está en SearchAPI: se aproxima con las editoriales que indexa (no es una consulta a Scopus).

Las consultas se arman con los temas del sílabo (contenidos del momento): nunca llevan datos del
docente ni de los estudiantes. El modelo cita cada fuente por su identificador ([F1], …) y la
bibliografía con los enlaces reales la arma el código. Se guardan por momento (`fuente_momento`)
para no gastar créditos al regenerar la guía.
"""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import urlparse

import httpx
from psycopg.types.json import Jsonb

registro = logging.getLogger(__name__)

MAX_FUENTES_WEB = 10
POR_BASE = 3  # Las primeras de cada base, alternando, para que ninguna acapare la bibliografía.

# id → (nombre que se muestra, filtro que se agrega a la consulta de Google Scholar).
BASES: dict[str, tuple[str, str]] = {
    "google_scholar": ("Google Scholar", ""),
    "scopus": ("Editoriales indexadas en Scopus (IEEE, Elsevier, Springer, ACM, MDPI)",
               "source:IEEE OR source:Elsevier OR source:Springer OR source:ACM OR source:MDPI"),
    "scielo": ("SciELO", "site:scielo.org OR site:scielo.cl OR site:scielo.org.co OR site:scielo.org.mx "
                         "OR site:scielo.br OR site:scielo.senescyt.gob.ec"),
    "repositorios": ("Repositorios académicos", "site:repositorio OR site:dspace OR site:handle.net OR site:edu.ec"),
}
# Redes sociales, video y sitios de copias no autorizadas: no son fuentes para una guía.
EXCLUIDOS = ("facebook.", "instagram.", "tiktok.", "twitter.", "x.com", "pinterest.", "youtube.", "youtu.be",
             "libgen", "z-lib", "sci-hub", "scribd.", "studocu.", "brainly.", "coursehero.", "monografias.com",
             "google.com")
_ANIO = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def _tema(texto: str) -> str:
    texto = re.sub(r"^[\s•\-–·*\d.)]+", "", texto or "")
    return " ".join(texto.split())[:70]


def consultas(contenidos: list[str], carrera: str, n: int, *, bases=("google_scholar",),
              desde: int | None = None) -> list[dict]:
    """Una consulta de Google Scholar por base (hasta `n`), con los temas del momento."""
    temas = [t for t in (_tema(c) for c in contenidos) if len(t) > 3]
    if not temas or n <= 0:
        return []
    principal = " ".join(temas[:3])[:160]
    pedidos = []
    for base in [b for b in bases if b in BASES][:n]:
        filtro = BASES[base][1]
        params = {"as_ylo": str(desde)} if desde else {}
        pedidos.append({"base": base, "motor": "google_scholar",
                        "q": f"{principal} {filtro}".strip(), "params": params})
    return pedidos


def _permitido(enlace: str) -> bool:
    u = urlparse(enlace or "")
    return u.scheme == "https" and bool(u.netloc) and not any(x in u.netloc.lower() for x in EXCLUIDOS)


def normalizar(r: dict, motor: str, base: str = "") -> dict | None:
    """Scholar: «autores - revista, año - dominio» en `publication`."""
    enlace = r.get("link") or ""
    if not _permitido(enlace) or not (r.get("title") or "").strip():
        return None
    publicacion = r.get("publication") or ""
    partes = [p.strip() for p in publicacion.split(" - ")] if publicacion else []
    autores = partes[0] if len(partes) >= 2 else ", ".join(a.get("name", "") for a in r.get("authors", []) if isinstance(a, dict))
    anio = (_ANIO.search(publicacion) or _ANIO.search(r.get("date") or "") or [None])[0]
    sitio = partes[-1] if len(partes) >= 2 else (r.get("source") or urlparse(enlace).netloc)
    revista = ""
    if len(partes) >= 3:
        revista = _ANIO.sub("", partes[1]).strip(" ,…")
    titulo = " ".join(r["title"].split()).strip("\"'“”«»‘’ ")  # La referencia IEEE pone sus propias comillas.
    return {"titulo": titulo[:300], "autores": " ".join(autores.split())[:200],
            "anio": anio, "sitio": " ".join(str(sitio).split())[:120], "tipo": (r.get("type") or "").lower()[:40],
            "enlace": enlace[:600], "fragmento": " ".join((r.get("snippet") or "").split())[:400], "motor": motor,
            "base": base, "revista": revista[:160]}


def _pedido(p) -> dict:
    if isinstance(p, dict):
        return p
    motor, q = p  # Forma corta (motor, consulta).
    return {"base": motor, "motor": motor, "q": q, "params": {}}


def buscar(clave: str, url: str, pedidos: list, *, verificar_tls=True, http=None,
           anotar=None) -> tuple[list[dict], int, str | None]:
    """Fuentes únicas (por enlace), alternando bases, con id F1…; devuelve (fuentes, créditos, error).

    `anotar(motor, consulta, ok, resultados, error, segundos)` se llama por cada consulta enviada (un crédito).
    """
    por_base, vistos, gastados, error = [], set(), 0, None
    cliente = http or httpx.Client(timeout=30, verify=verificar_tls)
    try:
        for p in map(_pedido, pedidos):
            inicio, enviada, propias = time.monotonic(), False, []
            etiqueta = f"{p['motor']}:{p['base']}"
            try:
                r = cliente.get(url, params={"engine": p["motor"], "q": p["q"], "hl": "es", **p["params"]},
                                headers={"Authorization": f"Bearer {clave}"})
                enviada = True
                gastados += 1
                r.raise_for_status()
                resultados = r.json().get("organic_results", [])
            except (httpx.HTTPError, ValueError) as e:
                error = type(e).__name__  # Sin el cuerpo: podría traer la clave en la URL.
                registro.warning("SearchAPI no respondió (%s)", error)
                if enviada and anotar:
                    anotar(etiqueta, p["q"], False, 0, error, round(time.monotonic() - inicio, 3))
                continue
            if anotar:
                anotar(etiqueta, p["q"], True, len(resultados), None, round(time.monotonic() - inicio, 3))
            for res in resultados:
                f = normalizar(res, p["motor"], p["base"]) if isinstance(res, dict) else None
                if f and f["enlace"] not in vistos:
                    vistos.add(f["enlace"])
                    propias.append(f)
            por_base.append(propias[:POR_BASE] if len(pedidos) > 1 else propias)
    finally:
        if http is None:
            cliente.close()
    # Alternar bases: la 1.ª de cada una, luego la 2.ª, … (orden de prioridad del perfil).
    fuentes = [lista[k] for k in range(max((len(x) for x in por_base), default=0))
               for lista in por_base if k < len(lista)][:MAX_FUENTES_WEB]
    return [{"id": f"F{k}", **f} for k, f in enumerate(fuentes, 1)], gastados, error


def fuentes_momento(conn, config, asignatura_id, numero: int, contenidos: list[str], carrera: str,
                    *, bases=("google_scholar",), desde: int | None = None, http=None) -> list[dict]:
    """Fuentes web guardadas del momento; si no hay y SearchAPI está configurado, las busca una vez."""
    fila = conn.execute("select fuentes from fuente_momento where asignatura_id=%s and momento=%s",
                        (asignatura_id, numero)).fetchone()
    if fila is not None:
        return fila["fuentes"]
    if config.searchapi_key is None:
        return []
    pedidos = consultas(contenidos, carrera, config.searchapi_consultas_por_momento, bases=bases, desde=desde)
    if not pedidos:
        return []

    def anotar(motor, consulta, ok, resultados, error, segundos):
        conn.execute("insert into busqueda_web (asignatura_id,momento,motor,consulta,ok,resultados,error,segundos) "
                     "values (%s,%s,%s,%s,%s,%s,%s,%s)",
                     (asignatura_id, numero, motor, consulta[:300], ok, resultados, error, segundos))

    fuentes, gastados, error = buscar(config.searchapi_key.get_secret_value(), config.searchapi_url, pedidos,
                                      verificar_tls=config.llm_tls_estricto, http=http, anotar=anotar)
    if fuentes or not error:
        # Un fallo total no se guarda: el próximo intento vuelve a buscar.
        conn.execute("insert into fuente_momento (asignatura_id,momento,fuentes,consultas,creditos,error) "
                     "values (%s,%s,%s,%s,%s,%s) on conflict (asignatura_id,momento) do nothing",
                     (asignatura_id, numero, Jsonb(fuentes), Jsonb([p["q"] for p in pedidos]), gastados, error))
    return fuentes


def bibliografia_silabo(silabo) -> list[dict]:
    """La bibliografía del sílabo con id B1…: la base de la guía, antes que la web."""
    b = silabo.bibliografia
    entradas = [("basica", t) for t in b.basica] + [("complementaria", t) for t in b.complementaria]
    return [{"id": f"B{k}", "tipo": tipo, "texto": " ".join(t.split())[:600]}
            for k, (tipo, t) in enumerate(((x, t) for x, t in entradas if t.strip()), 1)]


def texto_fuentes(fuentes: dict) -> str:
    """Las fuentes como datos para el prompt (van dentro de <fuentes>)."""
    lineas = [f"[{b['id']}] Bibliografía {b['tipo']} del sílabo: {b['texto']}" for b in fuentes.get("silabo", [])]
    for f in fuentes.get("web", []):
        ref = " · ".join(x for x in (f["autores"], f.get("revista", ""), f["anio"] or "", f["sitio"]) if x)
        base = BASES.get(f.get("base", ""), ("",))[0]
        lineas.append(f"[{f['id']}] {f['titulo']} ({ref}{'; ' + base if base else ''}). Resumen: {f['fragmento']}")
    return " | ".join(lineas)
