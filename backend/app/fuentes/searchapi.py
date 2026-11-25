"""Fuentes web de la guía de estudio con SearchAPI (Google Scholar y Google). Solo para la guía.

Las consultas se arman con los temas del sílabo (contenidos del momento y carrera): nunca llevan
datos del docente ni de los estudiantes. Cada resultado conserva su enlace real: el modelo solo
puede citarlo por su identificador ([F1], [F2], …) y la bibliografía la arma el código.
Se guardan por momento (tabla `fuente_momento`) para no gastar créditos al regenerar la guía.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import httpx
from psycopg.types.json import Jsonb

registro = logging.getLogger(__name__)

MAX_FUENTES_WEB = 8
# Redes sociales, video y sitios de copias no autorizadas: no son fuentes para una guía.
EXCLUIDOS = ("facebook.", "instagram.", "tiktok.", "twitter.", "x.com", "pinterest.", "youtube.", "youtu.be",
             "libgen", "z-lib", "sci-hub", "scribd.", "studocu.", "brainly.", "coursehero.", "monografias.com")
_ANIO = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def _tema(texto: str) -> str:
    texto = re.sub(r"^[\s•\-–·*\d.)]+", "", texto or "")
    return " ".join(texto.split())[:70]


def consultas(contenidos: list[str], carrera: str, n: int) -> list[tuple[str, str]]:
    """(motor, consulta): Google Scholar para lo académico y Google para material abierto."""
    temas = [t for t in (_tema(c) for c in contenidos) if len(t) > 3]
    if not temas or n <= 0:
        return []
    principal = " ".join(temas[:3])[:160]
    lista = [("google_scholar", principal),
             ("google", f"{' '.join(temas[:2])} {carrera.lower()} pdf"[:160])]
    return lista[:n]


def _permitido(enlace: str) -> bool:
    u = urlparse(enlace or "")
    return u.scheme == "https" and bool(u.netloc) and not any(x in u.netloc.lower() for x in EXCLUIDOS)


def normalizar(r: dict, motor: str) -> dict | None:
    enlace = r.get("link") or ""
    if not _permitido(enlace) or not (r.get("title") or "").strip():
        return None
    publicacion = r.get("publication") or ""
    partes = [p.strip() for p in publicacion.split(" - ")] if publicacion else []
    autores = partes[0] if len(partes) >= 2 else ", ".join(a.get("name", "") for a in r.get("authors", []) if isinstance(a, dict))
    anio = (_ANIO.search(publicacion) or _ANIO.search(r.get("date") or "") or [None])[0]
    sitio = partes[-1] if len(partes) >= 2 else (r.get("source") or urlparse(enlace).netloc)
    return {"titulo": " ".join(r["title"].split())[:300], "autores": " ".join(autores.split())[:200],
            "anio": anio, "sitio": " ".join(str(sitio).split())[:120], "tipo": (r.get("type") or "").lower()[:40],
            "enlace": enlace[:600], "fragmento": " ".join((r.get("snippet") or "").split())[:400], "motor": motor}


def buscar(clave: str, url: str, pedidos: list[tuple[str, str]], *, verificar_tls=True, http=None) -> tuple[list[dict], int, str | None]:
    """Fuentes únicas (por enlace), con id F1…; devuelve (fuentes, créditos gastados, error)."""
    fuentes, vistos, gastados, error = [], set(), 0, None
    cliente = http or httpx.Client(timeout=30, verify=verificar_tls)
    try:
        for motor, q in pedidos:
            try:
                r = cliente.get(url, params={"engine": motor, "q": q, "hl": "es"},
                                headers={"Authorization": f"Bearer {clave}"})
                gastados += 1
                r.raise_for_status()
                resultados = r.json().get("organic_results", [])
            except (httpx.HTTPError, ValueError) as e:
                error = type(e).__name__  # Sin el cuerpo: podría traer la clave en la URL.
                registro.warning("SearchAPI no respondió (%s)", error)
                continue
            for res in resultados:
                f = normalizar(res, motor) if isinstance(res, dict) else None
                if f and f["enlace"] not in vistos:
                    vistos.add(f["enlace"])
                    fuentes.append(f)
    finally:
        if http is None:
            cliente.close()
    fuentes = fuentes[:MAX_FUENTES_WEB]
    return [{"id": f"F{k}", **f} for k, f in enumerate(fuentes, 1)], gastados, error


def fuentes_momento(conn, config, asignatura_id, numero: int, contenidos: list[str], carrera: str,
                    *, http=None) -> list[dict]:
    """Fuentes web guardadas del momento; si no hay y SearchAPI está configurado, las busca una vez."""
    fila = conn.execute("select fuentes from fuente_momento where asignatura_id=%s and momento=%s",
                        (asignatura_id, numero)).fetchone()
    if fila is not None:
        return fila["fuentes"]
    if config.searchapi_key is None:
        return []
    pedidos = consultas(contenidos, carrera, config.searchapi_consultas_por_momento)
    if not pedidos:
        return []
    fuentes, gastados, error = buscar(config.searchapi_key.get_secret_value(), config.searchapi_url, pedidos,
                                      verificar_tls=config.llm_tls_estricto, http=http)
    if fuentes or not error:
        # Un fallo total no se guarda: el próximo intento vuelve a buscar.
        conn.execute("insert into fuente_momento (asignatura_id,momento,fuentes,consultas,creditos,error) "
                     "values (%s,%s,%s,%s,%s,%s) on conflict (asignatura_id,momento) do nothing",
                     (asignatura_id, numero, Jsonb(fuentes), Jsonb([q for _, q in pedidos]), gastados, error))
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
        ref = " · ".join(x for x in (f["autores"], f["anio"] or "", f["sitio"]) if x)
        lineas.append(f"[{f['id']}] {f['titulo']} ({ref}). Resumen: {f['fragmento']}")
    return " | ".join(lineas)
