"""Separación 70/30 por sílabo (código de proyecto formativo), nunca por fragmento.

El orden dentro de cada facultad sale de un hash SHA-256 de `semilla:codigo`, por lo
que no depende del orden de entrada y es estable entre ejecuciones.
"""
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field

from ciencia_datos.origen import es_simulado

MIN_POR_FACULTAD = 4
MIN_FACULTADES = 5


@dataclass(frozen=True)
class Separacion:
    entrenamiento: list[str]
    prueba: list[str]
    avisos: list[str] = field(default_factory=list)
    control: list[str] = field(default_factory=list)  # reales: solo comparan, nunca entrenan


def _por_facultad(codigo_a_facultad: dict[str, str]) -> dict[str, list[str]]:
    grupos: dict[str, list[str]] = defaultdict(list)
    for codigo, facultad in codigo_a_facultad.items():
        grupos[facultad].append(codigo)
    return grupos


def separar(
    codigo_a_facultad: dict[str, str], proporcion: float = 0.7, semilla: int = 42
) -> Separacion:
    """Estratifica por facultad: prueba = round(n × (1 - proporción)), mínimo 1 si n ≥ 2."""
    entrenamiento: list[str] = []
    prueba: list[str] = []
    avisos: list[str] = []
    for facultad, codigos in sorted(_por_facultad(codigo_a_facultad).items()):
        ordenados = sorted(
            codigos,
            key=lambda c: hashlib.sha256(f"{semilla}:{c}".encode()).hexdigest(),
        )
        n = len(ordenados)
        if n < 2:
            avisos.append(f"{facultad}: un solo sílabo, va a entrenamiento")
            entrenamiento += ordenados
            continue
        n_prueba = min(max(1, round(n * (1 - proporcion))), n - 1)
        prueba += ordenados[:n_prueba]
        entrenamiento += ordenados[n_prueba:]
    return Separacion(sorted(entrenamiento), sorted(prueba), avisos)


def separar_preliminar(codigo_a_facultad: dict[str, str], proporcion: float = 0.7, semilla: int = 42) -> Separacion:
    """Los simulados van 70/30 por facultad; los reales, a `control`, sin entrenar ni probar."""
    simulados = {c: f for c, f in codigo_a_facultad.items() if es_simulado(c)}
    s = separar(simulados, proporcion, semilla)
    control = sorted(c for c in codigo_a_facultad if not es_simulado(c))
    return Separacion(s.entrenamiento, s.prueba, s.avisos, control)


def dejar_fuera(codigo_a_facultad: dict[str, str]) -> dict[str, Separacion]:
    """Por cada facultad, toda ella a prueba y el resto a entrenamiento."""
    grupos = _por_facultad(codigo_a_facultad)
    return {
        facultad: Separacion(
            sorted(c for f, cs in grupos.items() if f != facultad for c in cs),
            sorted(codigos),
            [],
        )
        for facultad, codigos in sorted(grupos.items())
    }


def cumple_minimo(codigo_a_facultad: dict[str, str]) -> bool:
    """Al menos MIN_FACULTADES facultades con MIN_POR_FACULTAD sílabos cada una."""
    suficientes = [f for f, cs in _por_facultad(codigo_a_facultad).items() if len(cs) >= MIN_POR_FACULTAD]
    return len(suficientes) >= MIN_FACULTADES
