"""Estadística pura de la evaluación: sin lectura de archivos ni de modelos.

Las métricas indefinidas son NaN (el informe las escribe como null) y nunca cumplen un criterio.
"""
import math

import numpy as np

EXHAUSTIVIDAD_UMBRAL = 0.90  # al elegir el umbral con el 70 %


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de Wilson al 95 % para una proporción k/n."""
    if n <= 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    mitad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (centro - mitad, centro + mitad)


def metricas(pred, y) -> dict:
    """Precisión, exhaustividad y F1. F1 = 0 si hay positivos y ningún acierto; NaN solo sin positivos."""
    pred, y = np.asarray(pred, bool), np.asarray(y, bool)
    tp = int((pred & y).sum())
    precision = tp / pred.sum() if pred.sum() else math.nan
    exhaustividad = tp / y.sum() if y.sum() else math.nan
    if not y.sum():
        f1 = math.nan
    elif not tp:
        f1 = 0.0
    else:
        f1 = 2 * precision * exhaustividad / (precision + exhaustividad)
    return {"precision": precision, "exhaustividad": exhaustividad, "f1": f1}


def elegir_umbral(sim, etiquetas, exhaustividad_min: float = EXHAUSTIVIDAD_UMBRAL) -> float:
    """Umbral (predice parecido si sim >= umbral) de máxima precisión con exhaustividad >= mínimo.

    En empate de precisión gana el umbral más bajo. Solo debe recibir el 70 %.
    """
    sim, y = np.asarray(sim, float), np.asarray(etiquetas, bool)
    if not y.any():
        raise ValueError("sin ejemplos positivos no hay umbral")
    mejor, mejor_precision = float(sim.min()), -1.0
    for t in sorted(set(sim.tolist())):
        m = metricas(sim >= t, y)
        if m["exhaustividad"] >= exhaustividad_min and m["precision"] > mejor_precision + 1e-12:
            mejor, mejor_precision = float(t), m["precision"]
    return mejor


def mcnemar_conteos(a_ok, b_ok) -> tuple[int, int]:
    """(aciertos solo de A, aciertos solo de B): la dirección que el valor p no da."""
    a, b = np.asarray(a_ok, bool), np.asarray(b_ok, bool)
    return int((a & ~b).sum()), int((~a & b).sum())


def mcnemar(a_ok, b_ok) -> float:
    """Valor p exacto (bilateral) de McNemar entre dos clasificadores sobre los mismos pares."""
    solo_a, solo_b = mcnemar_conteos(a_ok, b_ok)
    n = solo_a + solo_b
    if n == 0:
        return 1.0
    cola = sum(math.comb(n, i) for i in range(min(solo_a, solo_b) + 1)) / 2**n
    return min(1.0, 2 * cola)


def kappa(a, b) -> float:
    """Kappa de Cohen entre dos docentes. NaN si no está definido."""
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0 or len(a) != len(b):
        return math.nan
    po = float((a == b).mean())
    pe = sum(float((a == c).mean()) * float((b == c).mean()) for c in set(a.tolist()) | set(b.tolist()))
    return math.nan if pe >= 1 else (po - pe) / (1 - pe)


def agrupar(X, k: int, semilla: int = 42) -> np.ndarray:
    from sklearn.cluster import KMeans

    return KMeans(n_clusters=k, n_init=1, random_state=semilla).fit_predict(X)


def _silueta(X, etiquetas) -> float:
    from sklearn.metrics import silhouette_score

    return float(silhouette_score(X, etiquetas)) if len(set(etiquetas.tolist())) > 1 else math.nan


def _l2(X):
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)


def silueta_frente_al_azar(X, k: int, veces: int = 30, semilla: int = 42) -> dict:
    """Silueta de k-medias frente a la de datos sin estructura (columnas barajadas, filas en L2)."""
    X = np.asarray(X, float)
    real = _silueta(X, agrupar(X, k, semilla))
    azar = np.random.default_rng(semilla)
    nulas = []
    for _ in range(veces):
        Y = _l2(np.column_stack([azar.permutation(X[:, j]) for j in range(X.shape[1])]))
        nulas.append(_silueta(Y, agrupar(Y, k, semilla)))
    p95 = float(np.nanpercentile(nulas, 95))
    return {"real": real, "p95": p95, "media_azar": float(np.nanmean(nulas)), "supera": bool(real > p95)}


def estabilidad(X, k: int, semillas: int = 20) -> float:
    """ARI medio entre las agrupaciones de k-medias con distintas semillas."""
    from sklearn.metrics import adjusted_rand_score

    X = np.asarray(X, float)
    etiquetas = [agrupar(X, k, s) for s in range(semillas)]
    pares = [adjusted_rand_score(etiquetas[i], etiquetas[j]) for i in range(semillas) for j in range(i + 1, semillas)]
    return float(np.mean(pares)) if pares else math.nan


def cumple(valor, minimo: float) -> bool:
    """valor >= mínimo; None o NaN nunca cumplen."""
    return valor is not None and not (isinstance(valor, float) and math.isnan(valor)) and valor >= minimo
