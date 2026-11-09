"""Razonador en producción: vectores de frases con el modelo exportado, sin PyTorch.

Carga la carpeta que deja `ciencia_datos.entrenar` (`onnx/model.onnx`, `tokenizer.json`,
`metadatos.json`) con `onnxruntime` y `tokenizers`. Los vectores llevan agrupación media con la
máscara y norma L2, así que el producto punto entre dos vectores es su coseno.

Sirve a dos decisiones del planificador: `temas` agrupa textos por significado y `casos_libres`
descarta los casos que se parecen a algún entregable aunque no compartan palabras.

`ciencia_datos.evaluar` calcula sus vectores con este mismo código, para que el modelo que se
evalúa y el que se sirve no puedan diferir. Este módulo no importa `torch` ni `ciencia_datos`.
"""
import hashlib
import json
import math
from collections.abc import Callable
from pathlib import Path

import numpy as np

UMBRAL_DESARROLLO = 0.6  # solo con exigir_aprobado=False y un modelo sin umbral fijado
LONGITUD_POR_OMISION = 128  # la de entrenar.py, para carpetas que no registran su longitud
LOTE = 32
LONGITUD_TOPE = 512  # el máximo de posiciones del modelo base
K_MAXIMO = 8
SEMILLA = 42


class RazonadorInvalido(Exception):
    """La carpeta del modelo no sirve para responder; el mensaje nombra la causa, nunca un texto."""


def huella_pesos(ruta: Path) -> str:
    """SHA-256 de lo que define al modelo: `onnx/model.onnx` y, si existe, `onnx/model.onnx.data`."""
    h = hashlib.sha256()
    for nombre in ("model.onnx", "model.onnx.data"):
        archivo = Path(ruta) / "onnx" / nombre
        if archivo.is_file():
            h.update(f"{nombre}:{archivo.stat().st_size};".encode())
            with open(archivo, "rb") as f:
                for bloque in iter(lambda: f.read(1 << 20), b""):
                    h.update(bloque)
    return h.hexdigest()


def _leer_metadatos(ruta: Path) -> dict:
    if not ruta.is_dir():
        raise RazonadorInvalido("la carpeta del razonador no existe")
    archivo = ruta / "metadatos.json"
    if not archivo.is_file():
        raise RazonadorInvalido("falta metadatos.json")
    try:
        meta = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RazonadorInvalido("metadatos.json no se puede leer") from None
    if not isinstance(meta, dict):
        raise RazonadorInvalido("metadatos.json no es un objeto")
    return meta


def _validar(ruta: Path, exigir_aprobado: bool) -> tuple[dict, float]:
    """Metadatos y umbral. Toda condición que impida servir se detecta antes de abrir el modelo."""
    meta = _leer_metadatos(ruta)
    if not (ruta / "onnx" / "model.onnx").is_file():
        raise RazonadorInvalido("falta onnx/model.onnx")
    if not (ruta / "tokenizer.json").is_file():
        raise RazonadorInvalido("falta tokenizer.json")
    umbral = meta.get("umbral")
    if umbral is not None and (
        isinstance(umbral, bool) or not isinstance(umbral, (int, float))
        or not math.isfinite(umbral) or not -1 <= umbral <= 1
    ):
        raise RazonadorInvalido("el umbral de metadatos.json no es un coseno válido (finito, entre -1 y 1)")
    if exigir_aprobado:
        if meta.get("preliminar") is True:
            raise RazonadorInvalido("el modelo es preliminar (entrenado con sílabos simulados): no se sirve")
        sep = meta.get("separacion")
        if isinstance(sep, dict) and any(
            isinstance(c, str) and c.startswith("SIM-")
            for clave in ("entrenamiento", "prueba") if isinstance(sep.get(clave), list)
            for c in sep[clave]
        ):
            raise RazonadorInvalido("el modelo se entrenó o probó con sílabos simulados: no se sirve")
        if meta.get("humo") is not False:
            raise RazonadorInvalido("el modelo es de humo o no declara humo: false")
        if meta.get("aprobado") is not True:
            raise RazonadorInvalido("el modelo no está aprobado")
        if umbral is None:
            raise RazonadorInvalido("el modelo aprobado no tiene umbral")
        if not meta.get("huella_pesos"):
            raise RazonadorInvalido("el modelo aprobado no tiene huella_pesos")
        try:
            coincide = huella_pesos(ruta) == meta["huella_pesos"]
        except OSError:
            raise RazonadorInvalido("los pesos del modelo no se pueden leer") from None
        if not coincide:
            raise RazonadorInvalido("los pesos no coinciden con huella_pesos: la carpeta no es la que se aprobó")
    return meta, float(UMBRAL_DESARROLLO if umbral is None else umbral)


