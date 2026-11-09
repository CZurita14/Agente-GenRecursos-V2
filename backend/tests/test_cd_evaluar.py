import csv
import hashlib
import json
import math
import re
import shutil

import numpy as np
import pytest

from app.razonador import RazonadorInvalido, huella_pesos
from ciencia_datos import evaluar as ev
from ciencia_datos.entrenar import huella
from ciencia_datos.evaluar import (
    YaEvaluada, cargar_pares, dictaminar, elegir_umbral, escribir_informe,
    estabilidad, grupos_con_sentido, kappa, mcnemar, medir_puntaje, silueta_frente_al_azar, wilson,
)
from ciencia_datos.separar import dejar_fuera, separar

MEDIDAS_BUENAS = {
    "exhaustividad": 0.9, "mcnemar_p": 0.01, "solo_modelo": 30, "solo_filtro": 5,
    "silueta": 0.3, "silueta_p95": 0.1, "ari": 0.9, "grupos_con_sentido": 0.9, "kappa": 0.7,
    "pares_para_kappa": 150, "positivos_prueba": 80,
}


def test_wilson_coincide_con_lo_calculado():
    assert wilson(14, 16) == pytest.approx((0.640, 0.965), abs=0.001)


def test_umbral_no_usa_la_prueba():
    u = elegir_umbral(np.array([.9, .8, .3, .2]), np.array([1, 1, 0, 0]))
    assert .3 < u <= .8


def test_umbral_maxima_precision_con_exhaustividad_minima():
    sim = np.array([.95, .9, .85, .8, .7, .6, .5, .4, .3, .2])
    y = np.array([1, 1, 1, 1, 1, 1, 1, 0, 0, 0])
    assert elegir_umbral(sim, y, 1.0) == .5
    y2 = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0, 0])
    assert elegir_umbral(sim, y2, 1.0) == .8
    assert elegir_umbral(sim, y2, 0.5) == .9


def test_umbral_no_cambia_con_las_etiquetas_de_prueba():
    sim_ent, y_ent = np.array([.9, .8, .3, .2]), np.array([1, 1, 0, 0])
    sim_pru = np.array([.9, .6, .5, .1])
    a = medir_puntaje(sim_ent, y_ent, sim_pru, [1, 1, 0, 0])
    b = medir_puntaje(sim_ent, y_ent, sim_pru, [0, 1, 1, 1])
    assert a["umbral"] == b["umbral"]


def test_mcnemar_y_kappa():
    assert mcnemar([True] * 20 + [False] * 5, [False] * 20 + [False] * 5) < .05
    assert mcnemar([True, False], [True, False]) == 1.0
    assert kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1
    assert math.isnan(kappa([1, 1], [1, 1]))


def test_mcnemar_conteos_dan_la_direccion():
    assert ev.mcnemar_conteos([True, True, False, False], [False, False, True, False]) == (2, 1)


