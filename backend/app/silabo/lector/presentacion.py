"""Portada, sección II (presentación) y sección III (mapa de formación).

Los campos se localizan por su rótulo normalizado, nunca por posición fija.
La portada se lee solo hasta «Docente:»: el nombre del docente no se toca.
"""
import re
from datetime import date

from app.silabo.lector.errores import SilaboIlegible
from app.silabo.lector.texto import Tabla, filas, fecha_dmy, horas, limpio, normalizar_clave

_HORARIO = re.compile(r"(\w+)\s+(\d{1,2}:\d{2})\s+a\s+(\d{1,2}:\d{2})")
_VERSION = re.compile(r"v\.\s*([\d.]+)\s*\(APROBADA EL (\d{2}/\d{2}/\d{4})\)", re.I)


def _portada(texto: str) -> dict:
    # Todo lo que sigue a «Docente(s):», en cualquier grafía, se descarta sin leerlo.
    lineas = [l.strip() for l in re.split(r"(?i)docentes?\s*:", texto)[0].splitlines() if l.strip()]

    def despues(rotulo: str, n: int = 1) -> str:
        for k, linea in enumerate(lineas):
            if linea == rotulo and k + n < len(lineas):
                return lineas[k + n]
        raise SilaboIlegible(f"Falta «{rotulo.rstrip(':')}» en la portada.")

    def en_linea(rotulo: str) -> date:
        for linea in lineas:
            if linea.startswith(rotulo):
                return date.fromisoformat(linea.removeprefix(rotulo).strip())
        raise SilaboIlegible(f"Falta la fecha «{rotulo.rstrip(':')}» del periodo.")

    version = _VERSION.search(despues("Versión:"))
    if version is None:
        raise SilaboIlegible("No se reconoce la versión del proyecto formativo.")
    return {
        "facultad": despues("Facultad:"),
        "carrera": despues("Carrera:"),
        "periodo": {"codigo": despues("Periodo académico:"), "inicio": en_linea("Inicio:"), "fin": en_linea("Fin:")},
        "nombre": despues("Proyecto formativo:"),
        "codigo": despues("Proyecto formativo:", 2),
        "version": version.group(1),
        "aprobado": fecha_dmy(version.group(2)),
    }


def _a_la_derecha(tablas: list[Tabla], rotulo: str) -> str:
    """Celda no vacía a la derecha de la que empieza con el rótulo."""
    for fila in filas(tablas):
        for k, celda in enumerate(fila):
            if normalizar_clave(celda).startswith(rotulo):
                return limpio(next((c for c in fila[k + 1:] if c.strip()), ""))
    return ""


def _debajo(tablas: list[Tabla], rotulo: str) -> str | None:
    """Celda de la fila siguiente en la misma columna que el rótulo (None si no está)."""
    for tabla in tablas:
        for i, fila in enumerate(tabla[:-1]):
            for k, celda in enumerate(fila):
                if normalizar_clave(celda).startswith(rotulo):
                    siguiente = tabla[i + 1]
                    return siguiente[k] if k < len(siguiente) and siguiente[k] is not None else ""
    return None


def _requerido(valor: str | None, campo: str) -> str:
    if valor is None:
        raise SilaboIlegible(f"Falta «{campo}» en el sílabo.")
    return valor


def _horario(texto: str) -> list[dict]:
    return [{"dia": normalizar_clave(dia).lower(), "inicio": ini, "fin": fin}
            for dia, ini, fin in _HORARIO.findall(texto or "")]


def _vinetas(texto: str) -> list[str]:
    return [limpio(l.lstrip("•●-")) for l in (texto or "").splitlines() if l.strip().lstrip("•●-").strip()]


def leer_cabecera(portada: str, tablas_ii: list[Tabla], tablas_iii: list[Tabla]) -> dict:
    """Campos de cabecera de SilaboUTI (dicts con los tipos del contrato)."""
    p = _portada(portada)
    nivel = re.search(r"\d+", _requerido(_debajo(tablas_ii, "NIVEL"), "Nivel"))
    meta = next((l for l in (_debajo(tablas_iii, "METACOMPETENCIA") or "").splitlines() if "(X)" in l.upper()), "")
    ras = [{"id": f[0].strip(), "texto": limpio(f[1]), "evidencia": limpio(f[2])}
           for f in filas(tablas_iii) if re.fullmatch(r"RA\d+", f[0].strip()) and len(f) >= 3]
    return {
        "facultad": p["facultad"],
        "carrera": p["carrera"],
        "periodo": p["periodo"],
        "proyecto_formativo": {
            "nombre": p["nombre"], "codigo": p["codigo"], "version": p["version"], "aprobado": p["aprobado"],
            "uoc": _a_la_derecha(tablas_ii, "UNIDAD DE ORGANIZACION CURRICULAR"),
            "nivel": int(nivel.group()) if nivel else 0,
            "modalidad": limpio(_debajo(tablas_ii, "MODALIDAD")),
            "creditos": horas(_debajo(tablas_ii, "CREDITOS")),
            "horas": {
                "total": horas(_debajo(tablas_ii, "HORAS")),
                "contacto": horas(_debajo(tablas_ii, "APRENDIZAJE EN CONTACTO")),
                "autonomo": horas(_debajo(tablas_ii, "APRENDIZAJE AUTONOMO")),
                "practico": horas(_debajo(tablas_ii, "APRENDIZAJE PRACTICO")),
            },
            "horario": _horario(_debajo(tablas_ii, "HORARIO DE APRENDIZAJE EN CONTACTO")),
        },
        "competencia_perfil": limpio(_debajo(tablas_iii, "COMPETENCIA ESPECIFICA DEL PERFIL")),
        "competencia_pf": limpio(_debajo(tablas_iii, "COMPETENCIA ESPECIFICA DEL PROYECTO")),
        "metacompetencia": limpio(re.sub(r"^\s*\(X\)\s*", "", meta, flags=re.I)),
        "resultados_aprendizaje": ras,
        "problema": {
            "descripcion": _a_la_derecha(tablas_iii, "PROBLEMA, NECESIDAD"),
            "reto": _a_la_derecha(tablas_iii, "PREGUNTA O RETO"),
            "producto_final": _a_la_derecha(tablas_iii, "EVIDENCIA DE DESEMPENO CENTRAL"),
        },
        "pis": {
            "nombre": limpio(_debajo(tablas_iii, "PROYECTO INTERDISCIPLINARIO")),
            "aporte": limpio(_debajo(tablas_iii, "APORTE DEL PROYECTO FORMATIVO")),
        },
        "metodologias": _vinetas(_debajo(tablas_iii, "METODOLOGIA ACTIVA")),
    }
