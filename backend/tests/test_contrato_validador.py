"""Contrato definitivo: el JSON del Validador de Sílabos (silabo-api/0.1.0) tal cual.

Lo que se prueba: el JSON del validador entra al sistema y produce el mismo sílabo interno, y con
él las mismas herramientas, que el contrato 2.0 que usaba el Generador.
"""
import copy
import json
from pathlib import Path

import pytest

from app.sga import contrato_validador as cv
from app.sga.traductor import a_contrato, a_contrato_con_avisos
from app.silabo.escala import revision_automatica
from app.silabo.integridad import cargar_silabo
from ciencia_datos.migrar_validador import desde_v2

DOCS = Path(__file__).resolve().parents[2] / "docs" / "api-silabo"
SGA = Path(__file__).parent / "fixtures" / "sga" / "sga_silabos"


def _leer(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _ejemplo():
    return _leer(DOCS / "silabo-api-0.1.0.ejemplo.json")


def test_el_ejemplo_del_validador_entra_tal_cual():
    v = _ejemplo()
    assert cv.es_validador(v) and cv.reglas(v) == []
    contrato, avisos = a_contrato_con_avisos(v)
    s = cargar_silabo(contrato)
    assert avisos == []
    assert s.proyecto_formativo.codigo == v["portada"]["pf_codigo"]
    assert s.metacompetencia == "Pensamiento sociocrítico y sistémico para la toma de decisiones estratégicas"
    assert [m.numero for m in s.momentos] == [1, 2]
    assert s.momentos[0].sesiones[0].id == "M1-S1"
    assert s.proyecto_formativo.horario[0].model_dump() == {"dia": "lunes", "inicio": "08:00", "fin": "08:59"}
    assert s.momentos[1].politica_ia == ""  # null en el validador: el documento no tiene ese dato


def test_no_muta_la_entrada():
    v = _ejemplo()
    antes = copy.deepcopy(v)
    cv.a_interno(v)
    cv.a_v2(v)
    assert v == antes


@pytest.mark.parametrize("nombre", ["ejemplo-v2-completo.json", "ejemplo-v2-minimo.json"])
def test_mismo_silabo_interno_que_el_2_0(nombre):
    g = _leer(DOCS / nombre)
    directo = cargar_silabo(a_contrato(g)).model_dump(mode="json")
    por_validador = cargar_silabo(a_contrato(desde_v2(g))).model_dump(mode="json")
    assert por_validador == directo


@pytest.mark.parametrize("ruta", sorted(SGA.glob("*.json")), ids=lambda p: p.stem)
def test_los_silabos_del_sga_simulado_estan_en_el_contrato_del_validador(ruta):
    crudo = _leer(ruta)
    assert crudo["contrato"] == cv.VERSION and cv.reglas(crudo) == []
    cargar_silabo(a_contrato(crudo))


def test_horas_vacias_no_se_rellenan_con_cero():
    v = _ejemplo()
    v["momentos"][0]["sesiones"][0]["docente"]["horas"] = None
    v["presentacion"]["horas_total"] = None
    s = cargar_silabo(a_contrato(v))
    assert s.momentos[0].sesiones[0].docente.horas is None
    assert s.proyecto_formativo.horas is None


def test_fecha_de_sesion_vacia_se_aparta_con_aviso():
    v = _ejemplo()
    v["momentos"][0]["sesiones"].append(copy.deepcopy(v["momentos"][0]["sesiones"][0]) | {"numero": 2, "fecha_inicio": None, "fecha_fin": None})
    contrato, avisos = a_contrato_con_avisos(v)
    assert len(cargar_silabo(contrato).momentos[0].sesiones) == 1
    assert any("sin fecha programada" in a for a in avisos)


@pytest.mark.parametrize("cambio,fallo", [
    (lambda v: v.pop("mapa"), "mapa: falta"),
    (lambda v: v["mapa"].__setitem__("resultados_aprendizaje", []),
     "mapa.resultados_aprendizaje: el Generador necesita al menos un resultado de aprendizaje"),
    (lambda v: v.__setitem__("momentos", []), "momentos: el Generador necesita al menos un momento"),
    (lambda v: v["momentos"][1].__setitem__("sesiones", []), "momentos[1].sesiones: el Generador necesita al menos una sesión"),
    (lambda v: v["presentacion"].__setitem__("nivel", None), "presentacion.nivel: el Generador necesita el nivel"),
    (lambda v: v["portada"].__setitem__("pf_codigo", ""), "portada.pf_codigo: el Generador necesita el código del PF"),
    (lambda v: v["mapa"]["resultados_aprendizaje"][1].__setitem__("id", "RA1"), "mapa.resultados_aprendizaje[1].id: repetido"),
])
def test_requisitos_para_generar(cambio, fallo):
    v = _ejemplo()
    cambio(v)
    assert fallo in cv.reglas(v)


def test_lo_que_el_validador_acepta_y_el_generador_tambien():
    # Más de 4 RA, RA con salto o una metacompetencia fuera del catálogo: el validador los diagnostica;
    # el Generador no los necesita para generar, así que tampoco los rechaza.
    v = _ejemplo()
    ra = v["mapa"]["resultados_aprendizaje"]
    v["mapa"]["resultados_aprendizaje"] = ra + [dict(ra[0], id=f"RA{i}") for i in (4, 5, 6)]
    v["mapa"]["metacompetencias"][0]["texto"] = "Otra metacompetencia"
    assert cv.reglas(v) == []
    cargar_silabo(a_contrato(v))


def test_privados_se_descartan_sin_leerlos():
    v = _ejemplo()
    v.update(docente="MARCA-PRIVADA", correo="falso@ejemplo.test", firmas=["MARCA-PRIVADA"])
    v["portada"]["docente"] = "MARCA-PRIVADA"
    v["momentos"][0]["sesiones"][0]["correo"] = "MARCA-PRIVADA"
    salida = json.dumps(a_contrato(v), ensure_ascii=False)
    assert "MARCA-PRIVADA" not in salida and "falso@" not in salida


def test_escala_sobre_el_json_del_validador():
    g = cv.a_v2(_ejemplo())
    ev = revision_automatica(g, fecha="2026-11-24")
    nd = {p["codigo"] for p in ev["puntos"] if p["valor"] == "ND"}
    assert {"V.5", "V.12", "III.21"} <= nd          # el contrato del validador no trae esos apartados
    assert "III.4" not in nd and "III.11" not in nd  # habilidades blandas e inclusión sí vienen