def test_kappa_con_acuerdo_parcial():
    assert kappa([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(0.5)


def test_datos_sin_estructura_no_superan_al_azar():
    X = np.random.default_rng(1).normal(size=(60, 32))
    r = silueta_frente_al_azar(X / np.linalg.norm(X, axis=1, keepdims=True), 4)
    assert r["real"] <= r["p95"] + 0.02


def test_datos_con_grupos_claros_superan_al_azar_y_son_estables():
    azar = np.random.default_rng(3)
    centros = np.eye(4, 16) * 5
    X = np.vstack([c + azar.normal(scale=.3, size=(20, 16)) for c in centros])
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    assert silueta_frente_al_azar(X, 4)["supera"] is True
    assert estabilidad(X, 4) > .95


def test_dictamen_exige_todos_los_criterios():
    assert dictaminar(MEDIDAS_BUENAS)["aprobado"] is True
    assert dictaminar({**MEDIDAS_BUENAS, "kappa": .4})["aprobado"] is False
    for clave, malo in [("exhaustividad", .8), ("mcnemar_p", .05), ("silueta", .1), ("ari", .7),
                        ("grupos_con_sentido", .7)]:
        assert dictaminar({**MEDIDAS_BUENAS, clave: malo})["aprobado"] is False, clave


def test_un_modelo_peor_que_el_filtro_se_rechaza_aunque_p_sea_pequeno():
    peor = {**MEDIDAS_BUENAS, "mcnemar_p": 1.9e-06, "solo_modelo": 3, "solo_filtro": 40}
    assert dictaminar(peor)["aprobado"] is False
    assert dictaminar({**MEDIDAS_BUENAS, "solo_modelo": 5, "solo_filtro": 5})["aprobado"] is False


def test_sin_muestra_minima_no_se_aprueba():
    assert dictaminar({**MEDIDAS_BUENAS, "pares_para_kappa": 99})["aprobado"] is False
    assert dictaminar({**MEDIDAS_BUENAS, "positivos_prueba": 59})["aprobado"] is False
    assert dictaminar({**MEDIDAS_BUENAS, "pares_para_kappa": 100, "positivos_prueba": 60})["aprobado"] is True


def test_medida_indefinida_nunca_aprueba():
    for clave in MEDIDAS_BUENAS:
        assert dictaminar({**MEDIDAS_BUENAS, clave: None})["aprobado"] is False
        if clave not in ("pares_para_kappa", "positivos_prueba", "solo_modelo", "solo_filtro"):
            assert dictaminar({**MEDIDAS_BUENAS, clave: math.nan})["aprobado"] is False


def test_dejar_fuera_usa_el_plan_de_separar_y_no_oculta_la_peor():
    mapa = {"PF-1": "A", "PF-2": "A", "PF-3": "B", "PF-4": "B"}
    sim = np.array([.9, .8, .2, .1, .9, .1, .2, .8])
    y = np.array([1, 1, 0, 0, 1, 1, 0, 0])
    codigos = ["PF-1", "PF-2", "PF-1", "PF-2", "PF-3", "PF-4", "PF-3", "PF-4"]
    r = ev.dejar_fuera_pares(sim, y, codigos, dejar_fuera(mapa))
    assert r["peor"] == "B"
    assert r["peor_f1"] == r["por_facultad"]["B"]["f1"] < r["por_facultad"]["A"]["f1"]


def test_f1_cero_cuando_hay_positivos_y_ningun_acierto():
    m = ev.metricas(np.array([0, 0, 1, 1], bool), np.array([1, 1, 0, 0], bool))
    assert m["f1"] == 0.0
    assert math.isnan(ev.metricas(np.array([1, 0], bool), np.array([0, 0], bool))["f1"])


def test_dejar_fuera_lista_las_facultades_excluidas():
    mapa = {"PF-1": "A", "PF-2": "B"}
    r = ev.dejar_fuera_pares(np.array([.9, .1]), np.array([0, 0]), ["PF-1", "PF-2"], dejar_fuera(mapa))
    assert sorted(r["excluidas"]) == ["A", "B"] and r["peor"] is None


def _csv(ruta, filas, cabecera=("caso", "evidencia", "codigo_pf", "docente", "parecido")):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cabecera)
        w.writerows(filas)


def test_cargar_pares_cuenta_rechazos_desacuerdos_y_kappa(tmp_path):
    ruta = tmp_path / "pares.csv"
    _csv(ruta, [
        ("c1", "e1", "PF-A", "ana", "1"), ("c1", "e1", "PF-A", "luis", "1"),
        ("c2", "e2", "PF-A", "ana", "0"), ("c2", "e2", "PF-A", "luis", "1"),  # desacuerdo
        ("c3", "e3", "PF-B", "ana", "0"), ("c3", "e3", "PF-B", "luis", "0"),
        ("c4", "e4", "PF-X", "ana", "1"),  # código en ningún grupo
        ("c5", "e5", "PF-B", "ana", "tal vez"),  # valor inválido
    ])
    r = cargar_pares(ruta, ["PF-A"], ["PF-B"])
    assert r["filas_fuera_de_grupo"] == 1 and r["filas_valor_invalido"] == 1
    assert r["pares_en_desacuerdo"] == 1
    assert {(p["caso"], p["grupo"], p["codigo"]) for p in r["pares"]} == {
        ("c1", "entrenamiento", "PF-A"), ("c3", "prueba", "PF-B")}
    assert r["pares_para_kappa"] == 3 and 0 < r["kappa"] < 1


def _temas(ruta, filas):
    _csv(ruta, filas, ("huella_temas", "grupo", "docente", "tiene_sentido"))


def test_grupos_con_sentido_solo_cuenta_la_huella_del_modelo(tmp_path):
    ruta = tmp_path / "temas.csv"
    _temas(ruta, [("H", "0", "ana", "si"), ("H", "0", "luis", "si"), ("H", "1", "ana", "no"), ("H", "1", "luis", "si"),
                  ("otra", "0", "ana", "no"), ("otra", "1", "ana", "no")])
    assert grupos_con_sentido(ruta, "H", {"0", "1"}) == {"n_grupos": 2, "fraccion": .5}


def test_grupos_sin_juzgar_o_de_mas_dejan_la_fraccion_indefinida(tmp_path):
    ruta = tmp_path / "temas.csv"
    _temas(ruta, [("H", "0", "ana", "si")])  # 1 de 8 grupos juzgado
    assert math.isnan(grupos_con_sentido(ruta, "H", {str(i) for i in range(8)})["fraccion"])
    assert math.isnan(grupos_con_sentido(ruta, "H", set())["fraccion"])  # sobra el grupo 0
    assert math.isnan(grupos_con_sentido(ruta, "otra", {"0"})["fraccion"])  # huella sin filas


def test_informe_se_escribe_por_version_y_el_humo_aparte(tmp_path):
    assert escribir_informe({"v": 1}, tmp_path, "v1", humo=False).name == "v1.json"
    assert escribir_informe({"v": 1}, tmp_path, "v1", humo=True).name == "v1-humo.json"
    assert escribir_informe({"v": 1}, tmp_path, "v1", humo=False, completo=False).name == "v1-incompleta.json"


def test_informe_escribe_nan_como_null_y_floats(tmp_path):
    ruta = escribir_informe({"a": np.float32(.5), "b": math.nan, "c": [np.float64(1)]}, tmp_path, "v", True)
    assert json.loads(ruta.read_text()) == {"a": .5, "b": None, "c": [1.0]}


# --- de extremo a extremo con vectores falsos ---------------------------------------

DIM = 32


def _azar(clave: str):
    return np.random.default_rng(int(hashlib.sha256(clave.encode()).hexdigest()[:8], 16))


def _unitario(v):
    return v / np.linalg.norm(v)


def _vector_falso(bueno: str):
    """Los pares «parecidos» comparten vector en la carpeta `bueno`, y solo débilmente en la otra."""

    def vectorizar(carpeta, textos):
        salida = []
        for t in textos:
            m = re.search(r"(caso|evidencia) secret[oa] (\d+)$", t)
            if m is None:  # fragmentos de sílabo: tres temas claros
                centro = np.eye(DIM)[int(hashlib.sha256(t.encode()).hexdigest(), 16) % 3] * 5
                salida.append(_unitario(centro + _azar(t).normal(scale=.3, size=DIM)))
                continue
            i = int(m.group(2))
            if i % 2 == 1 and carpeta.name == bueno:
                salida.append(_unitario(_azar(f"u{i}").normal(size=DIM) + _azar(t).normal(scale=.1, size=DIM)))
            elif i % 2 == 1:  # el otro modelo solo separa un poco: su umbral depende de las etiquetas
                salida.append(_unitario(.6 * _unitario(_azar(f"u{i}").normal(size=DIM)) + _unitario(_azar(t).normal(size=DIM))))
            else:
                salida.append(_unitario(_azar(t).normal(size=DIM)))
        return np.array(salida)

    return vectorizar


FACULTADES = ["FACULTAD DE INGENIERIAS"] * 4 + ["FACULTAD DE CIENCIAS"] * 4


def _carpeta_modelo(ruta, version, ajuste, sep, huella_sep=None, humo=False):
    (ruta / "onnx").mkdir(parents=True)
    (ruta / "onnx" / "model.onnx").write_bytes(f"onnx {version}".encode())
    separacion = {"entrenamiento": sep.entrenamiento, "prueba": sep.prueba}
    (ruta / "metadatos.json").write_text(json.dumps({
        "version": version, "base": "modelo-base", "humo": humo, "aprobado": False, "umbral": None, "ajuste": ajuste,
        "huella_separacion": huella_sep or huella(separacion), "separacion": separacion,
    }))


def _construir(tmp_path, datos, invertir_prueba=False):
    silabos = tmp_path / "silabos"
    silabos.mkdir()
    codigos = [f"PF-{c}" for c in "ABCDEFGH"]
    for c, fac in zip(codigos, FACULTADES):
        d = json.loads(json.dumps(datos))
        d["proyecto_formativo"]["codigo"] = c
        d["facultad"] = fac
        for i, r in enumerate(d["resultados_aprendizaje"]):
            r["texto"] = f"Resultado {i} propio del sílabo {c}"
        (silabos / f"{c}.json").write_text(json.dumps(d), encoding="utf-8")
    sep = separar({c: "FING" if i < 4 else "FCIE" for i, c in enumerate(codigos)})
    _carpeta_modelo(tmp_path / "ajustado", "v-aj", True, sep)
    _carpeta_modelo(tmp_path / "base", "v-base", False, sep)
    datos_cd = tmp_path / "datos_cd"
    datos_cd.mkdir()
    filas = []
    for i in range(600):
        codigo = codigos[(i // 2) % 8]
        etiqueta = i % 2 if not (invertir_prueba and codigo in sep.prueba) else 1 - i % 2
        filas += [(f"caso secreto {i}", f"evidencia secreta {i}", codigo, d, str(etiqueta)) for d in ("ana", "luis")]
    _csv(datos_cd / "pares.csv", filas)
    return {"ajustado": tmp_path / "ajustado", "base": tmp_path / "base", "silabos": silabos,
            "datos": datos_cd, "salida": tmp_path / "pruebas", "tmp": tmp_path, "sep": sep}


@pytest.fixture
def entorno(tmp_path, datos):
    return _construir(tmp_path, datos)


def _correr(e, modelo="ajustado", base="base", bueno="ajustado", **kw):
    return ev.ejecutar(e[modelo], e["silabos"], base_modelo=e[base] if base else None, datos=e["datos"],
                       salida=kw.pop("salida", e["salida"]), vectorizar=_vector_falso(bueno), k=3,
                       abrir_modelo=kw.pop("abrir_modelo", lambda carpeta: None), **kw)


def _juzgar_temas(e, modelos=("ajustado", "base"), sentido="si"):
    """Paso 1 (temas-para-revisar) sobre cada candidato y los docentes los juzgan (paso 2 los lee evaluar)."""
    filas = []
    for modelo in modelos:
        r = ev.temas_para_revisar(e[modelo], e["silabos"], e["datos"] / f"temas-revision-{modelo}.csv",
                                  k=3, vectorizar=_vector_falso("ajustado"))
        filas += [(r["huella"], str(g), d, sentido) for g in range(r["k"]) for d in ("ana", "luis")]
    _temas(e["datos"] / "temas.csv", filas)


def _meta(e, modelo):
    return json.loads((e[modelo] / "metadatos.json").read_text())


def test_aprueba_y_escribe_aprobado_y_umbral_solo_en_la_carpeta_elegida(entorno):
    _juzgar_temas(entorno)
    r = _correr(entorno)
    assert r["aprobado"] is True, r
    assert r["modelo_elegido"] == "ajustado" and r["candidatos"].keys() == {"ajustado", "base"}
    assert r["huella_modelo_elegido"] == r["huella_modelo"]
    aj, base = _meta(entorno, "ajustado"), _meta(entorno, "base")
    assert aj["aprobado"] is True and aj["umbral"] is not None
    assert aj["huella_pesos"] == huella_pesos(entorno["ajustado"])
    assert base["aprobado"] is False and base["umbral"] is None and "huella_pesos" not in base


def test_gana_el_base_cuando_el_ajustado_no_lo_supera(entorno):
    _juzgar_temas(entorno)
    r = _correr(entorno, bueno="base")
    assert r["modelo_elegido"] == "base" and "no supera" in r["nota_modelo"]
    assert r["huella_modelo_elegido"] != r["huella_modelo"]
    assert r["aprobado"] is True, r
    assert _meta(entorno, "base")["aprobado"] is True and _meta(entorno, "ajustado")["aprobado"] is False
    assert r["dejar_fuera"]["codificador"] == "base" and "generalizacion_del_ajustado" not in r["dejar_fuera"]
    assert r["carpeta_elegida"] == str(entorno["base"]) and r["version_elegida"] == "v-base"
    assert _meta(entorno, "base")["huella_pesos"] == huella_pesos(entorno["base"])


def test_el_ajustado_que_gana_informa_que_su_generalizacion_no_se_midio(entorno):
    _juzgar_temas(entorno)
    r = _correr(entorno)
    assert r["dejar_fuera"]["codificador"] == "base"
    assert r["dejar_fuera"]["generalizacion_del_ajustado"] == "no medida"


def test_informe_real_sin_textos_y_con_conteos(entorno):
    _juzgar_temas(entorno)
    r = _correr(entorno)
    contenido = (entorno["salida"] / "v-aj.json").read_text(encoding="utf-8")
    assert "secret" not in contenido and "propio del sílabo" not in contenido
    assert r["humo"] is False and r["conteos"]["pares_en_desacuerdo"] == 0
    assert r["temas"]["k_reducido"] is False and r["n_silabos_prueba"] == 2
    assert "umbral_con_entrenamiento" not in r["medidas"] and "problemas" not in r
    assert str(entorno["tmp"]) not in contenido  # la carpeta elegida solo sale por consola


def test_segunda_evaluacion_se_rechaza_tambien_con_otra_salida(entorno):
    _juzgar_temas(entorno)
    _correr(entorno)
    with pytest.raises(YaEvaluada):
        _correr(entorno)
    with pytest.raises(YaEvaluada):
        _correr(entorno, salida=entorno["tmp"] / "otra")
    assert (entorno["ajustado"] / "evaluacion.candado").exists()
    assert (entorno["base"] / "evaluacion.candado").exists()


def test_el_candado_del_base_tambien_cuenta(entorno):
    _juzgar_temas(entorno, ("base",))
    _correr(entorno, modelo="base", base=None)  # el base evaluado solo
    with pytest.raises(YaEvaluada):
        _correr(entorno)
    assert not (entorno["ajustado"] / "evaluacion.candado").exists()


def test_humo_se_rechaza_sobre_una_version_real_y_al_reves(entorno):
    with pytest.raises(ValueError, match="humo"):
        _correr(entorno, humo=True)
    meta = _meta(entorno, "ajustado")
    (entorno["ajustado"] / "metadatos.json").write_text(json.dumps({**meta, "humo": True}))
    with pytest.raises(ValueError, match="humo"):
        _correr(entorno)
    assert not (entorno["salida"] / "v-aj.json").exists()
    assert not (entorno["ajustado"] / "evaluacion.candado").exists()


def test_humo_nunca_aprueba_no_usa_etiquetas_y_se_repite(entorno):
    meta = _meta(entorno, "ajustado")
    (entorno["ajustado"] / "metadatos.json").write_text(json.dumps({**meta, "humo": True}))
    (entorno["datos"] / "pares.csv").unlink()
    r = _correr(entorno, base=None, humo=True)
    assert r["humo"] is True and r["aprobado"] is False
    assert (entorno["salida"] / "v-aj-humo.json").exists()
    assert not (entorno["ajustado"] / "evaluacion.candado").exists()
    _correr(entorno, base=None, humo=True)


def test_base_invalido_se_rechaza_antes_de_tomar_candados(entorno):
    for cambio in ({"ajuste": True}, {"humo": True}, {"huella_separacion": "otra"}, {"base": "otro-modelo"}):
        meta = _meta(entorno, "base")
        (entorno["base"] / "metadatos.json").write_text(json.dumps({**meta, **cambio}))
        with pytest.raises(ValueError, match="base"):
            _correr(entorno)
        (entorno["base"] / "metadatos.json").write_text(json.dumps(meta))
    assert not (entorno["ajustado"] / "evaluacion.candado").exists()


def test_sin_csv_el_informe_lo_dice_no_aprueba_y_no_toma_candado(entorno):
    r = _correr(entorno)  # sin temas.csv
    assert r["aprobado"] is False and "temas.csv" in r["motivo"]
    assert (entorno["salida"] / "v-aj-incompleta.json").exists()
    assert not (entorno["ajustado"] / "evaluacion.candado").exists()


def test_encabezados_invalidos_se_rechazan_antes_del_candado(entorno):
    _csv(entorno["datos"] / "temas.csv", [("0", "ana", "si")], ("grupo", "docente", "tiene_sentido"))
    with pytest.raises(ValueError, match="temas.csv"):
        _correr(entorno)
    assert not (entorno["ajustado"] / "evaluacion.candado").exists()


def test_temas_para_revisar_escribe_huella_grupo_texto_sin_candado(entorno):
    destino = entorno["datos"] / "rev.csv"
    r = ev.temas_para_revisar(entorno["ajustado"], entorno["silabos"], destino, k=3, vectorizar=_vector_falso("ajustado"))
    filas = list(csv.DictReader(open(destino, encoding="utf-8-sig")))
    assert filas and set(filas[0]) == {"huella_temas", "grupo", "texto"}
    assert {f["huella_temas"] for f in filas} == {r["huella"]}
    assert {f["grupo"] for f in filas} == {"0", "1", "2"} and r["k_reducido"] is False
    assert not (entorno["ajustado"] / "evaluacion.candado").exists()
    # misma huella al repetir; otro modelo, otra huella
    again = ev.temas_para_revisar(entorno["ajustado"], entorno["silabos"], destino, k=3, vectorizar=_vector_falso("ajustado"))
    otro = ev.temas_para_revisar(entorno["base"], entorno["silabos"], destino, k=3, vectorizar=_vector_falso("ajustado"))
    assert again["huella"] == r["huella"] != otro["huella"]


def test_k_reducido_por_pocos_textos_se_informa(entorno):
    r = ev.temas_para_revisar(entorno["ajustado"], entorno["silabos"], entorno["datos"] / "rev.csv", k=500,
                              vectorizar=_vector_falso("ajustado"))
    assert r["k_reducido"] is True and r["k"] < 500


# --- validación previa al candado ------------------------------------------------------


def _argv(e, **cambios):
    a = {"--modelo": e["ajustado"], "--base-modelo": e["base"], "--silabos": e["silabos"],
         "--datos": e["datos"], "--salida": e["salida"], "--k": 3} | cambios
    return [x for par in a.items() if par[1] is not None for x in (par[0], str(par[1]))]


def _sin_candados(e):
    return not (e["ajustado"] / "evaluacion.candado").exists() and not (e["base"] / "evaluacion.candado").exists()


def _csv_truncado(ruta):
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    ruta.write_text(chr(10).join(lineas[:2] + [lineas[2].rsplit(",", 2)[0]] + lineas[3:]), encoding="utf-8")


@pytest.mark.parametrize("caso", [
    "silabos_inexistente", "sin_onnx_del_modelo", "sin_onnx_del_base", "salida_es_archivo", "k_menor_que_2",
    "pares_truncado", "temas_truncado", "ajustado_sin_base", "base_sobre_un_base",
])
def test_argumento_malo_sale_con_2_sin_quemar_el_candado(entorno, caso):
    e = entorno
    _juzgar_temas(e)
    restaurar = None
    cambios = {}
    if caso == "silabos_inexistente":
        cambios["--silabos"] = e["tmp"] / "no_hay"
    elif caso == "sin_onnx_del_modelo":
        restaurar = (e["ajustado"] / "onnx" / "model.onnx", b"onnx v-aj")
        restaurar[0].unlink()
    elif caso == "sin_onnx_del_base":
        restaurar = (e["base"] / "onnx" / "model.onnx", b"onnx v-base")
        restaurar[0].unlink()
    elif caso == "salida_es_archivo":
        archivo = e["tmp"] / "archivo"
        archivo.write_text("x")
        cambios["--salida"] = archivo
    elif caso == "k_menor_que_2":
        cambios["--k"] = 1
    elif caso == "pares_truncado":
        copia = e["datos"] / "pares.csv"
        original = copia.read_text(encoding="utf-8")
        _csv_truncado(copia)
        restaurar = (copia, original.encode())
    elif caso == "temas_truncado":
        copia = e["datos"] / "temas.csv"
        original = copia.read_text(encoding="utf-8")
        _csv_truncado(copia)
        restaurar = (copia, original.encode())
    elif caso == "ajustado_sin_base":
        cambios["--base-modelo"] = None
    elif caso == "base_sobre_un_base":
        cambios["--modelo"] = e["base"]
        cambios["--base-modelo"] = e["base"]
    assert ev.main(_argv(e, **cambios)) == 2
    assert _sin_candados(e) and not (e["salida"] / "v-aj.json").exists()
    if restaurar:
        restaurar[0].write_bytes(restaurar[1])
    r = _correr(e)  # una corrida correcta después sigue funcionando
    assert r["version"] == "v-aj" and (e["ajustado"] / "evaluacion.candado").exists()


# --- errores recuperables: salen antes del candado y sin métricas -------------------------


def _reescribir_pares(e, valor):
    """Reescribe pares.csv con `valor(i, codigo, docente)` en lugar de la etiqueta."""
    ruta = e["datos"] / "pares.csv"
    original = ruta.read_bytes()
    filas = list(csv.DictReader(open(ruta, encoding="utf-8")))
    _csv(ruta, [(f["caso"], f["evidencia"], f["codigo_pf"], f["docente"],
                 valor(int(f["caso"].split()[-1]), f["codigo_pf"], f["docente"])) for f in filas])
    return ruta, original


def _quitar(ruta):
    original = ruta.read_bytes()
    ruta.unlink()
    return ruta, original


def _cambiar_meta(e, cambio):
    ruta = e["ajustado"] / "metadatos.json"
    original = ruta.read_bytes()
    ruta.write_text(json.dumps({**_meta(e, "ajustado"), **cambio}))
    return ruta, original


def _cambiar_temas(e, transformar):
    ruta = e["datos"] / "temas.csv"
    original = ruta.read_bytes()
    filas = list(csv.reader(open(ruta, encoding="utf-8")))
    _temas(ruta, transformar(filas[1:]))
    return ruta, original


def _huellas(e):
    return [ev.temas_para_revisar(e[m], e["silabos"], e["tmp"] / "aux.csv", k=3, vectorizar=_vector_falso("ajustado"))["huella"]
            for m in ("ajustado", "base")]


def _romper(e, caso):
    prueba = _meta(e, "ajustado")["separacion"]["prueba"]
    aj, base = _huellas(e)
    return {
        "silabo_de_prueba_ausente": lambda: _quitar(e["silabos"] / f"{prueba[0]}.json"),
        "huella_de_separacion": lambda: _cambiar_meta(e, {"huella_separacion": "x"}),
        "pocos_positivos": lambda: _reescribir_pares(e, lambda i, c, d: "0" if c in prueba else str(i % 2)),
        "positivos_en_desacuerdo": lambda: _reescribir_pares(
            e, lambda i, c, d: str(i % 2) if c not in prueba else ("1" if d == "ana" else "0") if i % 2 else "0"),
        "pocos_pares_para_kappa": lambda: _reescribir_pares(
            e, lambda i, c, d: str(i % 2) if d == "ana" or i < 99 else "tal vez"),
        "temas_sin_el_base": lambda: _cambiar_temas(e, lambda fs: [f for f in fs if f[0] != base]),
        "temas_sin_el_ajustado": lambda: _cambiar_temas(e, lambda fs: [f for f in fs if f[0] != aj]),
        "temas_sin_un_grupo": lambda: _cambiar_temas(e, lambda fs: [f for f in fs if not (f[0] == base and f[1] == "2")]),
        "temas_con_un_grupo_de_mas": lambda: _cambiar_temas(e, lambda fs: fs + [[aj, "7", "ana", "si"]]),
        "temas_sin_docente": lambda: _cambiar_temas(e, lambda fs: [[f[0], f[1], "", f[3]] if i == 0 else f for i, f in enumerate(fs)]),
        "temas_sin_respuesta": lambda: _cambiar_temas(e, lambda fs: [[f[0], f[1], f[2], " "] if i == 0 else f for i, f in enumerate(fs)]),
        "temas_vacios_de_otra_huella": lambda: _cambiar_temas(e, lambda fs: fs + [["otra", "0", "", ""]]),
    }[caso]()


@pytest.mark.parametrize("caso", [
    "silabo_de_prueba_ausente", "huella_de_separacion", "pocos_positivos", "positivos_en_desacuerdo",
    "pocos_pares_para_kappa", "temas_sin_el_base", "temas_sin_el_ajustado", "temas_sin_un_grupo",
    "temas_con_un_grupo_de_mas", "temas_sin_docente", "temas_sin_respuesta", "temas_vacios_de_otra_huella",
])
def test_error_recuperable_no_quema_el_candado_y_la_corrida_siguiente_funciona(entorno, caso):
    e = entorno
    _juzgar_temas(e)
    ruta, original = _romper(e, caso)
    with pytest.raises(ev.EntradaInvalida):
        _correr(e)
    assert _sin_candados(e) and not (e["salida"] / "v-aj.json").exists()
    ruta.write_bytes(original)
    r = _correr(e)
    assert r["aprobado"] is True, r
    assert (e["ajustado"] / "evaluacion.candado").exists()


def test_huella_de_separacion_falsa_en_ambos_no_quema_el_candado(entorno):
    _juzgar_temas(entorno)
    for nombre in ("ajustado", "base"):
        (entorno[nombre] / "metadatos.json").write_text(json.dumps({**_meta(entorno, nombre), "huella_separacion": "x"}))
    with pytest.raises(ev.EntradaInvalida, match="huella_separacion"):
        _correr(entorno)
    assert _sin_candados(entorno)


def test_el_base_que_no_abre_no_quema_el_candado_y_se_abren_ambos(entorno):
    _juzgar_temas(entorno)
    abiertos = []

    def abrir(carpeta):
        abiertos.append(carpeta)
        if carpeta == entorno["base"]:
            raise RazonadorInvalido("falta tokenizer.json")

    with pytest.raises(RazonadorInvalido):
        _correr(entorno, abrir_modelo=abrir)
    assert abiertos == [entorno["ajustado"], entorno["base"]] and _sin_candados(entorno)
    assert _correr(entorno)["aprobado"] is True


def test_main_convierte_un_modelo_que_no_abre_en_salida_2_sin_traza(entorno, capsys):
    _juzgar_temas(entorno)  # las carpetas de prueba traen un ONNX de mentira: el real no abre
    assert ev.main(_argv(entorno)) == 2
    assert "entrada inválida" in capsys.readouterr().out
    assert _sin_candados(entorno) and not (entorno["salida"] / "v-aj.json").exists()


def test_metadatos_ausentes_salen_con_2_sin_traza(entorno, capsys):
    (entorno["ajustado"] / "metadatos.json").unlink()
    assert ev.main(_argv(entorno)) == 2
    assert "metadatos" in capsys.readouterr().out


def test_otra_carpeta_con_la_misma_version_se_rechaza(entorno):
    _juzgar_temas(entorno)
    _correr(entorno)
    entorno["copia"], entorno["copia_base"] = entorno["tmp"] / "copia", entorno["tmp"] / "copia_base"
    for origen, destino in (("ajustado", "copia"), ("base", "copia_base")):
        shutil.copytree(entorno[origen], entorno[destino], ignore=shutil.ignore_patterns("evaluacion.candado"))
    with pytest.raises(YaEvaluada):
        _correr(entorno, modelo="copia", base="copia_base")
    assert not (entorno["copia"] / "evaluacion.candado").exists()
    assert not (entorno["copia_base"] / "evaluacion.candado").exists()


def test_un_base_ya_evaluado_copiado_a_otra_carpeta_se_rechaza(entorno):
    _juzgar_temas(entorno)
    _correr(entorno, modelo="base", base=None)
    entorno["copia_base"] = entorno["tmp"] / "copia_base"
    shutil.copytree(entorno["base"], entorno["copia_base"], ignore=shutil.ignore_patterns("evaluacion.candado"))
    with pytest.raises(YaEvaluada):
        _correr(entorno, base="copia_base")
    assert _sin_candados({"ajustado": entorno["ajustado"], "base": entorno["copia_base"]})


def test_un_informe_en_la_salida_de_omision_cuenta_aunque_se_cambie_salida(entorno, monkeypatch):
    _juzgar_temas(entorno)
    omision = entorno["tmp"] / "omision"
    omision.mkdir()
    (omision / "v-aj.json").write_text("{}")
    monkeypatch.setattr(ev, "SALIDA_POR_DEFECTO", omision)
    with pytest.raises(YaEvaluada):
        _correr(entorno)
    assert _sin_candados(entorno)


def test_la_consola_nombra_el_modelo_elegido_y_su_carpeta(entorno, monkeypatch, capsys):
    monkeypatch.setattr(ev, "ejecutar", lambda *a, **k: {
        "version": "v-aj", "humo": False, "aprobado": True, "ruta": "informe.json",
        "modelo_elegido": "base", "carpeta_elegida": str(entorno["base"])})
    assert ev.main(_argv(entorno)) == 0
    salida = capsys.readouterr().out
    assert "modelo_elegido=base" in salida and f"carpeta={entorno['base']}" in salida


# --- CSV de docentes: Excel, BOM, separador y plantilla ------------------------------------


@pytest.mark.parametrize("codificacion", ["utf-8", "utf-8-sig"])
@pytest.mark.parametrize("separador", [",", ";"])
def test_los_csv_aceptan_bom_y_ambos_separadores(tmp_path, codificacion, separador):
    ruta = tmp_path / "pares.csv"
    with open(ruta, "w", encoding=codificacion, newline="") as f:
        w = csv.writer(f, delimiter=separador)
        w.writerow(("caso", "evidencia", "codigo_pf", "docente", "parecido"))
        w.writerows([("c1, con coma", "e1; con punto y coma", "PF-A", d, "sí") for d in ("ana", "luis")])
    r = cargar_pares(ruta, ["PF-A"], [])
    assert [(p["caso"], p["evidencia"], p["etiqueta"]) for p in r["pares"]] == [("c1, con coma", "e1; con punto y coma", 1)]
    assert r["filas_valor_invalido"] == 0


def test_csv_que_no_es_utf8_se_rechaza_con_entrada_invalida(tmp_path):
    ruta = tmp_path / "temas.csv"
    ruta.write_bytes("huella_temas,grupo,docente,tiene_sentido\nH,0,ana,sí\n".encode("cp1252"))
    with pytest.raises(ev.EntradaInvalida, match="temas.csv"):
        grupos_con_sentido(ruta, "H", {"0"})


def test_temas_para_revisar_escribe_la_plantilla_y_los_archivos_llevan_bom(entorno):
    destino = entorno["datos"] / "rev.csv"
    r = ev.temas_para_revisar(entorno["ajustado"], entorno["silabos"], destino, k=3, vectorizar=_vector_falso("ajustado"))
    plantilla = entorno["datos"] / "temas-plantilla-v-aj.csv"
    assert r["plantilla"] == str(plantilla)
    assert destino.read_bytes().startswith(b"\xef\xbb\xbf") and plantilla.read_bytes().startswith(b"\xef\xbb\xbf")
    filas = list(csv.reader(open(plantilla, encoding="utf-8-sig", newline="")))
    assert filas[0] == ["huella_temas", "grupo", "docente", "tiene_sentido"]
    assert filas[1:] == [[r["huella"], str(g), "", ""] for g in range(3)]


def test_las_plantillas_de_ambos_pegadas_en_un_solo_csv_de_excel_aprueban(entorno):
    """El camino de la guía: cada docente llena su copia y se pegan en un solo temas.csv con `;` y BOM."""
    filas = []
    for modelo, version in (("ajustado", "v-aj"), ("base", "v-base")):
        ev.temas_para_revisar(entorno[modelo], entorno["silabos"], entorno["datos"] / f"rev-{modelo}.csv", k=3,
                              vectorizar=_vector_falso("ajustado"))
        lector = csv.DictReader(open(entorno["datos"] / f"temas-plantilla-{version}.csv", encoding="utf-8-sig", newline=""))
        filas += [(f["huella_temas"], f["grupo"], d, "sí") for f in lector for d in ("D1", "D2")]
    with open(entorno["datos"] / "temas.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(ev.CABECERA_TEMAS)
        w.writerows(filas)
    assert _correr(entorno)["aprobado"] is True


def test_invertir_las_etiquetas_de_prueba_no_mueve_el_umbral_de_ningun_candidato(tmp_path, datos):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = _construir(tmp_path / "a", datos)
    b = _construir(tmp_path / "b", datos, invertir_prueba=True)
    for e in (a, b):
        _juzgar_temas(e)
    ra, rb = _correr(a), _correr(b)
    assert set(ra["candidatos"]) == set(rb["candidatos"]) == {"ajustado", "base"}
    for nombre in ra["candidatos"]:
        assert ra["candidatos"][nombre]["umbral"] == rb["candidatos"][nombre]["umbral"], nombre
    assert ra["medidas"]["positivos_prueba"] != 0  # y las métricas de prueba sí cambian
    assert ra["candidatos"]["ajustado"]["f1"] != rb["candidatos"]["ajustado"]["f1"]


def test_dejar_fuera_mide_con_el_base_aunque_gane_el_ajustado(entorno):
    _juzgar_temas(entorno)
    r = _correr(entorno)  # el ajustado es bueno; el base, débil
    assert r["modelo_elegido"] == "ajustado"
    assert r["dejar_fuera"]["peor_f1"] < 0.9  # con el ajustado sería ~1,0


def test_pares_de_silabos_desconocidos_se_cuentan_y_no_entran_a_dejar_fuera(entorno):
    _juzgar_temas(entorno)
    perdido = entorno["sep"].entrenamiento[0]
    (entorno["silabos"] / f"{perdido}.json").unlink()
    esperados = sum(1 for f in csv.DictReader(open(entorno["datos"] / "pares.csv", encoding="utf-8"))
                    if f["codigo_pf"] == perdido and f["docente"] == "ana")
    r = _correr(entorno)
    assert esperados > 0 and r["dejar_fuera"]["pares_sin_facultad"] == esperados


def test_las_filas_del_azar_de_la_silueta_van_en_l2(monkeypatch):
    from ciencia_datos import estadistica

    vistos = []
    real = estadistica.agrupar
    monkeypatch.setattr(estadistica, "agrupar", lambda X, k, semilla=42: (vistos.append(np.asarray(X)), real(X, k, semilla))[1])
    X = np.random.default_rng(5).normal(size=(40, 16))
    silueta_frente_al_azar(X / np.linalg.norm(X, axis=1, keepdims=True), 3, veces=4)
    assert len(vistos) == 5
    for Y in vistos:
        assert np.allclose(np.linalg.norm(Y, axis=1), 1.0)


def _modelo_falso(tmp_path, *, preliminar, humo):
    modelo = tmp_path / "modelo"
    (modelo / "onnx").mkdir(parents=True)
    (modelo / "onnx" / "model.onnx").write_bytes(b"onnx")
    (tmp_path / "silabos").mkdir(exist_ok=True)
    (modelo / "metadatos.json").write_text(json.dumps({
        "version": "v-pre", "base": "modelo-base", "humo": humo, "aprobado": False, "umbral": None, "ajuste": True,
        "preliminar": preliminar, "separacion": {"entrenamiento": [], "prueba": []},
    }))
    return modelo


def test_evaluar_rechaza_un_modelo_preliminar_sin_tomar_candado(tmp_path):
    modelo = _modelo_falso(tmp_path, preliminar=True, humo=False)
    with pytest.raises(ev.EntradaInvalida, match="preliminar"):
        ev.ejecutar(modelo, tmp_path / "silabos", datos=tmp_path, salida=tmp_path / "s")
    assert not (modelo / "evaluacion.candado").exists()


def test_evaluar_con_humo_sigue_con_un_modelo_preliminar(tmp_path):
    modelo = _modelo_falso(tmp_path, preliminar=True, humo=True)
    r = ev.ejecutar(modelo, tmp_path / "silabos", datos=tmp_path, salida=tmp_path / "s", humo=True)
    assert r["humo"] is True and r["aprobado"] is False


def _modelo_con_sep(tmp_path, sep, origen=None, preliminar=False):
    modelo = _modelo_falso(tmp_path, preliminar=preliminar, humo=False)
    p = modelo / "metadatos.json"
    meta = json.loads(p.read_text())
    meta.pop("preliminar", None)
    meta["separacion"] = sep
    if origen:
        meta["origen"] = origen
    p.write_text(json.dumps(meta))
    return modelo


@pytest.mark.parametrize("sep,origen", [
    ({"entrenamiento": ["SIM-1"], "prueba": []}, None),
    ({"entrenamiento": [], "prueba": ["SIM-2"]}, None),
    ({"entrenamiento": ["PF-1"], "prueba": ["PF-2"]}, {"simulados": 3, "reales": 2}),
])
def test_evaluar_rechaza_simulados_sin_la_marca_preliminar(tmp_path, sep, origen):
    modelo = _modelo_con_sep(tmp_path, sep, origen)
    with pytest.raises(ev.EntradaInvalida, match="simulados"):
        ev.ejecutar(modelo, tmp_path / "silabos", datos=tmp_path, salida=tmp_path / "s")
    assert not (modelo / "evaluacion.candado").exists()
