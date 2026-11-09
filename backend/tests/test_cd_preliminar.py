import json
import zlib

import numpy as np
import pytest

from ciencia_datos.evaluar import EntradaInvalida
from ciencia_datos.preliminar import ADVERTENCIA, ejecutar_preliminar, main, precision_k

FING = "FACULTAD DE INGENIERIAS"
FADA = "FACULTAD DE ARQUITECTURA, DISEÑO Y ARTES"
FCED = "FACULTAD DE CIENCIAS DE LA EDUCACION"
TEXTO_DE_PRUEBA = "Resultado propio del sílabo SIM-A"


def _silabos(tmp_path, datos, lista):
    carpeta = tmp_path / "silabos"
    carpeta.mkdir(exist_ok=True)
    for codigo, facultad, carrera in lista:
        d = json.loads(json.dumps(datos))
        d["proyecto_formativo"]["codigo"] = codigo
        d["facultad"] = facultad
        d["carrera"] = carrera
        for r in d["resultados_aprendizaje"]:
            r["texto"] = f"Resultado propio del sílabo {codigo}"
        (carpeta / f"{codigo}.json").write_text(json.dumps(d), encoding="utf-8")
    return carpeta


def _modelo(tmp_path, nombre, *, ajuste=True, preliminar=True, huella="h1", prueba=("SIM-A", "SIM-B", "SIM-C"),
            control=("REAL-1", "REAL-2")):
    carpeta = tmp_path / nombre
    carpeta.mkdir()
    meta = {
        "version": nombre, "aprobado": False, "umbral": None, "ajuste": ajuste, "huella_separacion": huella,
        "separacion": {"entrenamiento": ["SIM-X"], "prueba": list(prueba), "control_real": list(control)},
    }
    if preliminar:
        meta["preliminar"] = True
    (carpeta / "metadatos.json").write_text(json.dumps(meta), encoding="utf-8")
    return carpeta


def _vectores_falsos(carpeta, textos):
    """Vectores deterministas por texto y por modelo, sin cargar nada."""
    sal = zlib.crc32(carpeta.name.encode())
    return np.array([np.random.default_rng(zlib.crc32(t.encode()) ^ sal).normal(size=8) for t in textos])


@pytest.fixture
def entorno(tmp_path, datos):
    silabos = _silabos(tmp_path, datos, [
        ("SIM-A", FING, "SOFTWARE"), ("SIM-B", FING, "INDUSTRIAL"), ("SIM-C", FADA, "ARQUITECTURA"),
        ("REAL-1", FING, "SOFTWARE"), ("REAL-2", FADA, "ARQUITECTURA"), ("REAL-3", FCED, "EDUCACION"),
    ])
    return {
        "silabos": silabos,
        "modelo": _modelo(tmp_path, "v1"),
        "base": _modelo(tmp_path, "base", ajuste=False),
        "salida": tmp_path / "informes",
    }


def _correr(e, **cambios):
    a = {**e, **cambios}
    return ejecutar_preliminar(a["modelo"], a["base"], [a["silabos"]], a["salida"], vectorizar=_vectores_falsos)


# --- precision_k --------------------------------------------------------------------


def test_precision_5_con_vecinos_conocidos():
    X = np.array([[1, 0], [0.99, 0.1], [0, 1], [0.1, 0.99]], dtype=float)
    assert precision_k(X, ["A", "A", "B", "B"], ["s1", "s2", "s3", "s4"], k=1) == 1.0
    assert precision_k(X, ["A", "B", "A", "B"], ["s1", "s2", "s3", "s4"], k=1) == 0.0


def test_los_vecinos_del_mismo_silabo_no_cuentan():
    X = np.array([[1.0, 0.0], [1.0, 0.0]])
    assert precision_k(X, ["A", "A"], ["s1", "s1"], k=1) is None


def test_el_vecino_del_mismo_silabo_se_salta():
    X = np.array([[1, 0], [1, 0.001], [0, 1]], dtype=float)
    # El más cercano al primero es del mismo sílabo: debe contar el del otro sílabo, de otra etiqueta.
    assert precision_k(X, ["A", "A", "B"], ["s1", "s1", "s2"], k=1) == 0.0


# --- informe ------------------------------------------------------------------------


def test_informe_compara_ambos_modelos_y_nunca_aprueba(entorno):
    r = _correr(entorno)
    assert set(r["candidatos"]) == {"ajustado", "base"}
    assert r["apto_produccion"] is False
    assert r["advertencia"] == ADVERTENCIA and "no calidad" in r["advertencia"]
    assert "aprobado" not in json.dumps(r)
    for c in r["candidatos"].values():
        assert {"precision_5_carrera", "precision_5_facultad", "silueta_facultad", "silueta_facultad_barajada",
                "por_facultad", "control_real"} <= set(c)
    assert r["n_control_real"] == 2
    assert (entorno["salida"] / "v1-preliminar.json").exists()
    # Los modelos no se tocan.
    assert not any(p.name.endswith("-preliminar.json") for p in entorno["modelo"].iterdir())
    assert json.loads((entorno["modelo"] / "metadatos.json").read_text(encoding="utf-8"))["umbral"] is None


def test_se_puede_repetir(entorno):
    a, b = _correr(entorno), _correr(entorno)
    assert a == b