def _abrir(ruta: Path, longitud: int) -> Callable[[list[str]], np.ndarray]:
    """Sesión y tokenizador, creados una sola vez; la función devuelta es segura entre hilos."""
    import onnxruntime as ort
    from tokenizers import Tokenizer

    try:
        tok = Tokenizer.from_file(str(ruta / "tokenizer.json"))
        sesion = ort.InferenceSession(str(ruta / "onnx" / "model.onnx"), providers=["CPUExecutionProvider"])
    except Exception:
        raise RazonadorInvalido("tokenizer.json u onnx/model.onnx no se pueden leer") from None
    tok.enable_truncation(max_length=longitud)
    tok.enable_padding()
    pedidas = {i.name for i in sesion.get_inputs()}

    def codificar(textos: list[str]) -> np.ndarray:
        codificados = tok.encode_batch(textos)
        ids = np.array([c.ids for c in codificados], dtype=np.int64)
        mascara = np.array([c.attention_mask for c in codificados], dtype=np.int64)
        entradas = {"input_ids": ids, "attention_mask": mascara, "token_type_ids": np.zeros_like(ids)}
        oculto = sesion.run(None, {k: v for k, v in entradas.items() if k in pedidas})[0]
        m = mascara[..., None].astype(oculto.dtype)
        media = (oculto * m).sum(axis=1) / np.maximum(m.sum(axis=1), 1)
        return media / np.maximum(np.linalg.norm(media, axis=1, keepdims=True), 1e-12)

    return codificar


class Razonador:
    """Vectores normalizados de frases y las dos decisiones que se apoyan en ellos."""

    def __init__(self, codificar: Callable[[list[str]], np.ndarray], *, version: str, umbral: float):
        self._codificar = codificar
        self.version = version
        self.umbral = umbral

    @classmethod
    def cargar(cls, ruta: Path, *, exigir_aprobado: bool) -> "Razonador":
        ruta = Path(ruta)
        meta, umbral = _validar(ruta, exigir_aprobado)
        longitud = meta.get("longitud_maxima", LONGITUD_POR_OMISION)
        if isinstance(longitud, bool) or not isinstance(longitud, int) or not 1 <= longitud <= LONGITUD_TOPE:
            raise RazonadorInvalido(f"longitud_maxima de metadatos.json debe ser un entero de 1 a {LONGITUD_TOPE}")
        codificar = _abrir(ruta, longitud)
        # Un modelo que abre pero no responde debe fallar aquí, no en el primer trabajo.
        try:
            valido = np.isfinite(codificar(["prueba"])).all()
        except Exception:
            valido = False
        if not valido:
            raise RazonadorInvalido("el modelo no superó la inferencia de prueba")
        return cls(codificar, version=str(meta.get("version", ruta.name)), umbral=umbral)

    def vectores(self, textos: list[str]) -> np.ndarray:
        """Una fila por texto, de norma 1. Sin textos, una matriz de cero filas."""
        if not textos:
            return np.zeros((0, 0))
        return np.vstack([self._codificar(list(textos[i : i + LOTE])) for i in range(0, len(textos), LOTE)])

    def temas(self, textos: list[str]) -> list[list[int]]:
        """Índices de `textos` agrupados por significado, en orden estable (por primer índice).

        K-medias con semilla fija; k entre 2 y min(8, n-1) por silueta, y a igualdad el menor.
        Con tres textos o menos cada uno es su propio tema, sin correr el modelo.
        """
        n = len(textos)
        if n <= 3:
            return [[i] for i in range(n)]
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        X = self.vectores(textos)
        mejor, mejor_silueta = None, -np.inf
        distintos = len(np.unique(X, axis=0))  # k-medias no puede separar más grupos que puntos distintos
        for k in range(2, min(K_MAXIMO, n - 1, distintos) + 1):
            etiquetas = KMeans(n_clusters=k, n_init=20, random_state=SEMILLA).fit_predict(X)
            if not 2 <= len(set(etiquetas.tolist())) <= n - 1:  # textos repetidos: silueta indefinida
                continue
            silueta = float(silhouette_score(X, etiquetas))
            if silueta > mejor_silueta:
                mejor, mejor_silueta = etiquetas, silueta
        if mejor is None:
            return [list(range(n))]
        grupos: dict[int, list[int]] = {}
        for i, e in enumerate(mejor.tolist()):
            grupos.setdefault(e, []).append(i)
        return sorted(grupos.values(), key=lambda g: g[0])

    def casos_libres(self, casos: list[str], entregables: list[str]) -> list[str]:
        """Casos cuyo mayor coseno con cualquier entregable queda por debajo del umbral."""
        if not entregables or not casos:
            return list(casos)
        parecido = (self.vectores(casos) @ self.vectores(entregables).T).max(axis=1)
        # Regla: un caso con coseno igual al umbral se descarta; solo queda libre el estrictamente menor.
        return [c for c, p in zip(casos, parecido) if p < self.umbral]
