"""Informe del modelo preliminar: compara el codificador ajustado con el base, sin aprobar nada.

Mide, sobre los mismos textos (fragmentos de los sílabos de `prueba` simulados y de
`control_real`; nunca los de entrenamiento), qué tan bien agrupan por carrera y por facultad
los dos modelos. No toma candado, no ajusta, no fija umbral y nunca escribe `aprobado`: los
textos los redactó Qwen, así que las cifras indican coherencia técnica, no calidad.
El informe lleva solo cifras y conteos, nunca textos, y se escribe en
`<salida>/<version>-preliminar.json`; nunca en las carpetas de los modelos.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from app.agentes.facultades import cargar_catalogo, normalizar
from app.razonador import RazonadorInvalido
from ciencia_datos import consola_utf8
from ciencia_datos.corpus import fragmentos, leer_carpeta
from ciencia_datos.entrenar import RAIZ, codigo_a_facultad
from ciencia_datos.estadistica import _l2, _silueta
from ciencia_datos.evaluar import EntradaInvalida, vectores

K = 5
SEMILLA = 42
ADVERTENCIA = (
    "Los textos los redactó Qwen a partir de la carrera: estas medidas indican coherencia técnica, "
    "no calidad. La aprobación exige sílabos reales y etiquetas docentes."
)


# --- medidas ------------------------------------------------------------------------


def _precisiones(X, etiquetas, silabos, k: int) -> np.ndarray:
    """Por fragmento, la parte de sus k vecinos (coseno, de otros sílabos) con su misma etiqueta; nan si no hay."""
    X = _l2(np.asarray(X, dtype=float))
    etiquetas = np.asarray(etiquetas)
    silabos = np.asarray(silabos)
    sim = X @ X.T
    sim[silabos[:, None] == silabos[None, :]] = -np.inf
    salida = np.full(len(X), np.nan)
    for i in range(len(X)):
        fila = sim[i]
        validos = int(np.isfinite(fila).sum())
        if not validos:
            continue
        vecinos = np.argsort(-fila, kind="stable")[: min(k, validos)]
        salida[i] = float(np.mean(etiquetas[vecinos] == etiquetas[i]))
    return salida


def _media(valores: np.ndarray) -> float | None:
    validos = valores[~np.isnan(valores)]
    return float(validos.mean()) if len(validos) else None


def precision_k(vectores, etiquetas, silabos, k: int = K) -> float | None:
    """Precisión media de los k vecinos más cercanos de otros sílabos; None si ningún fragmento los tiene."""
    return _media(_precisiones(vectores, etiquetas, silabos, k))


def _silueta_o_none(X, etiquetas) -> float | None:
    etiquetas = np.asarray(etiquetas)
    if len(set(etiquetas.tolist())) < 2 or len(set(etiquetas.tolist())) >= len(etiquetas):
        return None
    valor = _silueta(_l2(np.asarray(X, dtype=float)), etiquetas)
    return None if np.isnan(valor) else float(valor)


def _control_real(Xr, fac_real, Xp, fac_prueba, k: int = K) -> dict:
    """Cada fragmento real busca sus k vecinos entre los de la prueba simulada; cuenta los de su facultad."""
    fac_prueba = np.asarray(fac_prueba)
    sim = _l2(np.asarray(Xr, dtype=float)) @ _l2(np.asarray(Xp, dtype=float)).T
    valores = []
    for i, fac in enumerate(fac_real):
        if fac not in set(fac_prueba.tolist()):
            continue
        vecinos = np.argsort(-sim[i], kind="stable")[:k]
        valores.append(float(np.mean(fac_prueba[vecinos] == fac)))
    return {
        "n_fragmentos": len(fac_real),
        "n_contados": len(valores),
        "precision_5_facultad": float(np.mean(valores)) if valores else None,
    }


def _medir(X, textos_marca: dict, k: int = K) -> dict:
    """Todas las medidas de un modelo; `textos_marca` trae etiquetas por fragmento (sin texto), prueba primero."""
    n_p = textos_marca["n_prueba"]
    todas = np.asarray(textos_marca["facultad"])
    # Las cifras globales usan solo la prueba simulada; los reales entran únicamente en `control_real`.
    Xr, X = X[n_p:], X[:n_p]
    carrera, facultad, silabo = textos_marca["carrera"][:n_p], todas[:n_p], textos_marca["silabo"][:n_p]
    prec_fac = _precisiones(X, facultad, silabo, k)
    prec_car = _precisiones(X, carrera, silabo, k)
    por_facultad = {}
    for f in sorted(set(facultad.tolist())):
        idx = facultad == f
        por_facultad[f] = {
            "n_fragmentos": int(idx.sum()),
            "precision_5_carrera": _media(prec_car[idx]),
            "precision_5_facultad": _media(prec_fac[idx]),
        }
    barajada = np.random.default_rng(SEMILLA).permutation(facultad)
    return {
        "precision_5_carrera": _media(prec_car),
        "precision_5_facultad": _media(prec_fac),
        "silueta_facultad": _silueta_o_none(X, facultad),
        "silueta_facultad_barajada": _silueta_o_none(X, barajada),
        "por_facultad": por_facultad,
        "control_real": _control_real(
            Xr, todas[n_p:], X, facultad, k
        ),
    }


# --- validación y ejecución ---------------------------------------------------------


def _meta(carpeta: Path) -> dict:
    ruta = Path(carpeta) / "metadatos.json"
    if not ruta.is_file():
        raise EntradaInvalida("un modelo no tiene metadatos.json")
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise EntradaInvalida("metadatos.json no es JSON válido") from None


def _validar(modelo: Path, base_modelo: Path, meta: dict, base: dict, salida: Path, codigos: set[str]) -> None:
    if meta.get("preliminar") is not True or base.get("preliminar") is not True:
        raise EntradaInvalida("el modelo y el base deben ser preliminares (preliminar: true)")
    if base.get("ajuste") is not False:
        raise EntradaInvalida("el modelo base debe ser el exportado con --sin-ajuste (ajuste: false)")
    if not meta.get("huella_separacion") or meta.get("huella_separacion") != base.get("huella_separacion"):
        raise EntradaInvalida("el modelo y el base deben tener la misma huella de separación")
    for carpeta in (modelo, base_modelo):
        if Path(salida).resolve().is_relative_to(Path(carpeta).resolve()):
            raise EntradaInvalida("la salida no puede estar dentro de la carpeta de un modelo")
    sep = meta.get("separacion") or {}
    for clave in ("prueba", "control_real"):
        faltan = [c for c in sep.get(clave, []) if c not in codigos]
        if faltan:
            raise EntradaInvalida(f"{len(faltan)} códigos de {clave} no están entre los sílabos leídos")
    if not sep.get("prueba"):
        raise EntradaInvalida("la separación del modelo no trae sílabos de prueba")


def ejecutar_preliminar(
    modelo: Path, base_modelo: Path, silabos: list[Path], salida: Path, vectorizar=vectores
) -> dict:
    """Escribe `<salida>/<version>-preliminar.json` con las medidas de ambos modelos y lo devuelve."""
    modelo, base_modelo, salida = Path(modelo), Path(base_modelo), Path(salida)
    meta, base = _meta(modelo), _meta(base_modelo)
    leidos, _ = leer_carpeta(list(silabos))
    por_codigo = {s.proyecto_formativo.codigo: s for s in leidos}
    _validar(modelo, base_modelo, meta, base, salida, set(por_codigo))

    catalogo = cargar_catalogo(RAIZ / "kb" / "catalogo.yaml")
    mapa, _ = codigo_a_facultad(leidos, catalogo)
    sep = meta["separacion"]
    prueba, control = sep["prueba"], sep.get("control_real", [])
    if sum(normalizar(por_codigo[c].facultad) not in catalogo for c in [*prueba, *control]):
        raise EntradaInvalida("hay sílabos de prueba o de control cuya facultad no está en el catálogo")

    textos: list[str] = []
    marca = {"carrera": [], "facultad": [], "silabo": []}
    for codigo in [*prueba, *control]:
        for f in fragmentos(por_codigo[codigo]):
            textos.append(f.texto)
            marca["carrera"].append(f"{mapa[codigo]}/{f.carrera}")
            marca["facultad"].append(mapa[codigo])
            marca["silabo"].append(codigo)
    marca["n_prueba"] = sum(len(fragmentos(por_codigo[c])) for c in prueba)
    marca["facultad"] = np.asarray(marca["facultad"])
    if not textos:
        raise EntradaInvalida("los sílabos medidos no tienen fragmentos")

    candidatos = {}
    for nombre, carpeta in (("ajustado", modelo), ("base", base_modelo)):
        X = np.asarray(vectorizar(carpeta, textos), dtype=float)
        candidatos[nombre] = _medir(X, marca)

    version = meta.get("version") or modelo.name
    informe = {
        "version": version,
        "version_base": base.get("version") or base_modelo.name,
        "huella_separacion": meta["huella_separacion"],
        "apto_produccion": False,
        "advertencia": ADVERTENCIA,
        "n_silabos_prueba": len(prueba),
        "n_fragmentos_prueba": marca["n_prueba"],
        "n_control_real": len(control),
        "n_fragmentos_control_real": len(textos) - marca["n_prueba"],
        "k": K,
        "semilla_barajado": SEMILLA,
        "candidatos": candidatos,
    }
    salida.mkdir(parents=True, exist_ok=True)
    ruta = salida / f"{version}-preliminar.json"
    ruta.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**informe, "ruta": str(ruta)}


def _cifra(x) -> str:
    return "null" if x is None else f"{x:.3f}"


def main(argv: list[str] | None = None) -> int:
    consola_utf8()
    p = argparse.ArgumentParser(prog="python -m ciencia_datos.preliminar")
    p.add_argument("--modelo", type=Path, required=True, help="modelo preliminar ajustado")
    p.add_argument("--base-modelo", type=Path, required=True, help="modelo base exportado con --sin-ajuste")
    p.add_argument("--silabos", type=Path, nargs="+", required=True, help="una o varias carpetas")
    p.add_argument("--salida", type=Path, required=True)
    a = p.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        r = ejecutar_preliminar(a.modelo, a.base_modelo, a.silabos, a.salida)
    except (EntradaInvalida, RazonadorInvalido) as e:
        print(f"entrada inválida: {e}")
        return 2
    for nombre, c in r["candidatos"].items():
        print(
            f"{nombre}: precision_5_carrera={_cifra(c['precision_5_carrera'])} "
            f"precision_5_facultad={_cifra(c['precision_5_facultad'])} "
            f"silueta_facultad={_cifra(c['silueta_facultad'])} "
            f"silueta_barajada={_cifra(c['silueta_facultad_barajada'])} "
            f"control_real_facultad={_cifra(c['control_real']['precision_5_facultad'])}"
        )
    print(f"n_control_real={r['n_control_real']} apto_produccion=False informe={r['ruta']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
