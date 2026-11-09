"""Revisión de calidad de un lote de sílabos simulados.

El informe solo lleva conteos y fracciones, nunca texto. La única salida con texto es
la muestra para revisión humana, que se escribe en `datos_cd/` y no se versiona.
`torch` y `sentence_transformers` se importan solo dentro del vectorizador real.
"""
import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

import numpy as np

from app.silabo.modelo import SilaboUTI
from app.agentes.facultades import normalizar
from ciencia_datos import consola_utf8
from ciencia_datos.casi_repetidos import UMBRAL_CASI_REPETIDO, normalizar_l2
from ciencia_datos.corpus import Fragmento, fragmentos, leer_carpeta, tiene_datos_personales
from ciencia_datos.origen import es_simulado
from ciencia_datos.sim_plan import cupos

RAIZ = Path(__file__).resolve().parents[2]
CATALOGO = RAIZ / "kb" / "catalogo.yaml"
BASE_POR_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
PALABRAS_INICIO = 5
PROPORCION_INICIO = 0.05
MUESTRA_POR_DEFECTO = 20
SEMILLA = 42
BLOQUE = 1024

# Criterios para pasar el piloto.
MAX_CASI_REPETIDOS_ENTRE_CARRERAS = 0.10
MAX_INICIO_REPETIDO = 0.30
MIN_FRAGMENTOS = 20
MAX_FRAGMENTOS = 80

Vectorizar = Callable[[list[str]], np.ndarray]


def _vectorizar_real(base: str = BASE_POR_DEFECTO) -> Vectorizar:
    """Vectorizador con el modelo base, en CPU y con vectores normalizados."""

    def vectorizar(textos: list[str]) -> np.ndarray:
        from sentence_transformers import SentenceTransformer

        if "modelo" not in vectorizar.__dict__:
            vectorizar.modelo = SentenceTransformer(base, device="cpu")
        return vectorizar.modelo.encode(
            textos, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )

    return vectorizar


def _cadenas(valor):
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _cadenas(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _cadenas(v)


def _datos_personales(silabos: list[SilaboUTI]) -> int:
    """Cadenas del sílabo que parecen datos personales; solo el conteo."""
    return sum(
        tiene_datos_personales(c)
        for s in silabos
        for c in _cadenas(s.model_dump(mode="json"))
    )


def _fraccion_casi_repetidos(
    v: np.ndarray, silabo: np.ndarray, carrera: np.ndarray, umbral: float
) -> tuple[float, float]:
    """(global, entre carreras): fragmentos con un casi igual en otro sílabo / otra carrera."""
    n = len(v)
    if n == 0:
        return 0.0, 0.0
    en_otro_silabo = np.zeros(n, dtype=bool)
    en_otra_carrera = np.zeros(n, dtype=bool)
    for i in range(0, n, BLOQUE):
        s = v[i : i + BLOQUE] @ v.T >= umbral
        en_otro_silabo[i : i + BLOQUE] = (s & (silabo[i : i + BLOQUE, None] != silabo[None, :])).any(1)
        en_otra_carrera[i : i + BLOQUE] = (s & (carrera[i : i + BLOQUE, None] != carrera[None, :])).any(1)
    return float(en_otro_silabo.mean()), float(en_otra_carrera.mean())


def _fraccion_inicio_repetido(textos: list[str]) -> float:
    """Parte de los fragmentos cuyas primeras palabras abren el 5 % o más del lote."""
    if not textos:
        return 0.0
    inicios = [" ".join(t.lower().split()[:PALABRAS_INICIO]) for t in textos]
    cuenta = Counter(inicios)
    minimo = PROPORCION_INICIO * len(textos)
    return sum(1 for i in inicios if cuenta[i] >= minimo) / len(textos)


def revisar(silabos: list[SilaboUTI], vectorizar: Vectorizar, esperadas: set[str] | None = None) -> dict:
    """Informe del lote: estructura, casi repetidos, inicios repetidos y datos personales.

    `esperadas` son las facultades que el lote debe cubrir; sin ellas, basta con que las presentes tengan sílabos."""
    por_facultad: Counter = Counter()
    por_carrera: dict[str, Counter] = {}
    por_silabo: list[int] = []
    frags: list[Fragmento] = []
    for s in silabos:
        por_facultad[s.facultad] += 1
        por_carrera.setdefault(s.facultad, Counter())[s.carrera] += 1
        f = fragmentos(s)
        por_silabo.append(len(f))
        frags += f
    if frags:
        v = normalizar_l2(np.asarray(vectorizar([f.texto for f in frags])))
        global_, entre = _fraccion_casi_repetidos(
            v,
            np.array([f.codigo_pf for f in frags]),
            np.array([f"{f.facultad}\x00{f.carrera}" for f in frags]),
            UMBRAL_CASI_REPETIDO,
        )
    else:
        global_ = entre = 0.0
    return {
        "n_silabos": len(silabos),
        "n_fragmentos": len(frags),
        "silabos_por_facultad": dict(sorted(por_facultad.items())),
        "silabos_por_carrera": {
            f: dict(sorted(c.items())) for f, c in sorted(por_carrera.items())
        },
        "fragmentos_por_silabo": {
            "minimo": min(por_silabo, default=0),
            "maximo": max(por_silabo, default=0),
        },
        "umbral_casi_repetido": UMBRAL_CASI_REPETIDO,
        "fraccion_casi_repetidos": global_,
        "fraccion_casi_repetidos_entre_carreras": entre,
        "fraccion_inicio_repetido": _fraccion_inicio_repetido([f.texto for f in frags]),
        "datos_personales_detectados": _datos_personales(silabos),
        "facultades_esperadas": None if esperadas is None else sorted(esperadas),
    }


def dictaminar_lote(informe: dict) -> list[str]:
    """Los criterios del piloto que el informe incumple; vacío si pasa."""
    falla: list[str] = []
    if informe["datos_personales_detectados"] > 0:
        falla.append("datos_personales_detectados == 0")
    if informe["fraccion_casi_repetidos_entre_carreras"] >= MAX_CASI_REPETIDOS_ENTRE_CARRERAS:
        falla.append(
            f"fraccion_casi_repetidos_entre_carreras < {MAX_CASI_REPETIDOS_ENTRE_CARRERAS:.2f}"
        )
    if informe["fraccion_inicio_repetido"] >= MAX_INICIO_REPETIDO:
        falla.append(f"fraccion_inicio_repetido < {MAX_INICIO_REPETIDO:.2f}")
    por = informe["fragmentos_por_silabo"]
    if informe["n_silabos"] and not MIN_FRAGMENTOS <= por["minimo"] <= por["maximo"] <= MAX_FRAGMENTOS:
        falla.append(f"fragmentos_por_silabo entre {MIN_FRAGMENTOS} y {MAX_FRAGMENTOS}")
    esperadas = informe.get("facultades_esperadas")
    presentes = {normalizar(f) for f, n in informe["silabos_por_facultad"].items() if n >= 1 and f}
    if not informe["n_silabos"] or any(
        n < 1 for n in informe["silabos_por_facultad"].values()
    ) or "" in informe["silabos_por_facultad"] or (
        esperadas is not None and not {normalizar(f) for f in esperadas} <= presentes
    ):
        falla.append("cobertura_facultades: todas con sílabos")
    return falla


def muestrear(silabos: list[SilaboUTI], n: int = MUESTRA_POR_DEFECTO) -> list[Fragmento]:
    """`n` fragmentos repartidos en rotación por facultad, con semilla fija."""
    azar = random.Random(SEMILLA)
    grupos: dict[str, list[Fragmento]] = {}
    for s in silabos:
        grupos.setdefault(s.facultad, []).extend(fragmentos(s))
    colas = []
    for f in sorted(grupos):
        azar.shuffle(grupos[f])
        colas.append(grupos[f])
    salida: list[Fragmento] = []
    while len(salida) < n and any(colas):
        for cola in colas:
            if cola and len(salida) < n:
                salida.append(cola.pop())
    return salida


def _celda(valor: str) -> str:
    """Una celda que empieza por `=`, `+`, `-` o `@` se escribe con `'` delante: Excel no la toma por fórmula."""
    return "'" + valor if valor[:1] in ("=", "+", "-", "@") else valor


def _esperadas(codigos: set[str]) -> set[str]:
    """Facultades con cupos cuyos códigos están entre los leídos; si no hay ninguno, todas las con cupos."""
    todos = cupos(CATALOGO)
    propias = {c.facultad for c in todos if c.codigo in codigos}
    return propias or {c.facultad for c in todos}


def _escribir_muestra(ruta: Path, muestra: list[Fragmento]) -> None:
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["codigo", "carrera", "momento", "tipo", "texto", "parece_real"])
        for x in muestra:
            w.writerow([_celda(x.codigo_pf), _celda(x.carrera), "" if x.momento is None else x.momento,
                        x.tipo, _celda(x.texto), ""])


