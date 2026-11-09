import csv
import hashlib
import json

import numpy as np

from app.silabo.modelo import SilaboUTI
from ciencia_datos import revisar_lote
from ciencia_datos.revisar_lote import dictaminar_lote, muestrear, revisar


def _vectorizar_falso(textos: list[str]) -> np.ndarray:
    """Un vector pseudoaleatorio por texto: iguales dan 1, distintos casi 0."""
    filas = []
    for t in textos:
        semilla = int.from_bytes(hashlib.sha256(t.encode("utf-8")).digest()[:8], "big")
        v = np.random.default_rng(semilla).normal(size=128)
        filas.append(v / np.linalg.norm(v))
    return np.array(filas, dtype=float).reshape(len(textos), 128)


def _reescribir(base: SilaboUTI, codigo: str, facultad: str, carrera: str, texto) -> SilaboUTI:
    """Copia del sílabo con `texto(tipo, indice)` en cada fragmento."""
    d = base.model_dump(mode="json")
    d["proyecto_formativo"]["codigo"] = codigo
    d["facultad"], d["carrera"] = facultad, carrera
    n = 0

    def nuevo(tipo):
        nonlocal n
        n += 1
        return texto(tipo, n)

    for r in d["resultados_aprendizaje"]:
        r["texto"] = nuevo("resultado")
    for m in d["momentos"]:
        m["evidencia"] = nuevo("evidencia")
        for s in m["sesiones"]:
            s["contenidos"] = [nuevo("contenido") for _ in s["contenidos"]]
            for k in ("docente", "practico", "autonomo"):
                s[k]["texto"] = nuevo("actividad")
    return SilaboUTI.model_validate(d)


def _lote_variado(base: SilaboUTI, actividad: str = "") -> list[SilaboUTI]:
    lote = []
    for f, fac in enumerate(("FACULTAD A", "FACULTAD B")):
        for c in range(2):
            carrera = f"CARRERA {f}{c}"

            def texto(tipo, i, f=f, c=c):
                extra = f" {actividad}" if actividad and tipo == "actividad" else ""
                return f"palabra{f}{c}x{i} {tipo} distinto {f}{c} caso {i}{extra}"

            lote.append(_reescribir(base, f"SIM-{f}{c}", fac, carrera, texto))
    return lote


def _lote_con_actividad_identica_en_dos_carreras(base: SilaboUTI) -> list[SilaboUTI]:
    def comun(tipo, i):
        return f"texto compartido numero {i} sobre {tipo} en ambas carreras"

    return [
        _reescribir(base, "SIM-1", "FACULTAD A", "CARRERA 1", comun),
        _reescribir(base, "SIM-2", "FACULTAD A", "CARRERA 2", comun),
    ]


def test_revisar_detecta_textos_repetidos_entre_carreras(silabo):
    informe = revisar(_lote_con_actividad_identica_en_dos_carreras(silabo), _vectorizar_falso)
    assert informe["fraccion_casi_repetidos_entre_carreras"] > 0
    assert any("casi_repetidos" in c for c in dictaminar_lote(informe))


def test_repetidos_dentro_de_la_misma_carrera_no_cuentan_entre_carreras(silabo):
    def comun(tipo, i):
        return f"texto compartido numero {i} sobre {tipo}"

    lote = [
        _reescribir(silabo, "SIM-1", "FACULTAD A", "CARRERA 1", comun),
        _reescribir(silabo, "SIM-2", "FACULTAD A", "CARRERA 1", comun),
    ]
    informe = revisar(lote, _vectorizar_falso)
    assert informe["fraccion_casi_repetidos"] > 0.9
    assert informe["fraccion_casi_repetidos_entre_carreras"] == 0


def test_lote_variado_pasa(silabo):
    informe = revisar(_lote_variado(silabo), _vectorizar_falso)
    assert dictaminar_lote(informe) == []


def test_informe_cuenta_silabos_y_fragmentos(silabo):
    informe = revisar(_lote_variado(silabo), _vectorizar_falso)
    assert informe["silabos_por_facultad"] == {"FACULTAD A": 2, "FACULTAD B": 2}
    assert informe["silabos_por_carrera"]["FACULTAD A"] == {"CARRERA 00": 1, "CARRERA 01": 1}
    minimo = informe["fragmentos_por_silabo"]["minimo"]
    assert minimo == informe["fragmentos_por_silabo"]["maximo"] > 0
    assert informe["datos_personales_detectados"] == 0


def test_el_informe_no_contiene_texto(silabo):
    informe = revisar(_lote_variado(silabo, actividad="TEXTO-SECRETO"), _vectorizar_falso)
    assert "TEXTO-SECRETO" not in json.dumps(informe, ensure_ascii=False)


def test_inicio_repetido_se_detecta(silabo):
    lote = [
        _reescribir(silabo, f"SIM-{k}", "FACULTAD A", f"CARRERA {k}",
                    lambda tipo, i, k=k: f"En esta sesion el estudiante hace {k} {i} {tipo}")
        for k in range(3)
    ]
    informe = revisar(lote, _vectorizar_falso)
    assert informe["fraccion_inicio_repetido"] > 0.9
    assert any("inicio_repetido" in c for c in dictaminar_lote(informe))


def test_datos_personales_se_cuentan_sin_guardar_el_texto(silabo):
    lote = _lote_variado(silabo)
    d = lote[0].model_dump(mode="json")
    d["resultados_aprendizaje"][0]["texto"] = "escribir a alguien.secreto@correo.com"
    lote[0] = SilaboUTI.model_validate(d)
    informe = revisar(lote, _vectorizar_falso)
    assert informe["datos_personales_detectados"] >= 1
    assert "alguien.secreto" not in json.dumps(informe)
    assert any("datos_personales" in c for c in dictaminar_lote(informe))


