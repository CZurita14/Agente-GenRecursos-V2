"""Imágenes para las diapositivas: Pexels (con clave) y, si no hay resultado, Openverse (sin clave).

Solo se envían a estos servicios las palabras de búsqueda que propone el modelo, nunca el sílabo.
La imagen se descarga al generar y se guarda en la tabla `imagen` por su SHA-256: la web y el .pptx
la sirven desde la base, sin depender del servicio externo ni abrir el servidor a URL arbitrarias.
"""
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

registro = logging.getLogger("app.imagenes")

MAX_BYTES = 5 * 1024 * 1024
TIPOS = {"image/jpeg", "image/png", "image/webp", "image/gif"}
# Openverse: solo licencias que permiten reutilizar con atribución (sin NC ni ND).
LICENCIAS_OPENVERSE = "by,by-sa,cc0,pdm"
NOMBRES_LICENCIA = {"by": "CC BY", "by-sa": "CC BY-SA", "cc0": "CC0", "pdm": "Dominio público"}


@dataclass(frozen=True)
class Imagen:
    datos: bytes
    tipo: str
    autor: str
    licencia: str
    fuente: str
    enlace: str

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.datos).hexdigest()

    def credito(self) -> dict:
        return {"hash": self.hash, "autor": self.autor[:200], "licencia": self.licencia[:80],
                "fuente": self.fuente, "enlace": self.enlace[:500]}


def _descargar(cliente: httpx.Client, url: str) -> tuple[bytes, str] | None:
    try:
        with cliente.stream("GET", url, follow_redirects=True) as r:
            tipo = r.headers.get("content-type", "").split(";")[0].strip().lower()
            if r.status_code != 200 or tipo not in TIPOS:
                return None
            datos = b""
            for parte in r.iter_bytes():
                datos += parte
                if len(datos) > MAX_BYTES:
                    return None
            return (datos, tipo) if datos else None
    except httpx.HTTPError:
        return None


def _pexels(cliente: httpx.Client, consulta: str, clave: str, usadas: set[str]) -> Imagen | None:
    r = cliente.get("https://api.pexels.com/v1/search", headers={"Authorization": clave},
                    params={"query": consulta, "per_page": 5, "orientation": "landscape"})
    if r.status_code != 200:
        return None
    for foto in r.json().get("photos", []):
        url = (foto.get("src") or {}).get("large")
        if not url or url in usadas:
            continue
        bajada = _descargar(cliente, url)
        if bajada:
            usadas.add(url)
            return Imagen(*bajada, autor=str(foto.get("photographer") or "Autor en Pexels"),
                          licencia="Licencia Pexels", fuente="Pexels", enlace=str(foto.get("url") or ""))
    return None


def _openverse(cliente: httpx.Client, consulta: str, usadas: set[str]) -> Imagen | None:
    r = cliente.get("https://api.openverse.org/v1/images/",
                    params={"q": consulta, "license": LICENCIAS_OPENVERSE, "mature": "false", "page_size": 5})
    if r.status_code != 200:
        return None
    for res in r.json().get("results", []):
        # La miniatura de Openverse (~600 px) es rápida y estable; el original puede ser enorme o estar caído.
        candidatas = [u for u in (res.get("thumbnail"), res.get("url")) if u and u not in usadas]
        for url in candidatas:
            bajada = _descargar(cliente, url)
            if bajada:
                usadas.add(url)
                licencia = NOMBRES_LICENCIA.get(str(res.get("license", "")).lower(), str(res.get("license", "")))
                return Imagen(*bajada, autor=str(res.get("creator") or "Autor desconocido"), licencia=licencia,
                              fuente="Openverse", enlace=str(res.get("foreign_landing_url") or res.get("url") or ""))
    return None


def crear_buscador(*, pexels_clave: str | None, verificar=True, timeout_s: float = 15,
                   transporte: httpx.BaseTransport | None = None) -> Callable[[str, set[str]], Imagen | None]:
    """Devuelve buscar(consulta, usadas) -> Imagen | None. Nunca lanza: una imagen no detiene la generación."""
    def buscar(consulta: str, usadas: set[str]) -> Imagen | None:
        consulta = " ".join(consulta.split())[:60]
        if not consulta:
            return None
        try:
            with httpx.Client(timeout=timeout_s, verify=verificar, transport=transporte,
                              headers={"User-Agent": "RecursosDeEstudio/2.0"}) as cliente:
                # Si la búsqueda completa no da nada, se prueba con sus dos primeras palabras.
                palabras = consulta.split()
                consultas = [consulta] + ([" ".join(palabras[:2])] if len(palabras) > 2 else [])
                for q in consultas:
                    fuentes = ([lambda: _pexels(cliente, q, pexels_clave, usadas)] if pexels_clave else [])
                    fuentes.append(lambda: _openverse(cliente, q, usadas))
                    for fuente in fuentes:
                        try:  # Un servicio lento o caído no impide probar el siguiente.
                            imagen = fuente()
                        except (httpx.HTTPError, ValueError) as exc:
                            registro.warning("Búsqueda de imagen fallida (%s)", type(exc).__name__)
                            continue
                        if imagen:
                            return imagen
                return None
        except (httpx.HTTPError, ValueError) as exc:
            registro.warning("No se pudo buscar una imagen (%s)", type(exc).__name__)
            return None
    return buscar


def guardar(conn, imagen: Imagen) -> None:
    conn.execute("insert into imagen (hash,tipo,datos) values (%s,%s,%s) on conflict (hash) do nothing",
                 (imagen.hash, imagen.tipo, imagen.datos))


def leer(conn, hash_: str) -> tuple[bytes, str] | None:
    fila = conn.execute("select datos,tipo from imagen where hash=%s", (hash_,)).fetchone()
    return (bytes(fila["datos"]), fila["tipo"]) if fila else None


def hashes(contenido) -> set[str]:
    """Hashes de las imágenes que el contenido referencia (las únicas que se sirven de ese recurso)."""
    encontrados: set[str] = set()

    def recorrer(v):
        if isinstance(v, dict):
            img = v.get("imagen")
            if isinstance(img, dict) and isinstance(img.get("hash"), str):
                encontrados.add(img["hash"])
            for x in v.values():
                recorrer(x)
        elif isinstance(v, list):
            for x in v:
                recorrer(x)
    recorrer(contenido)
    return encontrados