def main(argv: list[str] | None = None) -> int:
    consola_utf8()
    p = argparse.ArgumentParser(description="Revisa la calidad de un lote de sílabos simulados.")
    p.add_argument("--silabos", required=True, type=Path)
    p.add_argument("--salida", required=True, type=Path)
    p.add_argument("--muestra", type=int, default=MUESTRA_POR_DEFECTO)
    p.add_argument("--base", default=BASE_POR_DEFECTO)
    a = p.parse_args(argv)

    permitida = (RAIZ / "datos_cd").resolve()
    if not a.salida.resolve().is_relative_to(permitida):
        print("entrada inválida: --salida debe quedar dentro de datos_cd/", file=sys.stderr)
        return 2
    silabos, rechazados = leer_carpeta(a.silabos)
    codigos = {s.proyecto_formativo.codigo for s in silabos}
    if not all(es_simulado(c) for c in codigos):
        print("entrada inválida: el lote trae sílabos que no son simulados; la muestra solo admite simulados",
              file=sys.stderr)
        return 2
    informe = revisar(silabos, _vectorizar_real(a.base), _esperadas(codigos))
    informe["archivos_rechazados"] = len(rechazados)
    incumplidos = dictaminar_lote(informe)
    informe["criterios_incumplidos"] = incumplidos
    destino = a.salida / "simulacion"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "revision.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    muestra = muestrear(silabos, a.muestra)
    _escribir_muestra(destino / "muestra-revision.csv", muestra)

    print(
        f"sílabos: {informe['n_silabos']}, fragmentos: {informe['n_fragmentos']}, "
        f"rechazados: {len(rechazados)}, muestra: {len(muestra)}"
    )
    print(
        f"casi repetidos: {informe['fraccion_casi_repetidos']:.3f} "
        f"(entre carreras {informe['fraccion_casi_repetidos_entre_carreras']:.3f}), "
        f"inicio repetido: {informe['fraccion_inicio_repetido']:.3f}, "
        f"datos personales: {informe['datos_personales_detectados']}"
    )
    if incumplidos:
        print("Criterios incumplidos:")
        for c in incumplidos:
            print(f"  - {c}")
        return 1
    print("El lote cumple los criterios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