def test_pocos_fragmentos_incumple_el_criterio(silabo):
    d = silabo.model_dump(mode="json")
    d["resultados_aprendizaje"] = d["resultados_aprendizaje"][:1]
    d["momentos"] = d["momentos"][:1]
    d["momentos"][0]["sesiones"] = d["momentos"][0]["sesiones"][:1]
    pequeno = SilaboUTI.model_validate(d)
    informe = revisar([pequeno], _vectorizar_falso)
    assert any("fragmentos_por_silabo" in c for c in dictaminar_lote(informe))


def test_muestra_toma_de_todas_las_facultades_y_es_reproducible(silabo):
    lote = _lote_variado(silabo)
    m1 = muestrear(lote, 10)
    assert len(m1) == 10
    assert {f.facultad for f in m1} == {"FACULTAD A", "FACULTAD B"}
    assert [f.texto for f in m1] == [f.texto for f in muestrear(lote, 10)]


def test_cli_escribe_revision_y_muestra(silabo, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(revisar_lote, "RAIZ", tmp_path)
    monkeypatch.setattr(revisar_lote, "_esperadas", lambda codigos: {"FACULTAD A", "FACULTAD B"})
    carpeta = tmp_path / "silabos"
    carpeta.mkdir()
    for s in _lote_variado(silabo):
        (carpeta / f"{s.proyecto_formativo.codigo}.json").write_text(
            s.model_dump_json(), encoding="utf-8"
        )
    monkeypatch.setattr(revisar_lote, "_vectorizar_real", lambda base=None: _vectorizar_falso)
    salida = tmp_path / "datos_cd"
    codigo = revisar_lote.main(["--silabos", str(carpeta), "--salida", str(salida), "--muestra", "6"])
    assert codigo == 0
    informe = json.loads((salida / "simulacion" / "revision.json").read_text(encoding="utf-8"))
    assert informe["datos_personales_detectados"] == 0
    with open(salida / "simulacion" / "muestra-revision.csv", encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 6
    assert list(filas[0]) == ["codigo", "carrera", "momento", "tipo", "texto", "parece_real"]
    assert all(r["parece_real"] == "" for r in filas)
    consola = capsys.readouterr().out
    assert "palabra" not in consola


def test_cobertura_compara_contra_las_facultades_esperadas(silabo):
    lote = _lote_variado(silabo)
    informe = revisar(lote, _vectorizar_falso, esperadas={"FACULTAD A", "FACULTAD B", "FACULTAD C"})
    assert any("cobertura_facultades" in c for c in dictaminar_lote(informe))
    informe = revisar(lote, _vectorizar_falso, esperadas={"FACULTAD A", "FACULTAD B"})
    assert dictaminar_lote(informe) == []


def test_muestra_neutraliza_formulas_en_el_csv(tmp_path):
    from ciencia_datos.corpus import Fragmento
    muestra = [Fragmento("SIM-1", "F", "=CARRERA", 1, "actividad", t) for t in ("=1+1", "+x", "-x", "@x", "normal")]
    revisar_lote._escribir_muestra(tmp_path / "m.csv", muestra)
    with open(tmp_path / "m.csv", encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    assert [r["texto"] for r in filas] == ["'=1+1", "'+x", "'-x", "'@x", "normal"]
    assert filas[0]["carrera"] == "'=CARRERA"


def _carpeta_de(silabos, destino):
    destino.mkdir(exist_ok=True)
    for s in silabos:
        (destino / f"{s.proyecto_formativo.codigo}.json").write_text(s.model_dump_json(), encoding="utf-8")
    return destino


def test_lote_con_un_real_sale_con_2_sin_escribir(silabo, tmp_path, monkeypatch):
    lote = _lote_variado(silabo)
    lote.append(_reescribir(silabo, "PF-REAL", "FACULTAD A", "CARRERA X", lambda t, i: f"otro {t} {i}"))
    carpeta = _carpeta_de(lote, tmp_path / "silabos")
    monkeypatch.setattr(revisar_lote, "_vectorizar_real", lambda base=None: _vectorizar_falso)
    salida = tmp_path / "datos_cd"
    assert revisar_lote.main(["--silabos", str(carpeta), "--salida", str(salida)]) == 2
    assert not salida.exists()


def test_salida_fuera_de_datos_cd_sale_con_2(silabo, tmp_path, monkeypatch):
    carpeta = _carpeta_de(_lote_variado(silabo), tmp_path / "silabos")
    monkeypatch.setattr(revisar_lote, "_vectorizar_real", lambda base=None: _vectorizar_falso)
    monkeypatch.setattr(revisar_lote, "RAIZ", tmp_path)
    monkeypatch.setattr(revisar_lote, "_esperadas", lambda codigos: {"FACULTAD A", "FACULTAD B"})
    fuera = tmp_path / "otra"
    assert revisar_lote.main(["--silabos", str(carpeta), "--salida", str(fuera)]) == 2
    assert not fuera.exists()
    dentro = tmp_path / "datos_cd"
    assert revisar_lote.main(["--silabos", str(carpeta), "--salida", str(dentro), "--muestra", "4"]) in (0, 1)
    assert (dentro / "simulacion" / "muestra-revision.csv").exists()


def test_esperadas_son_las_facultades_de_los_codigos_leidos_o_todas():
    from ciencia_datos.sim_plan import cupos
    todos = cupos(revisar_lote.CATALOGO)
    uno = todos[0]
    assert revisar_lote._esperadas({uno.codigo}) == {uno.facultad}
    assert revisar_lote._esperadas({"SIM-NO-EXISTE"}) == {c.facultad for c in todos}
    assert len({c.facultad for c in todos}) > 1
