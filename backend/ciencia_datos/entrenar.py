"""Entrenamiento del codificador: SimCSE sin etiquetas y exportación a ONNX.

Cada texto es su propio positivo; el dropout (0,1) los vuelve dos vistas distintas y
el resto del lote hace de negativos (`MultipleNegativesRankingLoss`, escala 20 =
temperatura 0,05). Solo se entrena con el grupo de entrenamiento de la separación.

`torch` y `sentence_transformers` se importan dentro de las funciones: en producción
y en las pruebas normales no existen. Nunca se imprimen textos, solo conteos.
"""
import argparse
import hashlib
import json
import random
import sys
import warnings
from pathlib import Path

from app.agentes.facultades import cargar_catalogo, normalizar
from ciencia_datos import consola_utf8
from ciencia_datos.corpus import fragmentos, leer_con_origen, por_carpeta
from ciencia_datos.casi_repetidos import filtrar
from ciencia_datos.origen import es_simulado
from ciencia_datos.separar import MIN_FACULTADES, MIN_POR_FACULTAD, cumple_minimo, separar, separar_preliminar

BASE_POR_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RAIZ = Path(__file__).resolve().parents[2]
DROPOUT = 0.1
ESCALA = 20.0  # 1 / temperatura 0,05
LOTE = 32
TASA = 2e-5
LONGITUD_MAXIMA = 128
TEXTOS_HUMO = 64
SEMILLA = 42
CANDADO = "evaluacion.candado"
_ENTRADAS = ("input_ids", "attention_mask", "token_type_ids")


def _dispositivo() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def _tokenizar(modelo, textos: list[str]):
    return modelo.tokenizer(
        textos,
        padding=True,
        truncation=True,
        max_length=modelo.max_seq_length,
        return_tensors="pt",
    )


def _ajustar(modelo, textos: list[str], epocas: int, dispositivo: str) -> None:
    """SimCSE: pares (texto, texto) con dropout activo, lote LOTE."""
    import torch
    from sentence_transformers.sentence_transformer import losses

    for modulo in modelo.modules():
        if isinstance(modulo, torch.nn.Dropout):
            modulo.p = DROPOUT
    perdida = losses.MultipleNegativesRankingLoss(modelo, scale=ESCALA)
    optimizador = torch.optim.AdamW(modelo.parameters(), lr=TASA)
    azar = random.Random(SEMILLA)
    torch.manual_seed(SEMILLA)
    unicos = list(dict.fromkeys(textos))  # un repetido en el lote sería un falso negativo
    modelo.train()
    for _ in range(epocas):
        azar.shuffle(unicos)
        for i in range(0, len(unicos), LOTE):
            lote = unicos[i : i + LOTE]
            if len(lote) < 2:
                continue
            rasgos = {k: v.to(dispositivo) for k, v in _tokenizar(modelo, lote).items() if k in _ENTRADAS}
            # Dos pasadas con el mismo lote: el dropout las vuelve distintas.
            optimizador.zero_grad()
            perdida([dict(rasgos), dict(rasgos)], None).backward()
            optimizador.step()
    modelo.eval()


def _exportar_onnx(modelo, destino: Path) -> None:
    """Solo el transformador; la agrupación media la hace el consumidor."""
    import torch

    transformador = modelo[0].auto_model.to("cpu").eval()
    rasgos = _tokenizar(modelo, ["texto de ejemplo para trazar", "otro más largo para el lote " * 3])
    nombres = [n for n in _ENTRADAS if n in rasgos]

    class _Salida(torch.nn.Module):
        def __init__(self, interno):
            super().__init__()
            self.interno = interno

        def forward(self, input_ids, attention_mask, token_type_ids=None):
            return self.interno(
                input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids
            ).last_hidden_state

    lote, secuencia = torch.export.Dim("lote", min=1), torch.export.Dim("secuencia", min=2)
    ejes = {n: {0: lote, 1: secuencia} for n in nombres}
    destino.parent.mkdir(parents=True, exist_ok=True)
    with torch.no_grad(), warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="# The axis name")
        torch.onnx.export(
            _Salida(transformador).eval(),
            (),
            str(destino),
            kwargs={n: rasgos[n].to("cpu") for n in nombres},
            input_names=nombres,
            output_names=["last_hidden_state"],
            dynamic_shapes=ejes,
            dynamo=True,
        )


