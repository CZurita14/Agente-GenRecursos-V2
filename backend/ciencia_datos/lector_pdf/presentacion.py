"""Portada, sección II (presentación) y sección III (mapa de formación).

Los campos se localizan por su rótulo normalizado, nunca por posición fija.
La portada se lee solo hasta «Docente:»: el nombre del docente no se toca.
"""
import re
from datetime import date

from ciencia_datos.lector_pdf.errores import SilaboIlegible
from ciencia_datos.lector_pdf.texto import Tabla, filas, fecha_dmy, horas, limpio, normalizar_clave

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


def _fila_sin_rotulo_antes(tablas: list[Tabla], rotulo: str) -> str:
    """Texto de la fila sin rótulo que precede a la fila del rótulo dado. Pasa cuando una tabla
    empieza en página nueva y la fila anterior perdió su rótulo (p. ej. «Problema, necesidad…»)."""
    for tabla in tablas:
        for i, fila in enumerate(tabla):
            if i and normalizar_clave(fila[0] if fila else "").startswith(rotulo):
                previa = [c or "" for c in tabla[i - 1]]
                if previa and not previa[0].strip():
                    return limpio(" ".join(c for c in previa[1:] if c.strip()))
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


def _resultados(tablas_iii: list[Tabla]) -> list[dict]:
    """Filas «RAn»; una fila sin id justo después, en una tabla de RA, continúa el RA anterior
    (la tabla se partió entre páginas)."""
    ras: list[dict] = []
    for tabla in tablas_iii:
        de_ra = any(normalizar_clave(c).startswith("RESULTADOS DE APRENDIZAJE Y EVIDENCIAS") for c in (tabla[0] if tabla else []) if c)
        for f in ([c or "" for c in fila] for fila in tabla):
            if len(f) < 3:
                continue
            if re.fullmatch(r"RA\d+", f[0].strip()):
                ras.append({"id": f[0].strip(), "texto": limpio(f[1]), "evidencia": limpio(f[2])})
            elif de_ra and ras and not f[0].strip() and (f[1].strip() or f[2].strip()):
                ras[-1]["texto"] = limpio(f"{ras[-1]['texto']} {f[1]}")
                ras[-1]["evidencia"] = limpio(f"{ras[-1]['evidencia']} {f[2]}")
    return ras


def leer_cabecera(portada: str, tablas_ii: list[Tabla], tablas_iii: list[Tabla]) -> dict:
    """Campos de cabecera de SilaboUTI (dicts con los tipos del contrato)."""
    p = _portada(portada)
    nivel = re.search(r"\d+", _requerido(_debajo(tablas_ii, "NIVEL"), "Nivel"))
    meta = next((l for l in (_debajo(tablas_iii, "METACOMPETENCIA") or "").splitlines() if "(X)" in l.upper()), "")
    ras = _resultados(tablas_iii)
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
            "descripcion": (_a_la_derecha(tablas_iii, "PROBLEMA, NECESIDAD")
                            or _fila_sin_rotulo_antes(tablas_iii, "PREGUNTA O RETO")),
            "reto": _a_la_derecha(tablas_iii, "PREGUNTA O RETO"),
            "producto_final": _a_la_derecha(tablas_iii, "EVIDENCIA DE DESEMPENO CENTRAL"),
        },
        "pis": {
            "nombre": limpio(_debajo(tablas_iii, "PROYECTO INTERDISCIPLINARIO")),
            "aporte": limpio(_debajo(tablas_iii, "APORTE DEL PROYECTO FORMATIVO")),
        },
        "metodologias": _vinetas(_debajo(tablas_iii, "METODOLOGIA ACTIVA")),
    }
