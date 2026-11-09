"""Herramientas sin IA (P3a, catálogo #12, #13, #15, #17): todo sale del sílabo."""
import pytest

from app.herramientas.sin_ia import HERRAMIENTAS_SIN_IA, NIVELES, generar_sin_ia
from app.silabo.modelo import SilaboUTI


def _momento(silabo, numero):
    return next(m for m in silabo.momentos if m.numero == numero)


def test_registro_y_ambitos():
    assert HERRAMIENTAS_SIN_IA == {"hoja_ruta": "asignatura", "autoevaluacion_rubrica": "momento",
                                   "autoevaluacion_final": "asignatura", "lista_evidencia": "momento",
                                   "rubrica_momento": "momento", "rubrica_final": "asignatura"}


def test_hoja_ruta_con_la_fixture(silabo):
    h = generar_sin_ia("hoja_ruta", silabo, "asignatura")
    assert (h["asignatura"], h["codigo"]) == (silabo.proyecto_formativo.nombre, silabo.proyecto_formativo.codigo)
    assert [s["numero"] for s in h["semanas"]] == [2, 3, 4]
    assert h["semanas"][0]["clases"][0]["clase_id"] == "M2-S1"
    assert [m["numero"] for m in h["momentos"]] == [2, 3]
    assert h["momentos"][0]["politica_ia"] == _momento(silabo, 2).politica_ia
    assert h["producto_final"] == silabo.problema.producto_final


def test_autoevaluacion_rubrica_m2(silabo):
    a = generar_sin_ia("autoevaluacion_rubrica", silabo, "M2")
    m = _momento(silabo, 2)
    assert (a["momento"], a["titulo"], a["evidencia"]) == (2, m.titulo, m.evidencia)
    assert a["niveles"] == list(NIVELES)
    assert [i["indicador"] for i in a["indicadores"]] == [f.indicador for f in m.rubrica]
    primero = a["indicadores"][0]
    assert primero["descriptores"] == {n: m.rubrica[0].niveles[n] for n in NIVELES}
    assert primero["para_subir"]["receptivo"] == m.rubrica[0].niveles["resolutivo"]
    assert primero["para_subir"]["cocreativo"] is None
    assert [r["id"] for r in a["ra"]] == m.ra
    assert a["politica_ia"] == m.politica_ia and a["instrucciones"]


def test_autoevaluacion_final(silabo):
    a = generar_sin_ia("autoevaluacion_final", silabo, "asignatura")
    assert [i["indicador"] for i in a["indicadores"]] == [f.indicador for f in silabo.rubrica_producto_final]
    assert a["evidencia"] == silabo.problema.producto_final
    assert [p["momento"] for p in a["politica_ia"]] == [2, 3]


def test_lista_evidencia_m3(silabo):
    lista = generar_sin_ia("lista_evidencia", silabo, "M3")
    m = _momento(silabo, 3)
    assert lista["evidencia"] == m.evidencia
    assert [i["indicador"] for i in lista["items"]] == [f.indicador for f in m.rubrica]
    assert lista["items"][0]["referencia_resolutivo"] == m.rubrica[0].niveles["resolutivo"]
    assert lista["entregables"] == sorted({e for s in m.sesiones for e in s.entregables})


def test_textos_salen_del_silabo(silabo):
    # Ningún indicador ni descriptor se inventa: todos aparecen literal en el sílabo.
    fuente = silabo.model_dump_json()
    for herramienta, ambito in (("autoevaluacion_rubrica", "M2"), ("autoevaluacion_final", "asignatura"),
                                ("lista_evidencia", "M3")):
        contenido = generar_sin_ia(herramienta, silabo, ambito)
        for item in contenido.get("indicadores", []) + contenido.get("items", []):
            assert item["indicador"] in fuente
            for texto in item.get("descriptores", {}).values():
                assert texto in fuente


def test_sin_rubrica_final_da_error(silabo):
    sin_final = SilaboUTI.model_validate({**silabo.model_dump(), "rubrica_producto_final": []})
    with pytest.raises(ValueError):
        generar_sin_ia("autoevaluacion_final", sin_final, "asignatura")


@pytest.mark.parametrize("herramienta, ambito", [
    ("autoevaluacion_rubrica", "M9"), ("lista_evidencia", "asignatura"), ("hoja_ruta", "M2"),
    ("autoevaluacion_rubrica", "M"), ("desconocida", "M2")])
def test_ambito_inexistente(silabo, herramienta, ambito):
    with pytest.raises(ValueError):
        generar_sin_ia(herramienta, silabo, ambito)
