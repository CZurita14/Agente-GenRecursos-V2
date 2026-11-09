"""Plan de simulación: cupos por facultad y carrera, con códigos estables y marcados."""
from collections import Counter
from pathlib import Path

import yaml

from ciencia_datos.origen import PREFIJO_SIMULADO, es_simulado
from ciencia_datos.sim_plan import Cupo, cuota, cupos

CATALOGO = Path(__file__).resolve().parents[2] / "kb" / "catalogo.yaml"


def _catalogo_con_carrera_nueva(tmp_path, sigla, carrera):
    """Copia del catálogo real con una carrera de grado añadida a la facultad `sigla`."""
    datos = yaml.safe_load(CATALOGO.read_text(encoding="utf-8"))
    for facultad in datos["facultades"]:
        if facultad["sigla"] == sigla:
            facultad["carreras"] = [*facultad["carreras"], {"nombre": carrera, "nivel": "grado"}]
    ruta = tmp_path / "catalogo.yaml"
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    return ruta


def test_cuotas_del_catalogo_real():
    lista = cupos(CATALOGO)
    por_facultad = Counter(c.sigla for c in lista)
    assert por_facultad == {"FING": 36, "FADA": 24, "FACEAN": 42, "FCED": 24,
                            "FCSBH": 24, "FCSH": 24, "FJCP": 24}
    assert len(lista) == 198
    assert len({c.carrera for c in lista}) == 29


def test_excluye_posgrado_y_facultad_sin_carreras():
    lista = cupos(CATALOGO)
    assert not any(c.carrera.startswith("Maestría") for c in lista)
    assert "FCMA" not in {c.sigla for c in lista}


def test_los_primeros_20_cubren_las_7_facultades_sin_repetir_carrera():
    primeros = cupos(CATALOGO)[:20]
    assert len({c.sigla for c in primeros}) == 7
    assert len({c.carrera for c in primeros}) == 20


def test_los_codigos_son_unicos_y_marcados():
    codigos = [c.codigo for c in cupos(CATALOGO)]
    assert len(set(codigos)) == len(codigos)
    assert all(es_simulado(c) for c in codigos)
    assert not es_simulado("INF-101")


def test_agregar_una_carrera_conserva_los_codigos_de_las_demas(tmp_path):
    antes = {c.codigo for c in cupos(CATALOGO)}
    ruta = _catalogo_con_carrera_nueva(tmp_path, sigla="FCMA", carrera="Gestión Ambiental")
    despues = {c.codigo for c in cupos(ruta)}
    assert antes < despues
    assert sum(1 for c in cupos(ruta) if c.sigla == "FCMA") == 24


def test_forma_del_codigo_y_cuota():
    c = Cupo("FING", "FING", "Contabilidad y Auditoría", 7)
    assert c.codigo == "SIM-FING-CONTABILIDAD-Y-AUDITORIA-007"
    assert PREFIJO_SIMULADO == "SIM-"
    assert [cuota(n) for n in (1, 3, 6, 7)] == [24, 24, 36, 42]
