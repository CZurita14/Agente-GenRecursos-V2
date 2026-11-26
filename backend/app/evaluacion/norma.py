"""Norma de evaluación del RRA por modalidad y bloques de calificación (parciales) por fecha.

La tabla vive en `norma_rra.json` para poder ajustarla sin tocar el código; se valida al cargarla
(cada modalidad definida suma 100 y solo usa las seis calificaciones del RRA). Los parciales se
asignan por fecha y no por momento: el primer parcial cierra en la sesión de su prueba acumulativa
o, si no se reconoce, a la mitad del periodo de sesiones.
"""
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.silabo.modelo import SilaboUTI

TABLA = Path(__file__).with_name("norma_rra.json")


@dataclass(frozen=True)
class Calificacion:
    codigo: str
    nombre: str
    componente: str  # contacto | practico | autonomo


CALIFICACIONES = (
    Calificacion("C1_contacto", "Actividades en contacto con el docente", "contacto"),
    Calificacion("C3_formativa", "Evaluaciones cognitivas de proceso (formativas)", "contacto"),
    Calificacion("C5_sumativa", "Evaluación de resultados de aprendizaje (sumativa)", "contacto"),
    Calificacion("C2_practicas", "Actividades prácticas", "practico"),
    Calificacion("C1_autonoma", "Actividades autónomas", "autonomo"),
    Calificacion("C4_proyecto", "Proyecto integrador", "autonomo"),
)
_CODIGOS = {c.codigo: c for c in CALIFICACIONES}


class NormaInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Norma:
    modalidad: str
    estado: str  # definida | pendiente
    bloques: str | None  # parciales | unico | None (pendiente)
    pesos: dict[str, float]
    c5: str | None
    c4: str | None

    @property
    def componentes(self) -> dict[str, float]:
        suma = {"contacto": 0, "practico": 0, "autonomo": 0}
        for codigo, peso in self.pesos.items():
            suma[_CODIGOS[codigo].componente] += peso
        return suma


@dataclass(frozen=True)
class Bloque:
    numero: int
    nombre: str
    inicio: date
    fin: date
    sesiones: list[str]


def _plano(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()


def cargar_tabla(ruta: Path = TABLA) -> tuple[dict[str, Norma], dict[str, str]]:
    """Normas por modalidad y alias de los textos del sílabo; `NormaInvalida` si algo no cuadra."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    crudas: dict = datos["modalidades"]
    normas: dict[str, Norma] = {}
    for modalidad, cruda in crudas.items():
        if "igual_que" in cruda:
            cruda = crudas[cruda["igual_que"]]
        pesos = {k: float(v) for k, v in cruda["pesos"].items()}
        desconocidas = sorted(set(pesos) - set(_CODIGOS))
        if desconocidas:
            raise NormaInvalida(f"{modalidad}: calificaciones desconocidas {', '.join(desconocidas)}")
        if cruda["estado"] == "definida":
            if set(pesos) != set(_CODIGOS) or abs(sum(pesos.values()) - 100) > 1e-9:
                raise NormaInvalida(f"{modalidad}: las seis calificaciones deben sumar 100")
            if cruda["bloques"] not in ("parciales", "unico"):
                raise NormaInvalida(f"{modalidad}: bloques debe ser «parciales» o «unico»")
        elif cruda["estado"] != "pendiente":
            raise NormaInvalida(f"{modalidad}: estado desconocido")
        normas[modalidad] = Norma(modalidad, cruda["estado"], cruda["bloques"], pesos, cruda["c5"], cruda["c4"])
    alias = {_plano(k): v for k, v in datos["alias"].items()}
    faltan = sorted(set(alias.values()) - set(normas))
    if faltan:
        raise NormaInvalida(f"alias hacia modalidades inexistentes: {', '.join(faltan)}")
    return normas, alias


@lru_cache(maxsize=1)
def _tabla() -> tuple[dict[str, Norma], dict[str, str]]:
    return cargar_tabla()


def norma_de(modalidad: str | None) -> Norma | None:
    """Norma de la modalidad del sílabo; None si no se reconoce (no se inventan pesos)."""
    if not modalidad or not modalidad.strip():
        return None
    normas, alias = _tabla()
    clave = alias.get(_plano(modalidad))
    return normas.get(clave) if clave else None


# Sesión que cierra el primer parcial: su prueba acumulativa o parcial.
_CIERRE_P1 = re.compile(r"PRIMER PARCIAL|PARCIAL 1\b|PRIMERA PRUEBA (?:ACUMULATIVA|PARCIAL)|PRIMER HEMICICLO")


def _textos(sesion) -> str:
    partes = [sesion.docente.texto, sesion.practico.texto, sesion.autonomo.texto]
    if sesion.docente.asincronica:
        partes.append(sesion.docente.asincronica.texto)
    return _plano(" ".join(partes))


def bloques(silabo: SilaboUTI, norma: Norma | None, sumativas: list[str] | None = None) -> list[Bloque]:
    """Bloques de calificación con sus sesiones en orden de fecha; vacío si la norma está pendiente.

    El primer parcial cierra en la sesión que nombra su prueba («primer parcial», «primer hemiciclo»); si no hay,
    en la primera sesión con una prueba sumativa (`sumativas`, del clasificador) que no sea la última; si tampoco,
    a la mitad del periodo.
    """
    if norma is None or norma.bloques is None:
        return []
    sesiones = sorted((s for m in silabo.momentos for s in m.sesiones), key=lambda s: (s.fecha, s.id))
    if not sesiones:
        return []

    def bloque(numero, nombre, grupo):
        return Bloque(numero, nombre, grupo[0].fecha, grupo[-1].fecha, [s.id for s in grupo])

    if norma.bloques == "unico" or len(sesiones) == 1:
        return [bloque(1, "Bloque único", sesiones)]
    cierre = next((k for k, s in enumerate(sesiones) if _CIERRE_P1.search(_textos(s))), None)
    if cierre is None or cierre == len(sesiones) - 1:
        cierre = next((k for k, s in enumerate(sesiones[:-1]) if s.id in set(sumativas or ())), None)
    if cierre is None:
        mitad = sesiones[0].fecha + (sesiones[-1].fecha - sesiones[0].fecha) / 2
        cierre = max(k for k, s in enumerate(sesiones) if s.fecha <= mitad)
        cierre = min(cierre, len(sesiones) - 2)
    return [bloque(1, "Parcial 1", sesiones[:cierre + 1]), bloque(2, "Parcial 2", sesiones[cierre + 1:])]