def test_control_real_mide_la_facultad(entorno):
    c = _correr(entorno)["candidatos"]["ajustado"]["control_real"]
    assert c["n_fragmentos"] > 0 and c["n_contados"] == c["n_fragmentos"]
    assert 0.0 <= c["precision_5_facultad"] <= 1.0


def test_facultad_real_sin_simulados_da_null(tmp_path, entorno):
    modelo = _modelo(tmp_path, "v2", control=("REAL-3",))
    base = _modelo(tmp_path, "base2", ajuste=False, control=("REAL-3",))
    r = _correr(entorno, modelo=modelo, base=base)
    c = r["candidatos"]["ajustado"]["control_real"]
    assert c["precision_5_facultad"] is None and c["n_contados"] == 0
    assert r["n_control_real"] == 1


def test_rechaza_un_modelo_que_no_es_preliminar(tmp_path, entorno):
    modelo = _modelo(tmp_path, "v3", preliminar=False)
    with pytest.raises(EntradaInvalida):
        _correr(entorno, modelo=modelo)
    assert not entorno["salida"].exists()


def test_rechaza_un_base_con_ajuste(tmp_path, entorno):
    with pytest.raises(EntradaInvalida):
        _correr(entorno, base=_modelo(tmp_path, "base3", ajuste=True))


def test_rechaza_huellas_distintas(tmp_path, entorno):
    with pytest.raises(EntradaInvalida):
        _correr(entorno, base=_modelo(tmp_path, "base4", ajuste=False, huella="otra"))
    assert not entorno["salida"].exists()


def test_rechaza_codigos_que_no_estan_en_los_silabos(tmp_path, entorno):
    modelo = _modelo(tmp_path, "v4", prueba=("SIM-A", "SIM-NO"))
    base = _modelo(tmp_path, "base5", ajuste=False, prueba=("SIM-A", "SIM-NO"))
    with pytest.raises(EntradaInvalida):
        _correr(entorno, modelo=modelo, base=base)


def test_rechaza_salida_dentro_de_un_modelo(entorno):
    with pytest.raises(EntradaInvalida):
        _correr(entorno, salida=entorno["modelo"] / "informes")


def test_el_informe_no_lleva_texto(entorno):
    r = _correr(entorno)
    texto = json.dumps(r, ensure_ascii=False) + (entorno["salida"] / "v1-preliminar.json").read_text(encoding="utf-8")
    assert TEXTO_DE_PRUEBA not in texto and "propio" not in texto


def test_cli_entrada_invalida_sale_con_2(tmp_path, entorno, capsys):
    modelo = _modelo(tmp_path, "v5", preliminar=False)
    codigo = main(["--modelo", str(modelo), "--base-modelo", str(entorno["base"]),
                   "--silabos", str(entorno["silabos"]), "--salida", str(entorno["salida"])])
    assert codigo == 2
    assert not entorno["salida"].exists()


def test_los_reales_no_cambian_la_cifra_global(tmp_path, entorno):
    con = _correr(entorno)["candidatos"]
    (tmp_path / "otro").mkdir()
    sin = ejecutar_preliminar(
        _modelo(tmp_path / "otro", "v1", control=()), _modelo(tmp_path / "otro", "base", ajuste=False, control=()),
        [entorno["silabos"]], tmp_path / "otro" / "informes", vectorizar=_vectores_falsos,
    )["candidatos"]
    for nombre in ("ajustado", "base"):
        for clave in ("precision_5_carrera", "precision_5_facultad", "silueta_facultad",
                      "silueta_facultad_barajada", "por_facultad"):
            assert con[nombre][clave] == sin[nombre][clave]
    assert sin["ajustado"]["control_real"]["precision_5_facultad"] is None


def test_k_mayor_que_los_vecinos_disponibles():
    X = np.array([[1, 0], [0.9, 0.1], [0.95, 0.05]], dtype=float)
    # Cada fragmento solo tiene 2 vecinos de otros sílabos; k=10 usa los disponibles.
    assert precision_k(X, ["A", "A", "B"], ["s1", "s2", "s3"], k=10) == pytest.approx(1 / 3)


@pytest.mark.parametrize("sospechoso", ["SIM-C", "REAL-2"])
def test_facultad_sin_sigla_en_prueba_o_control_es_entrada_invalida(tmp_path, datos, sospechoso):
    lista = [("SIM-A", FING, "SOFTWARE"), ("SIM-B", FING, "INDUSTRIAL"), ("SIM-C", FADA, "ARQUITECTURA"),
             ("REAL-1", FING, "SOFTWARE"), ("REAL-2", FADA, "ARQUITECTURA")]
    lista = [(c, "FACULTAD INVENTADA" if c == sospechoso else f, ca) for c, f, ca in lista]
    e = {"silabos": _silabos(tmp_path, datos, lista), "modelo": _modelo(tmp_path, "v1"),
         "base": _modelo(tmp_path, "base", ajuste=False), "salida": tmp_path / "informes"}
    with pytest.raises(EntradaInvalida, match="facultad"):
        _correr(e)
    assert not e["salida"].exists()
    assert main(["--modelo", str(e["modelo"]), "--base-modelo", str(e["base"]),
                 "--silabos", str(e["silabos"]), "--salida", str(e["salida"])]) == 2
