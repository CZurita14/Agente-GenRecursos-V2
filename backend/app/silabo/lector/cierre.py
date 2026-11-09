"""Sección V (rúbrica del producto final) y sección VI (bibliografía)."""
import re

from app.silabo.lector.momentos import leer_rubrica
from app.silabo.lector.texto import Tabla, limpio, normalizar_clave

_ANIO = re.compile(r"\(\d{4}\)\.")
# Una línea que termina así, dentro de una URL, continúa la URL sin espacio.
_CORTE_URL = re.compile(r"https?://\S*[./?&=_-]$")


def leer_rubrica_final(tablas_v: list[Tabla]) -> list[dict]:
    return leer_rubrica([fila for tabla in tablas_v for fila in tabla])


def _referencias(lineas: list[str]) -> list[str]:
    """Una referencia empieza en la línea con «(AAAA).»; las demás la continúan."""
    refs: list[str] = []
    for linea in lineas:
        if _ANIO.search(linea) or not refs:
            refs.append(linea)
        elif _CORTE_URL.search(refs[-1]):
            refs[-1] += linea
        else:
            refs[-1] += " " + linea
    return [limpio(r) for r in refs]


def leer_bibliografia(texto_vi: str) -> dict:
    """Referencias tal como están escritas; no se completan ni se inventan datos."""
    listas: dict[str, list[str]] = {"basica": [], "complementaria": []}
    actual = None
    for linea in (l.strip() for l in texto_vi.splitlines()):
        clave = normalizar_clave(linea)
        if clave.startswith("BIBLIOGRAFIA BASICA"):
            actual = "basica"
        elif clave.startswith("BIBLIOGRAFIA COMPLEMENTARIA"):
            actual = "complementaria"
        elif actual and linea:
            listas[actual].append(linea)
    return {k: _referencias(v) for k, v in listas.items()}
