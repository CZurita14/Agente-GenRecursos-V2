"""Plan de simulación: cuántos sílabos simulados por facultad y carrera, y en qué orden.

Solo cuentan las carreras de grado. Una facultad sin carreras no genera cupos. Los
códigos dependen únicamente de la sigla, la carrera y su índice, de modo que agregar
una carrera al catálogo no cambia los códigos de las demás.
"""
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.agentes.facultades import normalizar
from ciencia_datos.origen import PREFIJO_SIMULADO

RAIZ = Path(__file__).resolve().parents[2]
POR_CARRERA = 6
MINIMO_POR_FACULTAD = 24


@dataclass(frozen=True)
class Cupo:
    sigla: str
    facultad: str
    carrera: str
    indice: int

    @property
    def codigo(self) -> str:
        slug = normalizar(self.carrera).replace(" ", "-")
        return f"{PREFIJO_SIMULADO}{self.sigla}-{slug}-{self.indice:03d}"


def cuota(n_carreras: int) -> int:
    """Sílabos simulados de una facultad con `n_carreras` carreras de grado."""
    return max(POR_CARRERA * n_carreras, MINIMO_POR_FACULTAD)


def _cupos_de_facultad(sigla: str, facultad: str, carreras: list[str]) -> list[Cupo]:
    """Rota entre las carreras; el índice de cada una empieza en 1."""
    siguiente = dict.fromkeys(carreras, 1)
    lista = []
    for i in range(cuota(len(carreras))):
        carrera = carreras[i % len(carreras)]
        lista.append(Cupo(sigla, facultad, carrera, siguiente[carrera]))
        siguiente[carrera] += 1
    return lista


def cupos(ruta_catalogo: Path) -> list[Cupo]:
    """Todos los cupos, en rotación: una carrera de cada facultad por turno."""
    datos = yaml.safe_load(ruta_catalogo.read_text(encoding="utf-8"))
    por_facultad = []
    for f in datos["facultades"]:
        carreras = [c["nombre"] for c in f.get("carreras") or [] if c.get("nivel") == "grado"]
        if carreras:
            por_facultad.append(_cupos_de_facultad(f["sigla"], f["nombre"], carreras))
    orden = []
    for turno in range(max((len(p) for p in por_facultad), default=0)):
        orden.extend(p[turno] for p in por_facultad if turno < len(p))
    return orden
