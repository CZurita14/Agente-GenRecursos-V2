"""Pesos sugeridos del plan de evaluación implícito en el sílabo y su auditoría (V3-4).

Cada calificación del RRA se reparte en partes iguales entre sus actividades dentro de cada bloque (parcial o
bloque único); cada bloque suma 100. En presencial la nota final es el promedio de los dos parciales (supuesto
por confirmar con la institución). Las alertas nombran sesiones y calificaciones, nunca texto del sílabo.
"""
import re
import unicodedata
from dataclasses import dataclass, field

from app.evaluacion.clasificador import Actividad
from app.evaluacion.norma import CALIFICACIONES, Bloque, Norma

NOMBRE = {c.codigo: c.nombre for c in CALIFICACIONES}
SOBRECARGA = 4  # Evaluaciones en una misma sesión a partir de las cuales se avisa.


@dataclass(frozen=True)
class ActividadPesada:
    actividad: Actividad
    bloque: int | None
    peso_bloque: float  # % dentro de su bloque
    peso_final: float  # % de la nota final


@dataclass
class Plan:
    norma: Norma | None
    bloques: list[Bloque]
    actividades: list[ActividadPesada]
    por_momento: dict[int, float] = field(default_factory=dict)
    por_bloque: dict[int, float] = field(default_factory=dict)
    alertas: list[str] = field(default_factory=list)


def _momento(sesion: str) -> int:
    return int(sesion.split("-")[0][1:])


def _plano(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").upper()


def _repartir(total: float, n: int) -> list[float]:
    """`total` en `n` partes con 2 decimales que suman exactamente `total`."""
    base = [round(total / n, 2)] * n
    base[-1] = round(total - sum(base[:-1]), 2)
    return base


def calcular(actividades: list[Actividad], norma: Norma | None, bloques: list[Bloque],
             textos: dict[str, str] | None = None) -> Plan:
    textos = textos or {}
    plan = Plan(norma, bloques, [])
    if norma is None:
        plan.alertas.append("La modalidad del sílabo no se reconoce: no se sugieren pesos.")
    elif norma.estado != "definida":
        plan.alertas.append(f"La norma de la modalidad {norma.modalidad} está pendiente de definición: "
                            "no se sugieren pesos.")
    evaluables = [a for a in actividades if a.evaluable]
    bloque_de = {s: b.numero for b in bloques for s in b.sesiones}
    pesos: dict[int, float] = {}
    if norma is not None and norma.estado == "definida" and bloques:
        for b in bloques:
            for codigo, peso in norma.pesos.items():
                indices = [k for k, a in enumerate(evaluables)
                           if a.calificacion == codigo and bloque_de.get(a.sesion) == b.numero]
                if not indices:
                    plan.alertas.append(f"{b.nombre}: falta una actividad de «{NOMBRE[codigo]}» ({peso:g} %).")
                    continue
                for k, parte in zip(indices, _repartir(peso, len(indices))):
                    pesos[k] = parte
            plan.por_bloque[b.numero] = round(sum(p for k, p in pesos.items()
                                                  if bloque_de.get(evaluables[k].sesion) == b.numero), 2)
        if not any(a.tipo == "diagnostica" for a in evaluables):
            plan.alertas.append("No hay evaluación diagnóstica al inicio del proyecto formativo.")
    fraccion = 1 / len(bloques) if bloques else 0
    for k, a in enumerate(evaluables):
        peso = pesos.get(k, 0.0)
        plan.actividades.append(ActividadPesada(a, bloque_de.get(a.sesion), peso, round(peso * fraccion, 2)))
    for p in plan.actividades:
        m = _momento(p.actividad.sesion)
        plan.por_momento[m] = round(plan.por_momento.get(m, 0) + p.peso_final, 2)
    _alertas_de_forma(plan, evaluables, textos)
    return plan


def _alertas_de_forma(plan: Plan, evaluables: list[Actividad], textos: dict[str, str]) -> None:
    sin_numero = [a.sesion for a in evaluables if a.tipo == "practica_experimental"
                  and re.search(r"PRACTICA DE APRENDIZAJE EXPERIMENTAL(?!\s*\d)", _plano(textos.get(f"{a.sesion}/{a.columna}", "")))]
    if sin_numero:
        plan.alertas.append(f"Prácticas experimentales sin numerar: {', '.join(sin_numero)}.")
    por_sesion: dict[str, int] = {}
    for a in evaluables:
        if a.tipo != "diagnostica":
            por_sesion[a.sesion] = por_sesion.get(a.sesion, 0) + 1
    for sesion, n in por_sesion.items():
        if n >= SOBRECARGA:
            plan.alertas.append(f"{sesion} concentra {n} evaluaciones en una sola sesión.")
