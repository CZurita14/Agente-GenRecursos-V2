"""Referencias en norma IEEE para la guía de estudio.

- Las citas se numeran [1], [2], … por orden de primera aparición en el texto; lo guardado conserva
  los identificadores ([B1], [F2]) y la numeración se aplica al mostrar y exportar.
- Fuentes web (Google Scholar): «N. Apellido, «Título», Revista, año. [En línea]. Disponible en: URL».
- Bibliografía del sílabo: viene en APA («Apellido, N. (año). Título. Editorial.»); se convierte a IEEE
  cuando tiene esa forma y, si no, se muestra tal cual.
"""
import re

CITA = re.compile(r"\[([BF]\d+)\]")
_INICIALES_SCHOLAR = re.compile(r"^([A-ZÁÉÍÓÚÑ]{1,3})\s+(.+)$")
_AUTOR_APA = re.compile(r"([^,&]+?),\s*((?:[A-ZÁÉÍÓÚÑ]\.\s?-?\s?)+)")
_APA = re.compile(r"^(?P<a>.+?)\s*\((?P<y>(?:19|20)\d{2}[a-z]?|s\.\s?f\.)\)\.?\s*(?P<r>.+)$")
_URL = re.compile(r"https?://\S+")
# Revista con volumen y páginas: «12(3), 45-60», «vol.», «pp. 4», «, 102, 179-191».
_ARTICULO = re.compile(r"\d+\s*\(\d+\)|\bvol\.|\bpp?\.\s*\d|,\s*\d+\s*,\s*\d+\s*[-–]\s*\d+", re.I)


def _lista(autores: list[str]) -> str:
    if len(autores) > 6:
        return f"{autores[0]} et al."
    if len(autores) <= 2:
        return " y ".join(autores)
    return ", ".join(autores[:-1]) + " y " + autores[-1]


def autores_scholar(texto: str) -> str:
    """«DE Vázquez, E Hernández…» → «D. E. Vázquez, E. Hernández et al.»."""
    truncado = "…" in texto or texto.rstrip().endswith("...")
    nombres = []
    for parte in [p.strip(" .…") for p in texto.replace("…", ",").split(",") if p.strip(" .…")]:
        m = _INICIALES_SCHOLAR.match(parte)
        nombres.append(f"{' '.join(c + '.' for c in m.group(1))} {m.group(2)}" if m else parte)
    if not nombres:
        return ""
    return f"{', '.join(nombres)} et al." if truncado else _lista(nombres)


def referencia_web(f: dict) -> str:
    partes = [autores_scholar(f.get("autores", "")), f"«{f['titulo']}»", f.get("revista", ""), f.get("anio") or ""]
    cuerpo = ", ".join(p for p in partes if p)
    return f"{cuerpo}. [En línea]. Disponible en: {f['enlace']}"


_APELLIDO_INICIALES = re.compile(r"^(?P<ape>[^\s]+(?:\s[^\s]+)?)\s+(?P<ini>(?:[A-ZÁÉÍÓÚÑ]\.?){1,3})\.?$")


def _autor_suelto(nombre: str) -> str:
    """Un autor de una lista con «;»: «Matthias Steup» → «M. Steup»; «Lalaleo-Analuisa F.R.» → «F. R. Lalaleo-Analuisa»;
    una sola palabra (organización) queda igual."""
    nombre = " ".join(nombre.split()).strip(" .,")
    if "," in nombre:  # «APELLIDOS, NOMBRES»
        ape, nom = (x.strip() for x in nombre.split(",", 1))
        return f"{' '.join(p[0] + '.' for p in nom.split())} {ape}".strip()
    m = _APELLIDO_INICIALES.match(nombre)
    if m:
        return f"{' '.join(c + '.' for c in re.findall(r'[A-ZÁÉÍÓÚÑ]', m.group('ini')))} {m.group('ape')}"
    palabras = nombre.split()
    if len(palabras) < 2:
        return nombre
    if nombre.isupper() and len(palabras) >= 3:
        # Estilo de nómina: «APELLIDO APELLIDO NOMBRE NOMBRE».
        apellidos, nombres = palabras[:2], palabras[2:]
        return f"{' '.join(p[0] + '.' for p in nombres)} {' '.join(apellidos)}"
    apellidos = palabras[-2:] if len(palabras) >= 4 else palabras[-1:]
    nombres = palabras[:len(palabras) - len(apellidos)]
    return f"{' '.join(p[0] + '.' for p in nombres)} {' '.join(apellidos)}"


def referencia_silabo(texto: str) -> str:
    """APA → IEEE; si la entrada no tiene la forma «Autor (año). Resto», queda tal cual."""
    m = _APA.match(" ".join(texto.split()))
    if not m:
        return texto
    pares = _AUTOR_APA.findall(m.group("a").replace(";", ","))  # Algunos sílabos separan con «;».
    if pares:
        autores = _lista([f"{ini.strip()} {ape.strip(' &')}" for ape, ini in pares])
    elif ";" in m.group("a"):
        autores = _lista([_autor_suelto(n) for n in m.group("a").split(";") if n.strip(" .")])
    else:
        autores = m.group("a").strip(" .")
    resto = m.group("r")
    url = _URL.search(resto)
    sin_url = _URL.sub("", resto).strip(" .")
    titulo, _, detalle = sin_url.partition(". ")
    anio = m.group("y")
    if _ARTICULO.search(detalle):
        ref = f"{autores}, «{titulo.strip()}», {detalle.strip(' .')}, {anio}"
    else:
        ref = ", ".join(x for x in (autores, titulo.strip(), detalle.strip(" .")) if x) + f", {anio}"
    return ref + (f". [En línea]. Disponible en: {url.group(0).rstrip('.')}" if url else ".")


def numeracion(textos: list[str]) -> dict[str, int]:
    """id de fuente → número IEEE, por orden de primera aparición."""
    orden: dict[str, int] = {}
    for t in textos:
        for cita in CITA.findall(t):
            orden.setdefault(cita, len(orden) + 1)
    return orden


def renumerar(texto: str, orden: dict[str, int]) -> str:
    """«[B1]» → «[1]»; une citas seguidas: «[1], [3]» queda como está (IEEE lo admite)."""
    return CITA.sub(lambda m: f"[{orden[m.group(1)]}]" if m.group(1) in orden else m.group(0), texto)
