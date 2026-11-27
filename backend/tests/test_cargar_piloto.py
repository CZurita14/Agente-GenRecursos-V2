"""Carga de sílabos piloto en la cuenta de un docente del SGA simulado."""
import json

import pytest

from ciencia_datos import cargar_piloto


def test_carga_sin_duplicar(tmp_path, monkeypatch):
    origen = tmp_path / "pdf"
    origen.mkdir()
    for n in ("a.pdf", "b.pdf", "c.pdf"):
        (origen / n).write_bytes(b"%PDF")
    monkeypatch.setattr(cargar_piloto, "leer_silabo_v2", lambda datos: datos)
    lecturas = iter([{"portada": {"pf_codigo": "B26-SOFT-3-11111-1", "pf_nombre": "Uno", "carrera": "SOFTWARE"}},
                     {"portada": {"pf_codigo": "B26-SOFT-3-11111-1", "pf_nombre": "Uno", "carrera": "SOFTWARE"}},
                     {"portada": {"pf_codigo": "", "pf_nombre": "Sin código"}}])
    monkeypatch.setattr(cargar_piloto, "desde_v2", lambda v2: next(lecturas))
    c = cargar_piloto.cargar(origen, tmp_path / "sga", "juntachristian")
    assert c["cargado"] == 2 and c["materia_nueva"] == 1 and c["materia_ya_existia"] == 1 and c["sin_codigo_pf"] == 1
    materias = json.loads((tmp_path / "sga/materias/juntachristian.json").read_text(encoding="utf-8"))
    assert materias == [{"carrera": "SOFTWARE", "codigo_pf": "B26-SOFT-3-11111-1", "estado": "ACTIVA",
                         "id_sga": "11111", "nombre": "Uno", "paralelo": "1"}]
    assert (tmp_path / "sga/sga_silabos/B26-SOFT-3-11111-1.json").exists()


def test_usuario_invalido(tmp_path):
    with pytest.raises(ValueError):
        cargar_piloto.cargar(tmp_path, tmp_path, "../otro")
