"""Filtro de casi repetidos por similitud coseno entre vectores.

No importa `torch` ni `sentence_transformers`: recibe los vectores ya calculados.
"""
import numpy as np

UMBRAL_CASI_REPETIDO = 0.95


def normalizar_l2(vectores: np.ndarray) -> np.ndarray:
    """Filas de longitud 1; una fila nula queda en ceros."""
    v = np.asarray(vectores, dtype=np.float32)
    normas = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(normas == 0, 1.0, normas)


def filtrar(
    textos: list[str],
    vectores: np.ndarray,
    *,
    contra: np.ndarray | None = None,
    umbral: float = UMBRAL_CASI_REPETIDO,
) -> tuple[list[str], int]:
    """Conserva el primero de cada grupo de casi repetidos.

    Quita el texto cuyo coseno con uno ya conservado, o con una fila de `contra`,
    iguala o supera el umbral. Devuelve los textos conservados y cuántos quitó.
    """
    if not textos:
        return [], 0
    v = normalizar_l2(vectores)
    c = normalizar_l2(contra) if contra is not None and len(contra) else None
    conservados = np.empty_like(v)
    n = 0
    salida: list[str] = []
    for i, texto in enumerate(textos):
        repetido = c is not None and bool(np.any(c @ v[i] >= umbral))
        if not repetido and n:
            repetido = bool(np.any(conservados[:n] @ v[i] >= umbral))
        if repetido:
            continue
        conservados[n] = v[i]
        n += 1
        salida.append(texto)
    return salida, len(textos) - len(salida)
