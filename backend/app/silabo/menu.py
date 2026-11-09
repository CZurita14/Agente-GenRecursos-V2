"""Menú de clases por semana y día (spec §8.1) y clases que cambian entre versiones (§2.2).

El estado de cada clase (sin generar, en cola, …) no se calcula aquí: depende de la
base de datos y lo agrega la API (P4).
"""
from datetime import date, timedelta

from app.silabo.contexto import contexto_clase
from app.silabo.modelo import BaseInmutable, SilaboUTI

DIAS = ("lun", "mar", "mie", "jue", "vie", "sab", "dom")


class ClaseMenu(BaseInmutable):
    clase_id: str
    numero_clase: int
    dia: str
    fecha: date
    momento: int
    momento_titulo: str
    contenidos: list[str]
    ra: list[str]
    entregables: list[str]


class SemanaMenu(BaseInmutable):
    numero: int
    inicio: date
    fin: date
    clases: list[ClaseMenu]
    cierra_momentos: list[int]


def construir_menu(silabo: SilaboUTI) -> list[SemanaMenu]:
    """Semanas con clases, en orden; cada clase numerada cronológicamente en la asignatura."""
    sesiones = sorted(((s, m) for m in silabo.momentos for s in m.sesiones), key=lambda par: (par[0].fecha, par[0].id))
    lunes_inicio = silabo.periodo.inicio - timedelta(days=silabo.periodo.inicio.weekday())
    ultima_semana = {m.numero: max(s.semana_periodo for s in m.sesiones) for m in silabo.momentos if m.sesiones}
    semanas: dict[int, list[ClaseMenu]] = {}
    for numero, (s, m) in enumerate(sesiones, 1):
        semanas.setdefault(s.semana_periodo, []).append(ClaseMenu(
            clase_id=s.id, numero_clase=numero, dia=DIAS[s.fecha.weekday()], fecha=s.fecha,
            momento=m.numero, momento_titulo=m.titulo, contenidos=list(s.contenidos),
            ra=list(m.ra), entregables=list(s.entregables)))
    return [SemanaMenu(
        numero=n, inicio=lunes_inicio + timedelta(weeks=n - 1), fin=lunes_inicio + timedelta(weeks=n - 1, days=6),
        clases=clases, cierra_momentos=sorted(k for k, ultima in ultima_semana.items() if ultima == n))
        for n, clases in sorted(semanas.items())]


def clases_cambiadas(anterior: SilaboUTI, nuevo: SilaboUTI) -> set[str]:
    """Ids de clase cuyo contexto cambió (sin contar la versión del sílabo) y los nuevos."""
    if anterior.proyecto_formativo.codigo != nuevo.proyecto_formativo.codigo:
        raise ValueError("los sílabos son de proyectos formativos distintos")
    previas = {s.id for m in anterior.momentos for s in m.sesiones}

    def contexto(silabo: SilaboUTI, clase_id: str) -> dict:
        return contexto_clase(silabo, clase_id).model_dump(exclude={"version_silabo"})

    return {s.id for m in nuevo.momentos for s in m.sesiones
            if s.id not in previas or contexto(anterior, s.id) != contexto(nuevo, s.id)}
