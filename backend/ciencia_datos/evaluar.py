"""Evaluación del codificador con el 30 % reservado, una sola vez por versión.

Compara el filtro por palabras actual (`_casos_libres`), TF-IDF, el modelo base y el
ajustado. El umbral se elige solo con el 70 % y se evalúa en el 30 %. Los informes
contienen cifras y huellas, nunca textos. Las métricas indefinidas se escriben como
`null` y nunca cumplen un criterio.

Flujo con docentes:
1. `temas-para-revisar` agrupa los fragmentos de prueba y escribe `huella_temas,grupo,texto`,
   más una plantilla por grupo para llenar.
2. Los docentes juzgan cada grupo en `temas.csv` (`huella_temas,grupo,docente,tiene_sentido`).
3. `evaluar` solo puntúa las filas con la huella del modelo elegido.
Hasta correr la evaluación no se sabe cuál de los dos candidatos (ajustado o base) gana: los
docentes deben juzgar los temas de AMBOS, ejecutando `temas-para-revisar` sobre cada carpeta.
Si faltan grupos de alguno, la evaluación no empieza.

El candado de «una sola vez» es `evaluacion.candado` dentro de la carpeta de cada modelo, y
también cuenta un informe `<version>.json` ya escrito. `--salida` solo decide dónde se escribe
el informe. Todo error recuperable sale antes del candado y sin calcular ninguna métrica.

Los vectores salen de `app.razonador` (el mismo código que sirve en producción) mediante
`vectores`, que las pruebas reemplazan por vectores fijos.
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

from app.agentes.facultades import cargar_catalogo
from app.agentes.planificador import _casos_libres
from app.razonador import Razonador, RazonadorInvalido, _leer_metadatos, huella_pesos
from ciencia_datos import consola_utf8
from ciencia_datos.corpus import fragmentos, leer_carpeta
from ciencia_datos.entrenar import CANDADO, RAIZ, codigo_a_facultad, huella
from ciencia_datos.estadistica import (  # noqa: F401  (se reexportan: siguen importables desde aquí)
    EXHAUSTIVIDAD_UMBRAL, agrupar, cumple, elegir_umbral, estabilidad, kappa, mcnemar,
    mcnemar_conteos, metricas, silueta_frente_al_azar, wilson,
)
from ciencia_datos.origen import es_simulado
from ciencia_datos.separar import dejar_fuera

EXHAUSTIVIDAD_MINIMA = 0.85  # exigida en el 30 %
ALFA = 0.05
ARI_MINIMO = 0.80
SENTIDO_MINIMO = 0.80
KAPPA_MINIMO = 0.60
MIN_PARES_KAPPA = 100
MIN_POSITIVOS_PRUEBA = 60
K_POR_OMISION = 8
SEMILLA = 42
SALIDA_POR_DEFECTO = RAIZ / "pruebas" / "ciencia_datos"
CABECERA_PARES = ("caso", "evidencia", "codigo_pf", "docente", "parecido")
CABECERA_TEMAS = ("huella_temas", "grupo", "docente", "tiene_sentido")
_SI = {"1", "si", "sí", "true", "verdadero", "s", "x", "yes"}
_NO = {"0", "no", "false", "falso", "n"}


class YaEvaluada(Exception):
    """El modelo ya tiene su evaluación real: el 30 % no se evalúa dos veces."""


class EntradaInvalida(ValueError):
    """Argumentos o archivos que impiden evaluar; se detecta antes de tomar candados."""


def dictaminar(medidas: dict) -> dict:
    """Aprobado solo si cumple todos los criterios; una medida ausente o NaN nunca cumple."""
    g = medidas.get
    p, a_favor, en_contra = g("mcnemar_p"), g("solo_modelo"), g("solo_filtro")
    silueta, p95 = g("silueta"), g("silueta_p95")
    criterios = {
        "exhaustividad": cumple(g("exhaustividad"), EXHAUSTIVIDAD_MINIMA),
        # Significativo Y a favor del modelo: un modelo peor que el filtro también da p pequeño.
        "mcnemar": p is not None and p < ALFA and a_favor is not None and en_contra is not None and a_favor > en_contra,
        "silueta": silueta is not None and p95 is not None and not math.isnan(silueta + p95) and silueta > p95,
        "estabilidad": cumple(g("ari"), ARI_MINIMO),
        "grupos_con_sentido": cumple(g("grupos_con_sentido"), SENTIDO_MINIMO),
        "kappa": cumple(g("kappa"), KAPPA_MINIMO),
        "muestra_kappa": cumple(g("pares_para_kappa"), MIN_PARES_KAPPA),
        "muestra_positivos": cumple(g("positivos_prueba"), MIN_POSITIVOS_PRUEBA),
    }
    return {"aprobado": all(criterios.values()), "criterios": criterios}


# --- vectores -----------------------------------------------------------------------


def vectores(carpeta: Path, textos: list[str]) -> np.ndarray:
    """Vectores de `textos` con el mismo código que sirve en producción (`app.razonador`)."""
    return Razonador.cargar(Path(carpeta), exigir_aprobado=False).vectores(textos)


# --- etiquetas ----------------------------------------------------------------------


def _valor(texto: str) -> int | None:
    t = (texto or "").strip().lower()
    return 1 if t in _SI else 0 if t in _NO else None


def _leer_csv(ruta: Path, requeridas: tuple[str, ...] = ()) -> list[dict]:
    """Filas del CSV, con o sin BOM y con `,` o `;` (Excel según la región).

    Con `requeridas`, exige las columnas y rechaza filas cortas o con sobrantes.
    """
    try:
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            cabecera = f.readline()
            f.seek(0)
            lector = csv.DictReader(f, delimiter=";" if cabecera.count(";") > cabecera.count(",") else ",")
            falta = [c for c in requeridas if c not in (lector.fieldnames or [])]
            if falta:
                raise EntradaInvalida(f"{ruta.name}: faltan columnas {', '.join(falta)}")
            filas = list(lector)
    except (UnicodeDecodeError, csv.Error):
        raise EntradaInvalida(f"{ruta.name}: no se puede leer; guárdelo como CSV UTF-8") from None
    for n, fila in enumerate(filas, start=2):
        if None in fila or any(fila.get(c) is None for c in requeridas):
            raise EntradaInvalida(f"{ruta.name}: la fila {n} está incompleta o tiene columnas de más")
    return filas


def cargar_pares(ruta: Path, entrenamiento: list[str], prueba: list[str]) -> dict:
    """Pares únicos (caso, evidencia) con su grupo, código y etiqueta; solo conteos de lo descartado.

    Un par con docentes en desacuerdo (o en grupos distintos) queda fuera de umbral y métricas
    y se cuenta. El kappa usa los dos docentes con más pares y los pares que ambos etiquetaron.
    """
    grupo_de = {c: "entrenamiento" for c in entrenamiento} | {c: "prueba" for c in prueba}
    filas = _leer_csv(ruta, CABECERA_PARES)
    por_par: dict[tuple[str, str], list[tuple[str, str, str, int]]] = {}
    fuera_de_grupo = valor_invalido = 0
    for f in filas:
        codigo = (f.get("codigo_pf") or "").strip()
        grupo, valor = grupo_de.get(codigo), _valor(f.get("parecido", ""))
        if grupo is None:
            fuera_de_grupo += 1
        elif valor is None:
            valor_invalido += 1
        else:
            por_par.setdefault((f["caso"], f["evidencia"]), []).append((f["docente"].strip(), grupo, codigo, valor))
    pares, desacuerdos, grupo_ambiguo = [], 0, 0
    for (caso, evidencia), votos in por_par.items():
        if len({g for _, g, _, _ in votos}) > 1:
            grupo_ambiguo += 1
        elif len({v for _, _, _, v in votos}) > 1:
            desacuerdos += 1
        else:
            pares.append({"caso": caso, "evidencia": evidencia, "grupo": votos[0][1],
                          "codigo": sorted({c for _, _, c, _ in votos})[0], "etiqueta": votos[0][3]})
    cuenta: dict[str, int] = {}
    for votos in por_par.values():
        for d in {d for d, _, _, _ in votos}:
            cuenta[d] = cuenta.get(d, 0) + 1
    docentes = [d for d, _ in sorted(cuenta.items(), key=lambda x: (-x[1], x[0]))[:2]]
    a, b = [], []
    if len(docentes) == 2:
        for votos in por_par.values():
            por_docente: dict[str, set] = {}
            for d, _, _, v in votos:
                por_docente.setdefault(d, set()).add(v)
            if all(len(por_docente.get(d, ())) == 1 for d in docentes):
                a.append(next(iter(por_docente[docentes[0]])))
                b.append(next(iter(por_docente[docentes[1]])))
    return {
        "pares": pares,
        "filas": len(filas),
        "filas_fuera_de_grupo": fuera_de_grupo,
        "filas_valor_invalido": valor_invalido,
        "pares_grupo_ambiguo": grupo_ambiguo,
        "pares_en_desacuerdo": desacuerdos,
        "pares_para_kappa": len(a),
        "kappa": kappa(a, b) if a else math.nan,
    }


def grupos_con_sentido(ruta: Path, huella_temas: str, esperados: set[str]) -> dict:
    """Fracción de grupos que la mayoría estricta de docentes juzga con sentido.

    Solo cuentan las filas con la huella del modelo. Si falta algún grupo esperado o sobra
    alguno, la fracción es NaN (y no se aprueba).
    """
    votos: dict[str, list[int]] = {}
    for f in _leer_csv(ruta, CABECERA_TEMAS):
        v = _valor(f.get("tiene_sentido", ""))
        if (f.get("huella_temas") or "").strip() == huella_temas and v is not None and (f.get("grupo") or "").strip():
            votos.setdefault(f["grupo"].strip(), []).append(v)
    if not votos or set(votos) != set(esperados):
        return {"n_grupos": len(votos), "fraccion": math.nan}
    con = sum(1 for v in votos.values() if sum(v) * 2 > len(v))
    return {"n_grupos": len(votos), "fraccion": con / len(votos)}


# --- temas --------------------------------------------------------------------------


def _textos_de_prueba(lista, prueba) -> list[str]:
    codigos = set(prueba)
    return sorted({f.texto for s in lista if s.proyecto_formativo.codigo in codigos for f in fragmentos(s)})


def asignar_temas(X, k: int, version: str) -> tuple[np.ndarray, int, str] | None:
    """Etiquetas de k-medias (semilla 42), k usado y huella (SHA-256 de la asignación y la versión)."""
    k_usado = min(k, len(X) - 1)
    if k_usado < 2:
        return None
    etiquetas = agrupar(np.asarray(X, float), k_usado, SEMILLA)
    clave = f"{version}|{','.join(str(int(e)) for e in etiquetas)}"
    return etiquetas, k_usado, hashlib.sha256(clave.encode()).hexdigest()


def temas_para_revisar(modelo: Path, silabos: Path, salida: Path, *, k: int = K_POR_OMISION, vectorizar=vectores) -> dict:
    """Escribe `huella_temas,grupo,texto` para que los docentes juzguen cada grupo.

    Junto a `salida` deja `temas-plantilla-<version>.csv`, una fila por grupo con las columnas
    de `temas.csv` y `docente` y `tiene_sentido` vacías. Los dos archivos van en `utf-8-sig`
    para que Excel lea los acentos. No imprime textos, no calcula métricas y no toma el candado.
    """
    meta = _meta(modelo)
    lista, _ = leer_carpeta(Path(silabos))
    textos = _textos_de_prueba(lista, _separacion(meta)["prueba"])
    asignacion = asignar_temas(vectorizar(Path(modelo), textos), k, meta["version"]) if len(textos) > 2 else None
    if asignacion is None:
        raise EntradaInvalida("muy pocos textos de prueba para agrupar")
    etiquetas, k_usado, h = asignacion
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["huella_temas", "grupo", "texto"])
        w.writerows((h, int(g), t) for g, t in zip(etiquetas, textos))
    plantilla = salida.parent / f"temas-plantilla-{meta['version']}.csv"
    with open(plantilla, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(CABECERA_TEMAS)
        w.writerows((h, g, "", "") for g in range(k_usado))
    return {"huella": h, "k": k_usado, "k_reducido": k_usado < k, "n_textos": len(textos), "plantilla": str(plantilla)}


def _temas(X, k: int, version: str) -> dict:
    asignacion = asignar_temas(X, k, version) if len(X) > 2 else None
    if asignacion is None:
        return {"k": 0, "k_reducido": True, "silueta": math.nan, "silueta_p95": math.nan, "ari": math.nan, "huella_temas": None}
    _, k_usado, h = asignacion
    s = silueta_frente_al_azar(X, k_usado)
    return {"k": k_usado, "k_reducido": k_usado < k, "silueta": s["real"], "silueta_p95": s["p95"],
            "silueta_media_azar": s["media_azar"], "ari": estabilidad(X, k_usado), "huella_temas": h}


# --- medición por modelo --------------------------------------------------------------


def _coseno(vec: dict[str, np.ndarray], pares: list[dict]) -> np.ndarray:
    return np.array([float(vec[p["caso"]] @ vec[p["evidencia"]]) for p in pares])


def _tfidf(pares_ent: list[dict], pares_pru: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    from sklearn.feature_extraction.text import TfidfVectorizer

    v = TfidfVectorizer().fit([t for p in pares_ent for t in (p["caso"], p["evidencia"])])

    def sims(pares):
        A, B = v.transform([p["caso"] for p in pares]), v.transform([p["evidencia"] for p in pares])
        return np.asarray(A.multiply(B).sum(axis=1)).ravel()

    return sims(pares_ent), sims(pares_pru)


def medir_puntaje(sim_ent, y_ent, sim_pru, y_pru) -> dict:
    """Umbral con el 70 % y métricas en el 30 % (con Wilson para la exhaustividad)."""
    y_ent, y_pru = np.asarray(y_ent, bool), np.asarray(y_pru, bool)
    try:
        umbral = elegir_umbral(sim_ent, y_ent)
    except ValueError:
        return {"umbral": None, "precision": None, "exhaustividad": None, "f1": None, "pred": None}
    pred = np.asarray(sim_pru) >= umbral
    lo, hi = wilson(int((pred & y_pru).sum()), int(y_pru.sum()))
    return {"umbral": float(umbral), **metricas(pred, y_pru), "exhaustividad_ic95": [lo, hi], "pred": pred}


def dejar_fuera_pares(sim, y, codigos, plan, exhaustividad_min: float = EXHAUSTIVIDAD_UMBRAL) -> dict:
    """Por pliegue de `separar.dejar_fuera`: umbral con los pares de las otras facultades, métricas en la dejada fuera.

    `codigos[i]` es el sílabo del par i. Una facultad sin positivos (en ella o en las demás) se
    lista en `excluidas`. La peor es la de menor F1; un F1 de 0 cuenta.
    """
    sim, y, codigos = np.asarray(sim, float), np.asarray(y, bool), np.asarray(codigos, dtype=object)
    por_facultad, excluidas = {}, []
    for facultad, sep in plan.items():
        dentro = np.isin(codigos, list(sep.prueba))
        resto = np.isin(codigos, list(sep.entrenamiento))
        try:
            t = elegir_umbral(sim[resto], y[resto], exhaustividad_min)
        except ValueError:
            t = None
        m = metricas(sim[dentro] >= t, y[dentro]) if t is not None else None
        if m is None or math.isnan(m["f1"]):
            excluidas.append(facultad)
            continue
        por_facultad[facultad] = {"n": int(dentro.sum()), "umbral": t, **m}
    peor = min(por_facultad, key=lambda f: por_facultad[f]["f1"]) if por_facultad else None
    return {"por_facultad": por_facultad, "peor": peor,
            "peor_f1": por_facultad[peor]["f1"] if peor else None, "excluidas": sorted(excluidas)}


def _evaluar_modelo(carpeta: Path, ent: list[dict], pru: list[dict], vectorizar) -> dict:
    textos = sorted({t for p in ent + pru for t in (p["caso"], p["evidencia"])})
    vec = dict(zip(textos, vectorizar(carpeta, textos)))
    y_ent, y_pru = [p["etiqueta"] for p in ent], [p["etiqueta"] for p in pru]
    return medir_puntaje(_coseno(vec, ent), y_ent, _coseno(vec, pru), y_pru) | {"_vec": vec}


# --- informes y candado ---------------------------------------------------------------


def _limpio(x):
    """Cifras para JSON: floats de Python, NaN o infinito como null."""
    if isinstance(x, dict):
        return {k: _limpio(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [_limpio(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(x) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def escribir_informe(informe: dict, salida: Path, version: str, humo: bool, completo: bool = True) -> Path:
    """`<version>.json`, `<version>-humo.json` o `<version>-incompleta.json`. No es el candado."""
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    destino = salida / f"{version}{'-humo' if humo else '' if completo else '-incompleta'}.json"
    destino.write_text(json.dumps(_limpio(informe), ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def _tomar_candados(carpetas: list[Path]) -> None:
    """Crea `evaluacion.candado` en cada carpeta (modo exclusivo); si alguno existe, no deja ninguno nuevo."""
    creados: list[Path] = []
    try:
        for c in carpetas:
            ruta = Path(c) / CANDADO
            try:
                with open(ruta, "x", encoding="utf-8") as f:
                    f.write("evaluada\n")
            except FileExistsError:
                raise YaEvaluada(str(c)) from None
            creados.append(ruta)
    except YaEvaluada:
        for ruta in creados:
            ruta.unlink(missing_ok=True)
        raise


def _meta(carpeta: Path) -> dict:
    return _leer_metadatos(Path(carpeta))


def _separacion(meta: dict) -> dict:
    sep = meta.get("separacion")
    if not isinstance(sep, dict) or "prueba" not in sep or "entrenamiento" not in sep:
        raise EntradaInvalida("metadatos.json no trae la separación")
    return sep


def _validar_entradas(modelo: Path, base_modelo: Path | None, meta: dict, silabos: Path, salida: Path, k: int) -> None:
    """Todo lo que puede fallar por argumentos va antes del candado: un error no quema la evaluación."""
    if not silabos.is_dir():
        raise EntradaInvalida("--silabos no es una carpeta existente")
    if k < 2:
        raise EntradaInvalida("--k debe ser al menos 2")
    if salida.exists() and not salida.is_dir():
        raise EntradaInvalida("--salida existe y no es una carpeta")
    try:
        salida.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise EntradaInvalida("--salida no se puede crear") from None
    if not (modelo / "onnx" / "model.onnx").is_file():
        raise EntradaInvalida("el modelo no tiene onnx/model.onnx")
    if meta.get("humo"):
        return  # el humo no compara con un base
    if meta.get("ajuste") is False:
        if base_modelo is not None:
            raise EntradaInvalida("--base-modelo sobra: el modelo ya es un base")
        return
    if base_modelo is None:
        raise EntradaInvalida("un modelo ajustado exige --base-modelo para decidir")
    base_modelo = Path(base_modelo)
    if not (base_modelo / "onnx" / "model.onnx").is_file():
        raise EntradaInvalida("el base no tiene onnx/model.onnx")
    mb = _meta(base_modelo)
    if (mb.get("ajuste") is not False or mb.get("humo") or mb.get("huella_separacion") != meta.get("huella_separacion")
            or mb.get("base") != meta.get("base")):
        raise EntradaInvalida("--base-modelo no es un base válido: exige ajuste false, humo false, "
                              "la misma separación y el mismo modelo base que el ajustado")


def _rechazar_si_ya_evaluada(carpetas: list[Path], salida: Path) -> None:
    """Una versión se evalúa una vez: cuenta el candado y también el informe de otra carpeta con su nombre."""
    for c in carpetas:
        if (c / CANDADO).exists():
            raise YaEvaluada(str(c))
        version = _meta(c)["version"]
        if any((d / f"{version}.json").exists() for d in (salida, SALIDA_POR_DEFECTO)):
            raise YaEvaluada(f"ya existe el informe de la versión {version}")


def _comprobar_temas(temas_csv: Path, carpetas: list[Path], textos: list[str], k: int, vectorizar) -> None:
    """`temas.csv` trae, para cada candidato, su huella y exactamente sus grupos, sin celdas vacías."""
    filas = _leer_csv(temas_csv, CABECERA_TEMAS)
    for n, f in enumerate(filas, start=2):
        if not f["docente"].strip() or not f["tiene_sentido"].strip():
            raise EntradaInvalida(f"{temas_csv.name}: la fila {n} tiene docente o tiene_sentido vacíos")
    for c in carpetas:
        asignacion = asignar_temas(vectorizar(c, textos), k, _meta(c)["version"]) if len(textos) > 2 else None
        if asignacion is None:
            raise EntradaInvalida("muy pocos textos de prueba para agrupar")
        _, k_usado, h = asignacion
        juzgados = {f["grupo"].strip() for f in filas
                    if f["huella_temas"].strip() == h and _valor(f["tiene_sentido"]) is not None}
        if juzgados != {str(i) for i in range(k_usado)}:
            raise EntradaInvalida(f"{temas_csv.name}: faltan o sobran grupos de {c.name} ({len(juzgados)} de {k_usado}); "
                                  "revise que venga su plantilla y que --k sea el de temas-para-revisar")


def _comprobar_antes_del_candado(carpetas: list[Path], meta: dict, silabos: Path, pares_csv: Path, temas_csv: Path,
                                 k: int, vectorizar, abrir_modelo) -> tuple[list, dict]:
    """Todo error recuperable sale aquí, sin calcular métricas. Devuelve los sílabos y las etiquetas leídas."""
    for c in carpetas:
        abrir_modelo(c)
    sep = _separacion(meta)
    if huella(sep) != meta.get("huella_separacion"):
        raise EntradaInvalida("huella_separacion no coincide con la separación guardada")
    lista, _ = leer_carpeta(silabos)
    faltan = len(set(sep["prueba"]) - {s.proyecto_formativo.codigo for s in lista})
    if faltan:
        raise EntradaInvalida(f"sílabo de prueba ausente: faltan {faltan}")
    cp = cargar_pares(pares_csv, sep["entrenamiento"], sep["prueba"])
    positivos = sum(p["etiqueta"] for p in cp["pares"] if p["grupo"] == "prueba")
    if positivos < MIN_POSITIVOS_PRUEBA:
        raise EntradaInvalida(f"{pares_csv.name}: {positivos} positivos en el grupo de prueba tras quitar desacuerdos; "
                              f"se exigen {MIN_POSITIVOS_PRUEBA}")
    if cp["pares_para_kappa"] < MIN_PARES_KAPPA:
        raise EntradaInvalida(f"{pares_csv.name}: {cp['pares_para_kappa']} pares comunes entre dos docentes; "
                              f"se exigen {MIN_PARES_KAPPA}")
    _comprobar_temas(temas_csv, carpetas, _textos_de_prueba(lista, sep["prueba"]), k, vectorizar)
    return lista, cp


def _abrir_modelo(carpeta: Path) -> None:
    Razonador.cargar(Path(carpeta), exigir_aprobado=False)


def ejecutar(
    modelo: Path,
    silabos: Path,
    *,
    base_modelo: Path | None = None,
    datos: Path = RAIZ / "datos_cd",
    salida: Path = SALIDA_POR_DEFECTO,
    humo: bool = False,
    k: int = K_POR_OMISION,
    vectorizar=vectores,
    abrir_modelo=_abrir_modelo,
) -> dict:
    """Evalúa `modelo` y escribe el informe. Lanza `YaEvaluada` si el modelo ya se evaluó, y
    `EntradaInvalida` o `RazonadorInvalido` (antes de tomar candados) si la evaluación no puede salir bien."""
    modelo, salida, datos = Path(modelo), Path(salida), Path(datos)
    meta = _meta(modelo)
    version = meta["version"]
    if meta.get("preliminar") is True and not humo:
        raise EntradaInvalida("el modelo es preliminar (entrenado con sílabos simulados): solo se evalúa con --humo")
    if not humo:
        sep_meta = meta.get("separacion")
        codigos = [c for clave in ("entrenamiento", "prueba") if isinstance(sep_meta, dict)
                   and isinstance(sep_meta.get(clave), list) for c in sep_meta[clave] if isinstance(c, str)]
        origen = meta.get("origen")
        n_sim = origen.get("simulados") if isinstance(origen, dict) else 0
        if any(es_simulado(c) for c in codigos) or (isinstance(n_sim, int) and n_sim > 0):
            raise EntradaInvalida("el modelo usa sílabos simulados: solo se evalúa con --humo")
    if humo and not meta.get("humo"):
        raise EntradaInvalida("--humo solo se acepta sobre un modelo con humo: true")
    if meta.get("humo") and not humo:
        raise EntradaInvalida("el modelo tiene humo: true: solo se evalúa con --humo")
    _validar_entradas(modelo, base_modelo, meta, Path(silabos), salida, k)
    base_modelo = Path(base_modelo) if base_modelo is not None else None
    sep = _separacion(meta)
    informe = {"version": version, "humo": humo, "aprobado": False,
               "huella_separacion": meta.get("huella_separacion"), "huella_modelo": huella_pesos(modelo)}

    if humo:
        lista, _ = leer_carpeta(Path(silabos))
        textos = _textos_de_prueba(lista, sep["prueba"])
        informe |= {"n_silabos_prueba": len({s.proyecto_formativo.codigo for s in lista} & set(sep["prueba"])),
                    "temas": _temas(vectorizar(modelo, textos), k, version) if len(textos) > 2 else {}}
        informe["ruta"] = str(escribir_informe(informe, salida, version, True))
        return informe

    carpetas = [modelo] + ([base_modelo] if base_modelo else [])
    _rechazar_si_ya_evaluada(carpetas, salida)
    pares_csv, temas_csv = datos / "pares.csv", datos / "temas.csv"
    for r, cab in ((pares_csv, CABECERA_PARES), (temas_csv, CABECERA_TEMAS)):
        if r.exists():
            _leer_csv(r, cab)  # completo y bien formado, antes del candado
    faltan = [r.name for r in (pares_csv, temas_csv) if not r.exists()]
    if faltan:
        informe |= {"motivo": "faltan archivos de etiquetas: " + ", ".join(faltan)}
        informe["ruta"] = str(escribir_informe(informe, salida, version, False, completo=False))
        return informe

    lista, cp = _comprobar_antes_del_candado(carpetas, meta, Path(silabos), pares_csv, temas_csv, k, vectorizar, abrir_modelo)

    _tomar_candados(carpetas)

    n_prueba = len({s.proyecto_formativo.codigo for s in lista} & set(sep["prueba"]))
    ent = [p for p in cp["pares"] if p["grupo"] == "entrenamiento"]
    pru = [p for p in cp["pares"] if p["grupo"] == "prueba"]
    y_pru = np.array([p["etiqueta"] for p in pru], bool)

    propio = _evaluar_modelo(modelo, ent, pru, vectorizar)
    candidatos, nota = {}, None
    if meta.get("ajuste") is False:
        candidatos["base"] = propio
        nombre, carpeta_elegida = "base", modelo
    else:
        candidatos["ajustado"] = propio
        nombre, carpeta_elegida = "ajustado", modelo
        if base_modelo is None:
            nota = "sin modelo base para comparar: no se puede decidir"
        else:
            candidatos["base"] = _evaluar_modelo(base_modelo, ent, pru, vectorizar)
            fa, fb = propio["f1"], candidatos["base"]["f1"]
            if not (fa is not None and not math.isnan(fa) and (fb is None or math.isnan(fb) or fa > fb)):
                nombre, carpeta_elegida = "base", base_modelo
                nota = "el ajustado no supera al base en F1: se usa el base"
    elegido = candidatos[nombre]

    ok = (elegido["pred"] == y_pru) if elegido["pred"] is not None else None
    palabras = np.array([p["caso"] not in _casos_libres([p["caso"]], [p["evidencia"]]) for p in pru], bool)
    solo_modelo, solo_filtro = mcnemar_conteos(ok, palabras == y_pru) if ok is not None else (None, None)
    p_mc = mcnemar(ok, palabras == y_pru) if ok is not None and len(pru) else None
    tf_ent, tf_pru = _tfidf(ent, pru) if ent and pru else (np.zeros(0), np.zeros(0))
    tfidf = medir_puntaje(tf_ent, [p["etiqueta"] for p in ent], tf_pru, y_pru) if ent and pru else None

    # Generalización: siempre con el modelo base, que nunca vio estos sílabos.
    catalogo = cargar_catalogo(RAIZ / "kb" / "catalogo.yaml")
    mapa, _ = codigo_a_facultad(lista, catalogo)
    todos = ent + pru
    vec_base = candidatos["base"]["_vec"] if "base" in candidatos else None
    if vec_base is not None and todos:
        con_facultad = [p for p in todos if p["codigo"] in mapa]
        fuera = dejar_fuera_pares(_coseno(vec_base, con_facultad), [p["etiqueta"] for p in con_facultad],
                                  [p["codigo"] for p in con_facultad], dejar_fuera(mapa))
        fuera |= {"codificador": "base", "pares_sin_facultad": len(todos) - len(con_facultad)}
        if nombre == "ajustado":
            fuera["generalizacion_del_ajustado"] = "no medida"
    else:
        fuera = {"codificador": None, "nota": "sin modelo base para medir"}

    version_elegida = _meta(carpeta_elegida)["version"]
    textos = _textos_de_prueba(lista, sep["prueba"])
    temas = _temas(vectorizar(carpeta_elegida, textos), k, version_elegida) if len(textos) > 2 else {}
    esperados = {str(i) for i in range(temas.get("k", 0))}
    sentido = (grupos_con_sentido(temas_csv, temas["huella_temas"], esperados)
               if temas.get("huella_temas") else {"n_grupos": 0, "fraccion": math.nan})
    medidas = {
        "exhaustividad": elegido["exhaustividad"], "mcnemar_p": p_mc, "solo_modelo": solo_modelo, "solo_filtro": solo_filtro,
        "silueta": temas.get("silueta"), "silueta_p95": temas.get("silueta_p95"), "ari": temas.get("ari"),
        "grupos_con_sentido": sentido["fraccion"], "kappa": cp["kappa"],
        "pares_para_kappa": cp["pares_para_kappa"], "positivos_prueba": int(y_pru.sum()),
    }
    sin_decision = nota is not None and nombre == "ajustado"
    veredicto = dictaminar(medidas)
    aprobado = veredicto["aprobado"] and not sin_decision
    quitar = ("pred", "_vec")
    informe |= {
        "aprobado": aprobado, "criterios": veredicto["criterios"], "medidas": medidas,
        "modelo_elegido": nombre, "version_elegida": version_elegida, "nota_modelo": nota, "umbral": elegido["umbral"],
        "huella_modelo_elegido": huella_pesos(carpeta_elegida), "n_silabos_prueba": n_prueba,
        "n_pares_entrenamiento": len(ent), "n_pares_prueba": len(pru),
        "conteos": {k_: v for k_, v in cp.items() if k_ not in ("pares", "kappa")},
        "candidatos": {n: {k_: v for k_, v in c.items() if k_ not in quitar} for n, c in candidatos.items()},
        "referencias": {
            "tfidf": {k_: v for k_, v in tfidf.items() if k_ != "pred"} if tfidf else None,
            "filtro_palabras": metricas(palabras, y_pru) if len(pru) else None,
        },
        "temas": {k_: v for k_, v in temas.items() if k_ != "huella_temas"} | {"huella_temas": temas.get("huella_temas")},
        "n_grupos_temas": sentido["n_grupos"], "dejar_fuera": fuera,
    }
    informe["ruta"] = str(escribir_informe(informe, salida, version, False))
    informe["carpeta_elegida"] = str(carpeta_elegida)  # Solo para la consola: el informe no lleva rutas.
    if aprobado:
        ruta = carpeta_elegida / "metadatos.json"
        ruta.write_text(json.dumps(_meta(carpeta_elegida) | {"aprobado": True, "umbral": elegido["umbral"],
                                                             "huella_pesos": huella_pesos(carpeta_elegida)},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    return informe


def _main_temas(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="python -m ciencia_datos.evaluar temas-para-revisar",
        description="Escribe los grupos de temas para que los docentes los juzguen. Ejecútelo sobre "
        "AMBOS candidatos (ajustado y base): el ganador se conoce solo al evaluar.",
    )
    p.add_argument("--modelo", type=Path, required=True)
    p.add_argument("--silabos", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True, help="p. ej. datos_cd/temas-revision-<version>.csv")
    p.add_argument("--k", type=int, default=K_POR_OMISION)
    a = p.parse_args(argv)
    try:
        r = temas_para_revisar(a.modelo, a.silabos, a.salida, k=a.k)
    except (EntradaInvalida, RazonadorInvalido) as e:
        print(f"entrada inválida: {e}")
        return 2
    print(f"huella_temas={r['huella']} k={r['k']} k_reducido={r['k_reducido']} textos={r['n_textos']} plantilla={r['plantilla']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    consola_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["temas-para-revisar"]:
        return _main_temas(argv[1:])
    p = argparse.ArgumentParser(prog="python -m ciencia_datos.evaluar")
    p.add_argument("--modelo", type=Path, required=True)
    p.add_argument("--base-modelo", type=Path, help="carpeta ONNX del modelo base (exportado con --sin-ajuste)")
    p.add_argument("--silabos", type=Path, required=True)
    p.add_argument("--datos", type=Path, default=RAIZ / "datos_cd")
    p.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO, help="solo dónde se escribe el informe")
    p.add_argument("--k", type=int, default=K_POR_OMISION, help="número de temas (el mismo que en temas-para-revisar)")
    p.add_argument("--humo", action="store_true")
    a = p.parse_args(argv)
    try:
        r = ejecutar(a.modelo, a.silabos, base_modelo=a.base_modelo, datos=a.datos, salida=a.salida, humo=a.humo, k=a.k)
    except YaEvaluada as e:
        print(f"ya evaluada: {e}")
        return 1
    except (EntradaInvalida, RazonadorInvalido) as e:
        print(f"entrada inválida: {e}")
        return 2
    print(f"version={r['version']} humo={r['humo']} aprobado={r['aprobado']} informe={r['ruta']}")
    if r.get("modelo_elegido"):
        print(f"modelo_elegido={r['modelo_elegido']} carpeta={r['carpeta_elegida']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
