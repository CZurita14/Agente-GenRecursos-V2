"""Esqueleto determinista de un sílabo simulado: estructura, fechas y horas, sin texto.

Todo el azar sale de `random.Random(f"{semilla}:{cupo.codigo}")`, de modo que un cupo
produce siempre el mismo esqueleto y agregar cupos no altera los demás. Los rangos son
los del perfil estructural medido en los sílabos reales.
"""
import random
from dataclasses import dataclass
from datetime import date, timedelta

from app.silabo.modelo import Periodo
from ciencia_datos.sim_plan import Cupo

CODIGO_PERIODO = "SIM-2026"
INICIO_PERIODO = date(2026, 3, 2)
SEMANAS = 16
N_MOMENTOS = 4
SEMANAS_POR_MOMENTO = SEMANAS // N_MOMENTOS
HORAS_TOTALES = (96, 144)


@dataclass(frozen=True)
class SesionBase:
    id: str
    numero: int
    fecha: date
    semana_periodo: int
    horas_docente: float
    horas_practico: float
    horas_autonomo: float


@dataclass(frozen=True)
class MomentoBase:
    numero: int
    fecha_inicio: date
    fecha_fin: date
    sesiones: tuple[SesionBase, ...]


@dataclass(frozen=True)
class Esqueleto:
    codigo: str
    horas_total: int
    periodo: Periodo
    momentos: tuple[MomentoBase, ...]
    n_resultados: int
    n_metodologias: int
    n_filas_rubrica: int
    n_filas_rubrica_pf: int
    contenidos_por_sesion: int


def _sesiones_por_momento(azar: random.Random) -> list[int]:
    """Reparte entre 6 y 11 sesiones en 4 momentos, de 1 a 4 cada uno."""
    total = azar.randint(6, 11)
    reparto = [1] * N_MOMENTOS
    for _ in range(total - N_MOMENTOS):
        reparto[azar.choice([i for i, n in enumerate(reparto) if n < 4])] += 1
    return reparto


def crear_esqueleto(cupo: Cupo, semilla: int = 42) -> Esqueleto:
    azar = random.Random(f"{semilla}:{cupo.codigo}")
    horas_total = azar.choice(HORAS_TOTALES)
    reparto = _sesiones_por_momento(azar)
    n_sesiones = sum(reparto)
    contacto = practico = horas_total // 3
    autonomo = horas_total - contacto - practico
    periodo = Periodo(
        codigo=CODIGO_PERIODO, inicio=INICIO_PERIODO,
        fin=INICIO_PERIODO + timedelta(weeks=SEMANAS, days=-1),
    )
    momentos = []
    for numero, cantidad in enumerate(reparto, 1):
        primera = (numero - 1) * SEMANAS_POR_MOMENTO + 1
        # Cada sesión cae en una semana distinta del bloque de su momento.
        semanas = sorted(azar.sample(range(primera, primera + SEMANAS_POR_MOMENTO), cantidad))
        sesiones = []
        for i, semana in enumerate(semanas, 1):
            fecha = INICIO_PERIODO + timedelta(weeks=semana - 1, days=azar.randint(0, 4))
            sesiones.append(SesionBase(
                id=f"M{numero}-S{i}", numero=i, fecha=fecha, semana_periodo=semana,
                horas_docente=contacto / n_sesiones, horas_practico=practico / n_sesiones,
                horas_autonomo=autonomo / n_sesiones,
            ))
        momentos.append(MomentoBase(
            numero=numero,
            fecha_inicio=INICIO_PERIODO + timedelta(weeks=primera - 1),
            fecha_fin=INICIO_PERIODO + timedelta(weeks=primera - 1 + SEMANAS_POR_MOMENTO, days=-1),
            sesiones=tuple(sesiones),
        ))
    return Esqueleto(
        codigo=cupo.codigo, horas_total=horas_total, periodo=periodo, momentos=tuple(momentos),
        n_resultados=azar.randint(3, 4), n_metodologias=azar.randint(3, 4),
        n_filas_rubrica=azar.randint(3, 6), n_filas_rubrica_pf=azar.randint(4, 5),
        contenidos_por_sesion=azar.randint(1, 3),
    )
