"""leer_silabo con los dos PDF reales (criterios 1 y 5). Se omiten si Silabos/ no está."""
import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.silabo.lector import SilaboIlegible, leer_silabo
from tests.lector.conftest import datos_personales, fugas

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "silabo_datos.json"


def _sesiones(s):
    return {x.id: x for m in s.momentos for x in m.sesiones}


def test_criterio_1_datos(pdf_real):
    s = leer_silabo(pdf_real("datos"))
    assert len(s.momentos) == 4
    fechas = {k: v.fecha for k, v in _sesiones(s).items()}
    assert fechas == {
        "M1-S1": date(2026, 10, 7), "M1-S2": date(2026, 10, 8), "M2-S1": date(2026, 10, 14),
        "M2-S2": date(2026, 10, 15), "M3-S1": date(2026, 10, 21), "M3-S2": date(2026, 10, 22),
        "M3-S3": date(2026, 10, 28), "M3-S4": date(2026, 10, 29), "M4-S1": date(2026, 11, 4),
        "M4-S2": date(2026, 11, 5), "M4-S3": date(2026, 11, 11)}
    assert _sesiones(s)["M3-S4"].semana_periodo == 4
    assert (s.carrera, s.proyecto_formativo.codigo, s.proyecto_formativo.nivel) == (
        "SOFTWARE", "B26-SOFT-3-56146-1727", 3)
    for m in s.momentos:
        assert m.rubrica and all(set(f.niveles) == {"receptivo", "resolutivo", "reflexivo", "critico", "cocreativo"}
                                 for f in m.rubrica)


def test_criterio_1_tic(pdf_real):
    s = leer_silabo(pdf_real("tic"))
    assert len(s.momentos) == 4 and len(_sesiones(s)) == 6
    assert s.momentos[0].ra == ["RA1", "RA2"]
    assert {"PAE 1", "EVALUACIÓN COGNITIVA 1"} <= set(_sesiones(s)["M2-S2"].entregables)
    assert s.competencia_pf == ""


@pytest.mark.parametrize("nombre", ["datos", "tic"])
def test_criterio_5_sin_datos_personales(pdf_real, nombre):
    datos = pdf_real(nombre)
    volcado = leer_silabo(datos).model_dump_json()
    assert "@" not in volcado and "orcid" not in volcado.lower()
    assert not re.search(r"\d{9,}", volcado), "hay una secuencia de 9 o más dígitos"
    n = fugas(volcado, datos_personales(datos))
    assert n == 0, f"{n} datos personales en el SilaboUTI"


def test_fixture_coincide_con_el_lector(pdf_real):
    leido = json.loads(leer_silabo(pdf_real("datos")).model_dump_json())
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for m in fixture["momentos"]:
        assert next(x for x in leido["momentos"] if x["numero"] == m["numero"]) == m
    assert leido["rubrica_producto_final"] == fixture["rubrica_producto_final"]


def test_pdf_invalido_da_silabo_ilegible():
    with pytest.raises(SilaboIlegible):
        leer_silabo(b"no es pdf")


def test_sin_sesiones_fechadas_da_silabo_ilegible(pdf_real, monkeypatch):
    import app.silabo.lector.ensamblar as ensamblar
    monkeypatch.setattr(ensamblar, "leer_momentos", lambda tablas, inicio: [])
    with pytest.raises(SilaboIlegible) as e:
        leer_silabo(pdf_real("datos"))
    assert "sesión fechada" in e.value.motivo


def test_errores_internos_no_filtran_texto_del_pdf(pdf_real, monkeypatch):
    import app.silabo.lector.ensamblar as ensamblar
    def falla(*a, **k):
        raise ValueError("could not convert string to float: 'TEXTO DEL PDF'")
    monkeypatch.setattr(ensamblar, "leer_momentos", falla)
    with pytest.raises(SilaboIlegible) as e:
        leer_silabo(pdf_real("datos"))
    assert "TEXTO DEL PDF" not in str(e.value)


def test_politica_tic_m3(pdf_real):
    # Defecto hallado en el P3b: la fila de la política de TIC M3 empieza al pie de página.
    s = leer_silabo(pdf_real("tic"))
    assert all(m.politica_ia for m in s.momentos)
    m3 = next(m for m in s.momentos if m.numero == 3)
    assert m3.politica_ia.startswith("SE PERMITE LA IA COMO APOYO PARA IDENTIFICAR RIESGOS")
