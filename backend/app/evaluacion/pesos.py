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
    # Cómo corregir cada alerta (V4-3): qué agregar y dónde, con un rótulo del prompt institucional. Nombra sesiones
    # y columnas; los textos entre corchetes los completa el docente (nunca se copia texto del sílabo).
    sugerencias: dict[str, str] = field(default_factory=dict)

    def alertar(self, texto: str, sugerencia: str | None = None) -> None:
        self.alertas.append(texto)
        if sugerencia:
            self.sugerencias[texto] = sugerencia


def _momento(sesion: str) -> int:
    return int(sesion.split("-")[0][1:])


def _plano(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").upper()


def _repartir(total: float, n: int) -> list[float]:
    """`total` en `n` partes con 2 decimales que suman exactamente `total`."""
    base = [round(total / n, 2)] * n
    base[-1] = round(total - sum(base[:-1]), 2)
    return base


def clave(a: Actividad) -> str:
    """Identifica una actividad evaluable del plan: «M2-S3/practico/practica_experimental»."""
    return f"{a.sesion}/{a.columna}/{a.tipo}"


def calcular(actividades: list[Actividad], norma: Norma | None, bloques: list[Bloque],
             textos: dict[str, str] | None = None, ajustes: dict[str, float] | None = None) -> Plan:
    """`ajustes` (V4-4): % de cada actividad dentro de su bloque, confirmados por el docente y ya validados con
    `validar_ajustes`. Una calificación usa los ajustes solo si están todas sus actividades; si no, el reparto igual."""
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
                    plan.alertar(f"{b.nombre}: falta una actividad de «{NOMBRE[codigo]}» ({peso:g} %).",
                                 _sugerencia_faltante(b, codigo, evaluables, textos))
                    continue
                partes = ([ajustes[clave(evaluables[k])] for k in indices]
                          if ajustes and all(clave(evaluables[k]) in ajustes for k in indices)
                          else _repartir(peso, len(indices)))
                for k, parte in zip(indices, partes):
                    pesos[k] = parte
            plan.por_bloque[b.numero] = round(sum(p for k, p in pesos.items()
                                                  if bloque_de.get(evaluables[k].sesion) == b.numero), 2)
        if not any(a.tipo == "diagnostica" for a in evaluables):
            plan.alertar("No hay evaluación diagnóstica al inicio del proyecto formativo.",
                         "Agrega en Momento 1, sesión 1 (con el docente) una actividad con el rótulo «Aplicación de la "
                         "evaluación diagnóstica sobre [conocimientos previos que el proyecto necesita]». Vale 0 %.")
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
        practicas = [a.sesion for a in evaluables if a.tipo == "practica_experimental"]
        numeros = {sesion: k for k, sesion in enumerate(dict.fromkeys(practicas), 1)}
        plan.alertar(f"Prácticas experimentales sin numerar: {', '.join(sin_numero)}.",
                     "Numera las prácticas en orden en todo el periodo, no por momento: "
                     + "; ".join(f"{_legible(s)} → «Práctica de aprendizaje experimental {numeros[s]}: …»" for s in sin_numero)
                     + ".")
    por_sesion: dict[str, int] = {}
    for a in evaluables:
        if a.tipo != "diagnostica":
            por_sesion[a.sesion] = por_sesion.get(a.sesion, 0) + 1
    for sesion, n in por_sesion.items():
        if n >= SOBRECARGA:
            vecinas = [v for v in _vecinas(sesion, textos) if por_sesion.get(v, 0) < SOBRECARGA - 1]
            destino = f" a {' o '.join(_legible(v) for v in vecinas[:2])}" if vecinas else " a una sesión vecina"
            plan.alertar(f"{sesion} concentra {n} evaluaciones en una sola sesión.",
                         f"Mueve una o dos de esas evaluaciones{destino}, o deja alguna como actividad de avance "
                         "(sin calificar).")


# --- Sugerencias de corrección (V4-3) ---------------------------------------------------------

# Columna donde va cada calificación y un rótulo del prompt institucional (§2.2) con lo que el docente completa.
_DONDE = {
    "C1_contacto": (("asincronica", "docente"), "Foro virtual sobre [tema del momento]: cada estudiante analiza [caso o "
                    "decisión del proyecto] y comenta con fundamentos el aporte de 2 compañeros"),
    "C3_formativa": (("docente",), "Aplicación de un cuestionario en plataforma sobre [contenidos de la sesión]"),
    "C5_sumativa": (("docente", "asincronica"), "Prueba acumulativa del {parcial} sobre [contenidos del bloque]"),
    "C2_practicas": (("practico",), "Práctica de aprendizaje experimental {n}: [actividad] con registro de resultados"),
    "C1_autonoma": (("autonomo",), "Ensayo de [N] palabras sobre [tema], con [criterios de la rúbrica] y declaración "
                    "del uso de IA"),
    "C4_proyecto": (("autonomo", "practico"), "Entrega de la versión [n] del [producto del momento] con [lo que se "
                    "verifica]"),
}
_COLUMNA = {"docente": "con el docente", "asincronica": "otras actividades con el docente",
            "practico": "práctico-experimental", "autonomo": "trabajo autónomo"}


def _legible(sesion: str) -> str:
    m = re.fullmatch(r"M(\d+)-S(\d+)", sesion)
    return f"Momento {m.group(1)}, sesión {m.group(2)}" if m else sesion


def _orden(sesion: str) -> tuple[int, int]:
    m = re.fullmatch(r"M(\d+)-S(\d+)", sesion)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _vecinas(sesion: str, textos: dict[str, str]) -> list[str]:
    """Sesiones del mismo momento, de la más cercana a la más lejana."""
    todas = sorted({k.split("/")[0] for k in textos}, key=_orden)
    momento, numero = _orden(sesion)
    return sorted([s for s in todas if _orden(s)[0] == momento and s != sesion],
                  key=lambda s: abs(_orden(s)[1] - numero))


def _sugerencia_faltante(b: Bloque, codigo: str, evaluables: list[Actividad], textos: dict[str, str]) -> str | None:
    """Dónde agregar la actividad que falta en el bloque: la sesión con menos evaluaciones que tiene esa columna."""
    if codigo not in _DONDE:
        return None
    columnas, rotulo = _DONDE[codigo]
    cuenta = {s: sum(a.sesion == s for a in evaluables) for s in b.sesiones}
    candidatas = [(s, c) for s in b.sesiones for c in columnas if textos.get(f"{s}/{c}", "").strip()]
    if not candidatas:
        return f"Agrega una actividad de «{NOMBRE[codigo]}» en {b.nombre} con un rótulo como «{rotulo}»."
    if codigo == "C5_sumativa":
        sesion, columna = max(candidatas, key=lambda x: _orden(x[0]))  # Al cierre del bloque.
    else:
        sesion, columna = min(candidatas, key=lambda x: (cuenta.get(x[0], 0), columnas.index(x[1]), _orden(x[0])))
    practicas = sum(a.tipo == "practica_experimental" for a in evaluables if _orden(a.sesion) < _orden(sesion))
    parcial = ({1: "primer parcial", 2: "segundo parcial"}.get(b.numero, "periodo")
               if b.nombre.lower().startswith("parcial") else "periodo")
    texto = rotulo.format(n=practicas + 1, parcial=parcial)
    return (f"Agrega en {_legible(sesion)} ({_COLUMNA[columna]}) una actividad evaluable con un rótulo como «{texto}». "
            f"Así {b.nombre} completa «{NOMBRE[codigo]}».")


# --- Ajuste del docente (V4-4) -----------------------------------------------------------------

TOLERANCIA = 0.005  # Los pesos van con 2 decimales.


def grupos(actividades: list[Actividad], norma: Norma, bloques: list[Bloque]) -> list[dict]:
    """Cada calificación de cada bloque con sus actividades: lo que el docente puede repartir.

    [{bloque, calificacion, peso (de la norma), claves: [...]}]; solo las calificaciones con actividades.
    """
    evaluables = [a for a in actividades if a.evaluable]
    bloque_de = {s: b.numero for b in bloques for s in b.sesiones}
    salida = []
    for b in bloques:
        for codigo, peso in norma.pesos.items():
            claves = [clave(a) for a in evaluables if a.calificacion == codigo and bloque_de.get(a.sesion) == b.numero]
            if claves:
                salida.append({"bloque": b.numero, "calificacion": codigo, "peso": peso, "claves": claves})
    return salida


def validar_ajustes(actividades: list[Actividad], norma: Norma | None, bloques: list[Bloque],
                    ajustes: dict[str, float]) -> list[str]:
    """Errores del reparto del docente: cada calificación de cada bloque suma exactamente el % de la norma."""
    if norma is None or norma.estado != "definida" or not bloques:
        return ["La norma de esta modalidad no está definida: no hay pesos que ajustar."]
    errores = []
    gs = grupos(actividades, norma, bloques)
    conocidas = {c for g in gs for c in g["claves"]}
    if extra := sorted(set(ajustes) - conocidas):
        errores.append(f"Actividades que no están en el plan: {', '.join(extra)}.")
    if falta := sorted(conocidas - set(ajustes)):
        errores.append(f"Faltan los pesos de: {', '.join(falta)}.")
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 or v > 100 for v in ajustes.values()):
        errores.append("Cada peso es un número entre 0 y 100.")
        return errores
    nombre_bloque = {b.numero: b.nombre for b in bloques}
    for g in gs:
        suma = round(sum(ajustes.get(c, 0) for c in g["claves"]), 2)
        if abs(suma - g["peso"]) > TOLERANCIA:
            errores.append(f"{nombre_bloque[g['bloque']]}: «{NOMBRE[g['calificacion']]}» suma {suma:g} % y la norma "
                           f"pide {g['peso']:g} %.")
    return errores
