"""Corpus de entrenamiento: fragmentos académicos de los sílabos, sin datos personales.

Solo se leen archivos `.json` con el sílabo crudo del SGA: cada uno pasa por `a_contrato` (lista blanca
que descarta docente, contacto y firmas) y por `cargar_silabo`, y de ahí sale un `SilaboUTI`, que por
construcción no tiene perfil docente ni contacto. Los `.pdf` se ignoran (se avisa cuántos) y los JSON
que no cumplen el contrato se descartan.
Como segunda barrera, se descarta todo fragmento con correos, ORCID o números largos.
Nada de este módulo imprime ni registra texto de los sílabos.
"""
import json
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

from app.sga.traductor import a_contrato
from app.silabo.integridad import cargar_silabo
from app.silabo.modelo import SilaboUTI

_PERSONAL = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"      # correo
    r"|\b\d{4}-\d{4}-\d{4}-\d{3}[\dXx]\b"  # ORCID
    r"|\d{7,}"                           # teléfono, cédula u otra secuencia larga
    # Título (sin distinguir mayúsculas) y punto, con espacio opcional, seguido de una palabra con
    # mayúscula inicial: "Dra. Ana", "Dr.Juan"; no "Ing. de requisitos".
    r"|(?<!\w)(?i:Dra?|Ing|Mgs|M\.?Sc|Mgtr|Mg|Mtra|Mtr|Lic|Lcd[oa]|Abg|Arq|Prof|Econ)\.\s*[A-ZÁÉÍÓÚÑ]"
    r"|(?<!\w)(?i:Ph\.?D)\.?\s+[A-ZÁÉÍÓÚÑ]"
)


@dataclass(frozen=True)
class Fragmento:
    codigo_pf: str
    facultad: str
    carrera: str
    momento: int | None
    tipo: str
    texto: str


def tiene_datos_personales(texto: str) -> bool:
    """Si el texto parece traer correo, ORCID, número largo o un título con nombre propio."""
    return _PERSONAL.search(" ".join(texto.split())) is not None


def _limpio(texto: str) -> str | None:
    t = " ".join(texto.split())
    return t if t and not tiene_datos_personales(t) else None


def fragmentos(silabo: SilaboUTI) -> list[Fragmento]:
    """Contenidos, actividades, resultados y evidencias; sin vacíos ni repetidos."""
    base = (silabo.proyecto_formativo.codigo, silabo.facultad, silabo.carrera)
    crudos: list[tuple[int | None, str, str]] = [
        (None, "resultado", r.texto) for r in silabo.resultados_aprendizaje
    ]
    for m in silabo.momentos:
        crudos.append((m.numero, "evidencia", m.evidencia))
        for s in m.sesiones:
            crudos += [(m.numero, "contenido", c) for c in s.contenidos]
            crudos += [
                (m.numero, "actividad", t)
                for t in (s.docente.texto, s.practico.texto, s.autonomo.texto)
            ]
    vistos: set[str] = set()
    salida: list[Fragmento] = []
    for momento, tipo, texto in crudos:
        t = _limpio(texto)
        if t is None or t in vistos:
            continue
        vistos.add(t)
        salida.append(Fragmento(*base, momento, tipo, t))
    return salida


def leer_carpeta(carpeta: Path | list[Path]) -> tuple[list[SilaboUTI], list[str]]:
    """Los sílabos de `leer_con_origen`, sin su ruta; acepta una carpeta o varias."""
    con_origen, rechazados = leer_con_origen(carpeta)
    return [s for s, _ in con_origen], rechazados


def por_carpeta(rutas: list[Path], raiz: Path) -> dict[str, int]:
    """Cuántas rutas hay por carpeta de primer nivel bajo `raiz` (`.` si están en ella), sin nombres de archivo."""
    cuenta: dict[str, int] = {}
    for ruta in rutas:
        partes = ruta.relative_to(raiz).parts
        nombre = partes[0] if len(partes) > 1 else "."
        cuenta[nombre] = cuenta.get(nombre, 0) + 1
    return dict(sorted(cuenta.items()))


def leer_con_origen(carpeta: Path | list[Path]) -> tuple[list[tuple[SilaboUTI, Path]], list[str]]:
    """Lee los `*.json` de una carpeta, o de varias, y sus subcarpetas.

    Cada JSON se trata como el sílabo crudo del SGA: pasa por `a_contrato` (que descarta lo
    que el contrato no declara, incluidos los datos personales) y por `cargar_silabo`.
    Los `*.pdf` se ignoran y se avisa cuántos eran.

    Conserva una versión por código de proyecto formativo: la de `aprobado` más
    reciente y, a igualdad, la de mayor nombre de archivo. Devuelve también los
    nombres de archivo rechazados, sin el motivo, que podría contener texto.
    """
    elegidos: dict[str, tuple[tuple, SilaboUTI, Path]] = {}
    rechazados: list[str] = []
    ignorados = 0
    carpetas = carpeta if isinstance(carpeta, (list, tuple)) else [carpeta]
    rutas = [r for c in carpetas for r in sorted(Path(c).rglob("*"))]
    for ruta in rutas:
        sufijo = ruta.suffix.lower()
        if sufijo not in (".pdf", ".json") or not ruta.is_file():
            continue
        if sufijo == ".pdf":
            ignorados += 1
            continue
        try:
            silabo = cargar_silabo(a_contrato(json.loads(ruta.read_bytes())))
        except Exception:
            rechazados.append(ruta.name)
            continue
        clave = (silabo.proyecto_formativo.aprobado, ruta.name)
        codigo = silabo.proyecto_formativo.codigo
        if codigo not in elegidos or clave > elegidos[codigo][0]:
            elegidos[codigo] = (clave, silabo, ruta)
    if ignorados:
        warnings.warn(f"{ignorados} PDF ignorados: el corpus solo lee JSON del SGA", UserWarning, stacklevel=2)
    return [(s, r) for _, s, r in elegidos.values()], rechazados
