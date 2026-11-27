"""Apartados que agregó la plantilla de sílabo 2026 (docs/api-silabo/plantilla-2026.md).

Se localizan por su rótulo, como el resto del lector. Un apartado ausente queda vacío: así una
plantilla anterior produce el mismo resultado que antes y la escala lo marca ND.
"""
import re

from ciencia_datos.lector_pdf.presentacion import _debajo, _vinetas
from ciencia_datos.lector_pdf.texto import Tabla, limpio, normalizar_clave

# Rótulo normalizado de la fila del eje → clave del contrato 2.0.
EJES = (
    ("SOSTENIBILIDAD", "sostenibilidad_ods"),
    ("INTERCULTURALIDAD", "interculturalidad"),
    ("INTERNACIONALIZACION", "internacionalizacion"),
    ("INTERDISCIPLINARIEDAD", "interdisciplinariedad"),
    ("EMPRENDIMIENTO", "emprendimiento"),
    ("EDUCACION FINANCIERA", "educacion_financiera"),
)
_ODS = re.compile(r"\bODS\s*(?:N[°º.]?\s*)?(\d{1,2})\b", re.I)
_INTERNACIONAL = (("CLASE ESPEJO", "clase_espejo"), ("COIL", "coil"), ("MOVILIDAD", "movilidad"))


def _lineas(texto: str | None) -> list[str]:
    """Una línea = un elemento; «Ninguno» = lista vacía."""
    lineas = [limpio(l) for l in (texto or "").splitlines() if l.strip()]
    return [] if [normalizar_clave(l) for l in lineas] in ([], ["NINGUNO"]) else lineas


def _contenido(tablas: list[Tabla], rotulo: str) -> str:
    """Celda debajo del rótulo. Si el rótulo cierra su tabla (la tabla anterior se partió entre páginas),
    las celdas a su derecha; y si no hay, la primera celda de la tabla siguiente."""
    for t, tabla in enumerate(tablas):
        for i, fila in enumerate(tabla):
            for k, celda in enumerate(fila):
                if normalizar_clave(celda).startswith(rotulo):
                    if i + 1 < len(tabla):
                        siguiente = tabla[i + 1]
                        return limpio(siguiente[k] if k < len(siguiente) else "")
                    derecha = " ".join(c for c in fila[k + 1:] if c and c.strip())
                    if derecha:
                        return limpio(derecha)
                    if t + 1 < len(tablas) and tablas[t + 1]:
                        return limpio(next((c for c in tablas[t + 1][0] if c), ""))
                    return ""
    return ""


def _ejes(tablas: list[Tabla]) -> dict:
    ejes: dict[str, dict] = {}
    for tabla in tablas:
        if not tabla or not any(normalizar_clave(c).startswith("EJES TRANSVERSALES") for c in tabla[0] if c):
            continue
        ultimo = None
        for fila in tabla[2:]:
            celdas = [c or "" for c in fila] + ["", ""]
            rotulo, texto = normalizar_clave(celdas[0]), celdas[1]
            clave = next((k for r, k in EJES if rotulo.startswith(r)), None)
            if clave:
                ejes[clave] = {"descripcion": limpio(texto)}
                ultimo = clave
            elif not rotulo and ultimo and texto.strip():
                ejes[ultimo]["descripcion"] = limpio(f"{ejes[ultimo]['descripcion']} {texto}")
    if "sostenibilidad_ods" in ejes:
        numeros = {int(n) for n in _ODS.findall(ejes["sostenibilidad_ods"]["descripcion"]) if 1 <= int(n) <= 17}
        ejes["sostenibilidad_ods"]["ods"] = sorted(numeros)
    if "internacionalizacion" in ejes:
        texto = normalizar_clave(ejes["internacionalizacion"]["descripcion"])
        ejes["internacionalizacion"]["tipo"] = next((t for r, t in _INTERNACIONAL if r in texto), None)
    return ejes


def _entre(texto: str, desde: str, hasta: str) -> str:
    """Respaldo por texto: lo que va entre la línea que empieza con `desde` y la que empieza con `hasta`
    (rótulos normalizados). Sirve cuando la tabla mezcla el rótulo con el contenido."""
    lineas = (texto or "").splitlines()
    claves = [normalizar_clave(l) for l in lineas]
    inicio = next((k for k, c in enumerate(claves) if c.startswith(desde)), None)
    if inicio is None:
        return ""
    fin = next((k for k in range(inicio + 1, len(claves)) if claves[k].startswith(hasta)), len(claves))
    return limpio(" ".join(lineas[inicio + 1:fin]))


def leer_apartados_2026(tablas_ii: list[Tabla], tablas_iii: list[Tabla], texto_iii: str = "") -> dict:
    contribucion = (_contenido(tablas_iii, "CONTRIBUCION DEL PROYECTO FORMATIVO")
                    or _entre(texto_iii, "CONTRIBUCION DEL PROYECTO FORMATIVO", "PROBLEMA DEL TERRITORIO"))
    inclusion = (_contenido(tablas_iii, "INCLUSION Y ATENCION")
                 or _entre(texto_iii, "INCLUSION Y ATENCION", "RESULTADOS DE APRENDIZAJE"))
    return {
        "prerrequisitos": _lineas(_debajo(tablas_ii, "PROYECTOS FORMATIVOS PREVIOS")),
        "correquisitos": _lineas(_debajo(tablas_ii, "PROYECTOS FORMATIVOS QUE SE DEBEN CURSAR")),
        "formacion": limpio(_debajo(tablas_ii, "NIVEL DE FORMACION")),
        "habilidades_blandas": _vinetas(_debajo(tablas_iii, "HABILIDADES BLANDAS")),
        "ejes": _ejes(tablas_iii),
        "inclusion": inclusion,
        "contribucion_perfil": contribucion,
    }
