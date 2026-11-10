import json
import shutil
from pathlib import Path

from app.sga.comparar import comparar, main

SGA = Path(__file__).resolve().parent / "fixtures" / "sga" / "sga_silabos"
CODIGOS = sorted(p.stem for p in SGA.glob("*.json"))


def _dirs(tmp_path):
    a, b = tmp_path / "sga", tmp_path / "ref"
    a.mkdir(); b.mkdir()
    for p in SGA.glob("*.json"):
        shutil.copy(p, a / p.name)
        shutil.copy(p, b / p.name)
    return a, b


def _codigo(p: Path) -> str:
    return json.loads(p.read_text(encoding="utf-8"))["proyecto_formativo"]["codigo"]


def test_identicos(tmp_path):
    a, b = _dirs(tmp_path)
    inf = comparar(a, b)
    assert len(inf["codigos"]) == 3
    for r in inf["codigos"].values():
        assert r["diferentes"] == [] and r["coincidencia"] == 100.0 and r["comparados"] > 50
    assert inf["solo_sga"] == [] and inf["solo_referencia"] == []


def test_campo_distinto_solo_ruta(tmp_path):
    a, b = _dirs(tmp_path)
    f = sorted(a.glob("*.json"))[0]
    d = json.loads(f.read_text(encoding="utf-8"))
    d["momentos"][0]["titulo"] = "TITULO-SECRETO-XYZ"
    d["docente"] = "otro docente"  # privado: no cuenta
    f.write_text(json.dumps(d), encoding="utf-8")
    inf = comparar(a, b)
    r = inf["codigos"][_codigo(f)]
    assert r["diferentes"] == ["momentos[0].titulo"]
    assert 0 < r["coincidencia"] < 100
    assert "TITULO-SECRETO-XYZ" not in json.dumps(inf)
    assert all(x["diferentes"] == [] for k, x in inf["codigos"].items() if k != _codigo(f))


def test_falta_en_un_lado(tmp_path):
    a, b = _dirs(tmp_path)
    f = sorted(b.glob("*.json"))[0]
    cod = _codigo(f)
    f.unlink()
    inf = comparar(a, b)
    assert inf["solo_sga"] == [cod] and cod not in inf["codigos"] and len(inf["codigos"]) == 2
    inf2 = comparar(b, a)
    assert inf2["solo_referencia"] == [cod]


def test_cli_imprime_resumen(tmp_path, capsys):
    a, b = _dirs(tmp_path)
    f = sorted(a.glob("*.json"))[0]
    d = json.loads(f.read_text(encoding="utf-8"))
    d["momentos"][0]["titulo"] = "TITULO-SECRETO-XYZ"
    f.write_text(json.dumps(d), encoding="utf-8")
    assert main([str(a), str(b)]) == 1
    out = capsys.readouterr().out
    assert "momentos[0].titulo" in out and "TITULO-SECRETO-XYZ" not in out and "%" in out
    assert main([str(b), str(b)]) == 0


def test_paralelos_identicos_cuentan_una_vez(tmp_path):
    a, b = _dirs(tmp_path)
    f = sorted(a.glob("*.json"))[0]
    shutil.copy(f, a / "zz-otro-paralelo.json")
    inf = comparar(a, b)
    assert len(inf["codigos"]) == 3 and all(r["diferentes"] == [] for r in inf["codigos"].values())


def test_paralelos_distintos_nombran_el_codigo(tmp_path):
    import pytest
    a, b = _dirs(tmp_path)
    f = sorted(a.glob("*.json"))[0]
    d = json.loads(f.read_text(encoding="utf-8"))
    d["momentos"][0]["titulo"] = "TITULO-SECRETO-XYZ"
    (a / "zz-otro-paralelo.json").write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        comparar(a, b)
    assert _codigo(f) in str(exc.value) and "TITULO-SECRETO-XYZ" not in str(exc.value)