def _versiones(destino: Path) -> dict:
    """Con qué se exportó, para poder repetirlo: torch, onnxruntime y el opset del grafo."""
    import onnx
    import onnxruntime
    import torch

    grafo = onnx.load(str(destino), load_external_data=False)
    opset = next(o.version for o in grafo.opset_import if o.domain in ("", "ai.onnx"))
    return {"torch": torch.__version__, "onnxruntime": onnxruntime.__version__, "opset": opset}


def _vectorizar_base(base: str, textos: list[str]):
    """Vectores del modelo base sin ajustar, para el filtro de casi repetidos."""
    from sentence_transformers import SentenceTransformer

    modelo = SentenceTransformer(base, device=_dispositivo())
    modelo.max_seq_length = min(modelo.max_seq_length or LONGITUD_MAXIMA, LONGITUD_MAXIMA)
    return modelo.encode(textos, batch_size=LOTE, show_progress_bar=False)


def entrenar(
    textos: list[str],
    base: str,
    salida: Path,
    *,
    epocas: int = 1,
    humo: bool = False,
    ajuste: bool = True,
    metadatos: dict | None = None,
) -> Path:
    """Ajusta `base` con `textos` (si `ajuste`) y deja `onnx/`, `tokenizer.json` y `metadatos.json`."""
    from sentence_transformers import SentenceTransformer

    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    dispositivo = _dispositivo()
    modelo = SentenceTransformer(base, device=dispositivo)
    modelo.max_seq_length = min(modelo.max_seq_length or LONGITUD_MAXIMA, LONGITUD_MAXIMA)
    usados = list(dict.fromkeys(textos))
    if humo:
        usados = usados[:TEXTOS_HUMO]
    if ajuste:
        _ajustar(modelo, usados, epocas, dispositivo)
    _exportar_onnx(modelo, salida / "onnx" / "model.onnx")
    modelo.tokenizer.backend_tokenizer.save(str(salida / "tokenizer.json"))
    meta = {
        "version": salida.name,
        "base": base,
        "humo": humo,
        "aprobado": False,
        "umbral": None,
        "longitud_maxima": modelo.max_seq_length,
        "ajuste": ajuste,
        "epocas": epocas if ajuste else 0,
        "n_fragmentos": len(usados) if ajuste else 0,
        "dispositivo": dispositivo,
        "versiones": _versiones(salida / "onnx" / "model.onnx"),
        "n_silabos": 0,
        "huella_separacion": None,
    }
    meta.update(metadatos or {})
    (salida / "metadatos.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return salida


def codigo_a_facultad(silabos, catalogo: dict[str, str]) -> tuple[dict[str, str], int]:
    """Código de proyecto formativo -> sigla, y cuántas facultades no están en el catálogo."""
    resultado: dict[str, str] = {}
    sin_sigla: set[str] = set()
    for s in silabos:
        nombre = normalizar(s.facultad)
        if nombre not in catalogo:
            sin_sigla.add(nombre)
        resultado[s.proyecto_formativo.codigo] = catalogo.get(nombre, nombre)
    return resultado, len(sin_sigla)


def huella(separacion: dict) -> str:
    canonico = json.dumps(separacion, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    consola_utf8()
    p = argparse.ArgumentParser(prog="python -m ciencia_datos.entrenar")
    p.add_argument("--silabos", type=Path, nargs="+", required=True, help="una o varias carpetas")
    p.add_argument("--salida", type=Path, required=True)
    p.add_argument("--base", default=BASE_POR_DEFECTO)
    p.add_argument("--epocas", type=int, default=1)
    p.add_argument("--humo", action="store_true", help="prueba rápida: sin exigir el mínimo")
    p.add_argument("--sin-ajuste", action="store_true", help="exporta el modelo base sin entrenar")
    a = p.parse_args(argv)

    if (a.salida / "metadatos.json").exists() or (a.salida / CANDADO).exists():
        raise SystemExit("--salida ya contiene un modelo y no se sobrescribe; use otra carpeta (una versión nueva).")
    con_origen, rechazados = leer_con_origen(a.silabos)
    silabos = [s for s, _ in con_origen]
    catalogo = cargar_catalogo(RAIZ / "kb" / "catalogo.yaml")
    mapa, sin_sigla = codigo_a_facultad(silabos, catalogo)
    preliminar = any(es_simulado(c) for c in mapa)
    if not preliminar and not a.humo and not cumple_minimo(mapa):
        raise SystemExit(
            f"Se exige un mínimo de {MIN_FACULTADES} facultades con {MIN_POR_FACULTAD} sílabos "
            "cada una; use --humo para una prueba rápida."
        )
    simulados = {c: f for c, f in mapa.items() if es_simulado(c)}
    if preliminar and not a.humo and not cumple_minimo(simulados):
        raise SystemExit(
            f"Se exige un mínimo de {MIN_FACULTADES} facultades con {MIN_POR_FACULTAD} sílabos "
            "simulados cada una; use --humo para una prueba rápida."
        )
    sep = separar_preliminar(mapa) if preliminar else separar(mapa)
    de_entrenamiento = set(sep.entrenamiento)
    de_prueba = set(sep.prueba)
    de_control = set(sep.control)

    def clave(texto: str) -> str:
        return texto.strip().casefold()

    # Un texto que también está en un sílabo de prueba (o de control) no entrena: inflaría la evaluación.
    de_comparacion = de_prueba | de_control
    textos_de_comparacion = list(dict.fromkeys(
        f.texto for s in silabos if s.proyecto_formativo.codigo in de_comparacion for f in fragmentos(s)
    ))
    prohibidos = {clave(t) for t in textos_de_comparacion}
    candidatos = {
        clave(f.texto): f.texto
        for s in silabos
        if s.proyecto_formativo.codigo in de_entrenamiento
        for f in fragmentos(s)
    }
    excluidos = sum(1 for k in candidatos if k in prohibidos)
    textos = [t for k, t in candidatos.items() if k not in prohibidos]
    casi_repetidos = 0
    if preliminar and not a.sin_ajuste and textos:
        # Ningún texto de entrenamiento se parece a lo que prueba o controla.
        vectores = _vectorizar_base(a.base, textos + textos_de_comparacion)
        textos, casi_repetidos = filtrar(
            textos, vectores[: len(textos)], contra=vectores[len(textos) :] if textos_de_comparacion else None
        )
    if a.humo:
        textos = textos[:TEXTOS_HUMO]
    n_entrenados = 0 if a.sin_ajuste else len(textos)
    separacion = {"entrenamiento": sep.entrenamiento, "prueba": sep.prueba}
    if sep.control:
        separacion["control_real"] = sep.control
    metadatos = {
        "n_silabos": len(silabos),
        "n_textos_excluidos_por_prueba": excluidos,
        "n_entrenamiento": len(sep.entrenamiento),
        "n_prueba": len(sep.prueba),
        "separacion": separacion,
        "huella_separacion": huella(separacion),
    }
    if preliminar:
        metadatos |= {
            "preliminar": True,
            "origen": {"simulados": len(simulados), "reales": len(mapa) - len(simulados)},
            "n_casi_repetidos_excluidos": casi_repetidos,
        }
    entrenar(
        textos,
        a.base,
        a.salida,
        epocas=a.epocas,
        humo=a.humo,
        ajuste=not a.sin_ajuste,
        metadatos=metadatos,
    )
    print(
        f"sílabos={len(silabos)} rechazados={len(rechazados)} "
        f"entrenamiento={len(sep.entrenamiento)} prueba={len(sep.prueba)} "
        f"fragmentos={n_entrenados} excluidos_por_prueba={excluidos} facultades_sin_sigla={sin_sigla} avisos={len(sep.avisos)}"
        + (f" preliminar=True control_real={len(sep.control)} casi_repetidos_excluidos={casi_repetidos}" if preliminar else "")
    )
    recuento: dict[str, int] = {}
    for raiz in a.silabos:
        propias = [r for _, r in con_origen if r.is_relative_to(raiz)]
        for nombre, n in por_carpeta(propias, raiz).items():
            recuento[nombre] = recuento.get(nombre, 0) + n
    recuento = dict(sorted(recuento.items()))
    print("por_carpeta: " + " ".join(f"{nombre}={n}" for nombre, n in recuento.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
