"""Sección IV: momentos, tabla de sesiones y rúbricas (docs/mapeo-silabo.md §2.1, §6).

Las tablas de un momento se cortan entre páginas, así que la sección se lee como
un único flujo de filas con una máquina de estados. Una fila sin «Sesión N»
continúa la sesión anterior (fila partida entre páginas).
"""
import re
from datetime import date

from app.silabo.lector.errores import SilaboIlegible
from app.silabo.lector.texto import Tabla, entregables_en, fecha_dmy, horas, limpio, normalizar_clave, semana_periodo

NIVELES = {"RECEPTIVO": "receptivo", "RESOLUTIVO": "resolutivo", "REFLEXIVO": "reflexivo",
           "CRITICO": "critico", "COCREATIVO": "cocreativo"}
_MOMENTO = re.compile(r"MOMENTO (\d+)$")
_SESION = re.compile(r"Sesi[oó]n\s+(\d+)\s+(\d{2}/\d{2}/\d{4})")
_ASINCRONICA = re.compile(r"Otras actividades con el\s+docente\s*\((\d+(?:[.,]\d+)?)\s*h\)\s*:?", re.I)
# CONTENIDO va antes que SESION: «Contenido de la sesión» es la columna de contenidos.
_ROLES = (("CONTENIDO", "contenidos"), ("SESION", "sesion"), ("DOCENTE", "docente"),
          ("PRACTICO", "practico"), ("AUTONOMO", "autonomo"))
_ROLES_REQUERIDOS = {"sesion", "docente", "practico", "autonomo", "contenidos"}


def _celdas(fila: list[str | None]) -> list[str]:
    return [c or "" for c in fila]


def _valor(fila: list[str]) -> str:
    """Primer texto a la derecha del rótulo de la fila."""
    return limpio(next((c for c in fila[1:] if c.strip()), ""))


def _columnas(encabezado: list[str]) -> dict[str, int]:
    """Índice de cada rol; «Horas…» toma el nombre de la actividad a su izquierda.

    Cada rol se asigna una sola vez; si falta alguno, la tabla no se reconoce.
    """
    columnas: dict[str, int] = {}
    ultimo = None
    for k, celda in enumerate(encabezado):
        clave = normalizar_clave(celda)
        if clave.startswith("HORA"):
            if ultimo:
                columnas.setdefault(f"horas_{ultimo}", k)
            continue
        rol = next((r for palabra, r in _ROLES if palabra in clave), None)
        if rol and rol not in columnas:
            columnas[rol] = k
            ultimo = rol
    if not _ROLES_REQUERIDOS <= columnas.keys():
        raise SilaboIlegible("No se reconocen las columnas de la tabla de sesiones.")
    return columnas


def _contenidos(texto: str) -> list[str]:
    """Una entrada por viñeta; las líneas sin viñeta continúan la anterior."""
    items: list[list[str]] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea[0] in "•●-" or not items:
            items.append([linea.lstrip("•●-").strip()])
        else:
            items[-1].append(linea)
    return [limpio(" ".join(i)) for i in items if " ".join(i).strip()]


def _sesion(numero_momento: int, crudo: dict, inicio_periodo: date) -> dict:
    docente = crudo["docente"]
    asincronica = None
    m = _ASINCRONICA.search(docente)
    if m:
        asincronica = {"texto": limpio(docente[m.end():]), "horas": horas(m.group(1))}
        docente = docente[:m.start()]
    textos = {r: crudo[r] for r in ("practico", "autonomo")}
    return {
        "id": f"M{numero_momento}-S{crudo['numero']}",
        "numero": crudo["numero"],
        "fecha": crudo["fecha"],
        "semana_periodo": semana_periodo(crudo["fecha"], inicio_periodo),
        "docente": {"texto": limpio(docente), "horas": horas(crudo["horas_docente"]), "asincronica": asincronica},
        "practico": {"texto": limpio(textos["practico"]), "horas": horas(crudo["horas_practico"])},
        "autonomo": {"texto": limpio(textos["autonomo"]), "horas": horas(crudo["horas_autonomo"])},
        "contenidos": _contenidos(crudo["contenidos"]),
        "entregables": entregables_en(crudo["docente"], textos["practico"], textos["autonomo"]),
    }


def leer_rubrica(filas: list[list[str | None]]) -> list[dict]:
    """Filas desde el encabezado «Indicador | Receptivo | …»; una fila sin indicador continúa la anterior."""
    rubrica: list[dict] = []
    niveles: dict[str, int] = {}
    ancho = 0
    for fila in map(_celdas, filas):
        if normalizar_clave(fila[0]) == "INDICADOR":
            niveles = {NIVELES[normalizar_clave(c)]: k for k, c in enumerate(fila) if normalizar_clave(c) in NIVELES}
            ancho = len(fila)
            continue
        if not niveles:
            continue
        valores = {nivel: fila[k] if k < len(fila) else "" for nivel, k in niveles.items()}
        if len(fila) != ancho or not any(v.strip() for v in valores.values()):
            # Otra tabla (otra forma o sin niveles): la rúbrica terminó.
            niveles = {}
            continue
        indicador = fila[0].strip()
        # Los indicadores empiezan con mayúscula o número; en minúscula, continúan
        # la fila anterior partida entre páginas.
        if indicador and not (indicador[0].islower() and rubrica):
            rubrica.append({"indicador": limpio(indicador), "niveles": {n: limpio(v) for n, v in valores.items()}})
        elif rubrica and (indicador or any(v.strip() for v in valores.values())):
            previa = rubrica[-1]
            if indicador:
                previa["indicador"] = limpio(f"{previa['indicador']} {indicador}")
            for n, v in valores.items():
                previa["niveles"][n] = limpio(f"{previa['niveles'][n]} {v}")
    return rubrica


def leer_momentos(tablas_iv: list[Tabla], inicio_periodo: date) -> list[dict]:
    """Momentos de la sección IV, en orden, con las claves del contrato `Momento`."""
    momentos: list[dict] = []
    estado = "fuera"
    columnas: dict[str, int] = {}
    crudas: list[dict] = []
    filas_rubrica: list[list[str | None]] = []
    abierto: str | None = None  # Campo de texto que una fila partida podría continuar.

    def cerrar():
        if momentos:
            momentos[-1]["sesiones"] = [_sesion(momentos[-1]["numero"], c, inicio_periodo) for c in crudas]
            momentos[-1]["rubrica"] = leer_rubrica(filas_rubrica)

    for tabla in tablas_iv:
        for original in tabla:
            fila = _celdas(original)
            clave = normalizar_clave(fila[0])
            nuevo = _MOMENTO.match(clave)
            if nuevo:
                cerrar()
                crudas, filas_rubrica, estado = [], [], "cabecera"
                titulo = re.sub(r"^Momento \d+:\s*", "", _valor(fila), flags=re.I)
                momentos.append({"numero": int(nuevo.group(1)), "titulo": titulo, "fecha_inicio": None,
                                 "fecha_fin": None, "ra": [], "evidencia": "", "recursos": "", "politica_ia": ""})
                continue
            if not momentos:
                continue
            actual = momentos[-1]
            if estado == "rubrica":
                filas_rubrica.append(original)
                continue
            if not clave and abierto and estado in ("cabecera", "despues") and _valor(fila):
                # Fila partida entre páginas: continúa el último campo de texto leído.
                actual[abierto] = limpio(f"{actual[abierto]} {_valor(fila)}")
                continue
            abierto = None
            if clave.startswith("SESION -"):
                columnas, estado = _columnas(fila), "sesiones"
            elif clave.startswith("TOTAL"):
                estado = "despues"
            elif clave.startswith("RECURSOS PARA EL APRENDIZAJE"):
                actual["recursos"], abierto = _valor(fila), "recursos"
            elif clave.startswith("POLITICA DE GOBERNANZA"):
                actual["politica_ia"], abierto = _valor(fila), "politica_ia"
            elif clave.startswith("RUBRICA DE EVALUACION"):
                estado = "rubrica"
            elif estado == "cabecera" and clave.startswith("FECHA"):
                inicio, _, fin = _valor(fila).partition(" al ")
                actual["fecha_inicio"], actual["fecha_fin"] = fecha_dmy(inicio), fecha_dmy(fin)
            elif estado == "cabecera" and clave.startswith("RESULTADOS DE APRENDIZAJE"):
                actual["ra"] = re.findall(r"RA\d+", _valor(fila))
            elif estado == "cabecera" and clave.startswith("EVIDENCIA DE DESEMPENO"):
                actual["evidencia"], abierto = _valor(fila), "evidencia"
            elif estado == "sesiones":
                def celda(rol: str) -> str:
                    k = columnas.get(rol)
                    return fila[k] if k is not None and k < len(fila) else ""
                inicio_sesion = _SESION.match(fila[0].strip())
                if inicio_sesion:
                    crudas.append({"numero": int(inicio_sesion.group(1)), "fecha": fecha_dmy(inicio_sesion.group(2)),
                                   **{r: celda(r) for r in ("docente", "practico", "autonomo", "contenidos")},
                                   **{f"horas_{r}": celda(f"horas_{r}") for r in ("docente", "practico", "autonomo")}})
                elif clave.startswith("SESION"):
                    raise SilaboIlegible("Una sesión de la tabla no tiene una fecha legible.")
                elif not fila[0].strip() and crudas:
                    previa = crudas[-1]
                    for r in ("docente", "practico", "autonomo", "contenidos"):
                        if celda(r).strip():
                            previa[r] = f"{previa[r]}\n{celda(r)}" if previa[r].strip() else celda(r)
                    for r in ("docente", "practico", "autonomo"):
                        if celda(f"horas_{r}").strip() and not previa[f"horas_{r}"].strip():
                            previa[f"horas_{r}"] = celda(f"horas_{r}")
    cerrar()
    return momentos
