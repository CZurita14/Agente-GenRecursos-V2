"""Contrato v2.0 del sílabo y Escala general de evaluación de sílabos (UTI, 23/10/2026)."""
import copy
import json
from pathlib import Path

import pytest

from app.sga import contrato_v2
from app.sga.traductor import a_contrato, a_contrato_con_avisos
from app.silabo.escala import calcular, catalogo, revision_automatica, vacio, validar_evaluacion
from app.silabo.integridad import cargar_silabo

DOCS = Path(__file__).resolve().parents[2] / "docs" / "api-silabo"


def _leer(nombre: str) -> dict:
    return json.loads((DOCS / nombre).read_text(encoding="utf-8"))


def _p(evaluacion, codigo, **filtro):
    return [p for p in evaluacion["puntos"] if p["codigo"] == codigo
            and all(p.get(k) == v for k, v in filtro.items())]


# --- contrato v2.0 ------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", ["ejemplo-v2-completo.json", "ejemplo-v2-minimo.json"])
def test_los_ejemplos_v2_entran_al_sistema(nombre):
    d = _leer(nombre)
    assert contrato_v2.reglas(d) == []
    contrato, _ = a_contrato_con_avisos(d)
    assert cargar_silabo(contrato).proyecto_formativo.codigo == d["proyecto_formativo"]["codigo"]


def test_v2_y_v1_dan_el_mismo_silabo_interno():
    v1 = a_contrato(_leer("ejemplo-completo.json"))
    v2 = a_contrato(_leer("ejemplo-v2-completo.json"))
    assert v2.pop("metodologias")[0] == "Clase invertida"
    v1.pop("metodologias")
    assert v2.pop("pis")["aporte"].startswith(v1.pop("pis")["aporte"])  # el v2 detalla fechas y coordinación
    assert v1 == v2


def test_adaptador_no_muta_y_quita_pis_no_aplicable():
    d = _leer("ejemplo-v2-minimo.json")
    antes = copy.deepcopy(d)
    v1 = contrato_v2.a_v1(d)
    assert d == antes
    assert "pis" not in v1 and "creditos" not in v1["proyecto_formativo"] and v1["metodologias"] == ["Clase invertida"]
    for raro in ({"contrato": "2.0", "metodologias": "x", "pis": 3}, {"contrato": "2.0", "metodologias": {"complementarias": [1]}}):
        contrato_v2.a_v1(raro)


def test_reglas_v2():
    d = _leer("ejemplo-v2-completo.json")
    d["resultados_aprendizaje"][1]["id"] = "RA3"
    d["metodologias"]["complementarias"][1]["tipo"] = "aprendizaje_basado_problemas"
    del d["inclusion"]
    assert contrato_v2.reglas(d) == ["inclusion: falta", "resultados_aprendizaje[1].id: debe ser RA2",
                                     "metodologias.complementarias[1].tipo: repetido"]


def test_raiz_obligatoria_igual_al_esquema():
    assert list(contrato_v2.RAIZ_OBLIGATORIA) == _leer("silabo-api.v2.schema.json")["required"]


def test_esquemas_v2_aceptan_los_ejemplos_y_rechazan_v1():
    jsonschema = pytest.importorskip("jsonschema")
    sil = jsonschema.Draft202012Validator(_leer("silabo-api.v2.schema.json"), format_checker=jsonschema.FormatChecker())
    ev = jsonschema.Draft202012Validator(_leer("evaluacion-silabo.schema.json"), format_checker=jsonschema.FormatChecker())
    for n in ("ejemplo-v2-completo.json", "ejemplo-v2-minimo.json"):
        assert not list(sil.iter_errors(_leer(n))), n
        assert not list(ev.iter_errors(revision_automatica(_leer(n), fecha="2026-11-18"))), n
    assert not list(ev.iter_errors(_leer("ejemplo-evaluacion.json")))
    assert list(sil.iter_errors(_leer("ejemplo-completo.json")))


# --- catálogo de la escala ------------------------------------------------------------------


def test_catalogo_de_la_escala():
    c = catalogo()
    assert len(c["puntos"]) == 60
    assert [(a["codigo"], a["peso"]) for a in c["apartados"]] == [
        ("I", 5), ("II", 5), ("III", 20), ("IV", 30), ("V", 30), ("VI", 5), ("VII", 5)]
    assert [n["valor"] for n in c["niveles"]] == [1, 2, 3, 4, 5]
    na = {p["codigo"] for p in c["puntos"] if p["admite_na"]}
    assert na == {"III.5", "III.6", "III.7", "III.8", "III.9", "III.10", "III.12", "III.13", "III.19", "III.20",
                  *(f"III.{n}" for n in range(22, 30)), "V.12"}
    assert {p["codigo"] for p in c["puntos"] if p["fuera_del_contrato"]} == {"I.1", "VII.1"}
    assert sum(p["repetir_por"] == "momento" for p in c["puntos"]) == 15


def test_esquema_de_evaluacion_enumera_el_catalogo():
    esquema = _leer("evaluacion-silabo.schema.json")
    assert esquema["$defs"]["punto"]["properties"]["codigo"]["enum"] == [p["codigo"] for p in catalogo()["puntos"]]


# --- revisión automática y cálculo -----------------------------------------------------------


def test_revision_automatica_del_minimo():
    d = _leer("ejemplo-v2-minimo.json")
    ev = revision_automatica(d, fecha="2026-11-18")
    assert validar_evaluacion(ev, d) == []
    assert _p(ev, "III.4")[0]["valor"] == "ND"
    assert _p(ev, "III.4")[0]["sugerencia"] == "Sin dato en: habilidades_blandas"
    assert [p["valor"] for p in _p(ev, "III.12")] == [None, "NA", "NA", "NA"]
    assert _p(ev, "III.13", ra="RA1")[0]["valor"] == "ND"
    assert {p["valor"] for c in ("III.19", "III.20", "V.12") for p in _p(ev, c)} == {"NA"}
    assert {p["valor"] for n in range(22, 30) for p in _p(ev, f"III.{n}")} == {"NA"}
    assert _p(ev, "III.21")[0]["valor"] == "ND"  # la clase invertida no admite NA
    assert _p(ev, "IV.12", momento=1)[0]["valor"] == "ND"  # política de IA vacía: ND, nunca NA
    assert _p(ev, "I.1")[0]["fuente"] == "evaluador" and _p(ev, "I.1")[0]["valor"] is None
    assert ev["completa"] is False and ev["total"] is None


def test_pendientes_automaticos():
    d = _leer("ejemplo-v2-completo.json")
    d["metodologias"]["complementarias"][1].update(aplicada_en=[], justificacion="")
    d["metodologias"]["complementarias"][0]["aplicada_en"].append("M9-S9")
    d["evaluacion"]["calificacion"]["componentes"][0]["porcentaje"] = 20
    d["momentos"][1]["sesiones"][0]["fecha"] = "2026-12-20"
    ev = revision_automatica(d, fecha="2026-11-18")
    assert _p(ev, "III.22")[0]["pendiente"] and "no existen" in _p(ev, "III.22")[0]["sugerencia"]
    assert _p(ev, "III.26")[0]["sugerencia"] == ("selección sin decisión pedagógica (justificacion vacía); "
                                                 "no se refleja en ninguna actividad (aplicada_en vacía)")
    assert _p(ev, "V.10")[0]["pendiente"]
    assert _p(ev, "IV.2", momento=2)[0]["pendiente"] and not _p(ev, "IV.2", momento=1)[0]["pendiente"]
    assert ev["apartados"]["III"]["pendientes"] == 2 and ev["apartados"]["IV"]["pendientes"] == 1


def _todo(evaluacion, valor):
    for p in evaluacion["puntos"]:
        if p["valor"] is None:
            p["valor"] = valor
    evaluacion.update(calcular(evaluacion["puntos"]))
    return evaluacion


def test_formula_de_la_escala():
    d = _leer("ejemplo-v2-completo.json")
    ev = _todo(revision_automatica(d, fecha="2026-11-18"), 5)
    assert ev["total"] == 100.0 and ev["completa"]
    iv = ev["apartados"]["IV"]
    assert (iv["maximo"], iv["puntos"], iv["aplicables"]) == (150, 150, 30)  # 75 por momento
    iii = ev["apartados"]["III"]
    # III: 29 preguntas + 3 repeticiones de III.12/III.13 por RA; NA: emprendimiento, RA3, RA4 (x2) y 6 metodologías
    assert (iii["na"], iii["aplicables"], iii["maximo"]) == (11, 24, 120)
    # Un ND vale cero y cuenta en el máximo; un NA sale del máximo
    p = _p(ev, "VI.1")[0]
    p["valor"] = "ND"
    assert calcular(ev["puntos"])["apartados"]["VI"]["resultado"] == 0.0
    p["valor"] = 3
    assert calcular(ev["puntos"])["apartados"]["VI"]["resultado"] == 3.0  # 3 ÷ 5 × 5 %
    _p(ev, "II.1")[0]["valor"] = 2
    r = calcular(ev["puntos"])
    assert r["apartados"]["II"]["resultado"] == 2.0 and r["total"] == 95.0  # 100 − 2 (VI) − 3 (II)


def test_ejemplo_de_evaluacion_cuadra():
    ev = _leer("ejemplo-evaluacion.json")
    assert validar_evaluacion(ev, _leer("ejemplo-v2-completo.json")) == []
    assert ev["total"] == round(sum(a["resultado"] for a in ev["apartados"].values()), 2)


def test_validar_evaluacion_detecta_errores():
    d = _leer("ejemplo-v2-completo.json")
    ev = _leer("ejemplo-evaluacion.json")
    malo = copy.deepcopy(ev)
    malo["puntos"].append(copy.deepcopy(malo["puntos"][0]))
    malo["puntos"].pop(5)
    malo["total"] = 99.0
    fallos = validar_evaluacion(malo, d)
    assert "puntos ('I.1', None, None): repetido" in fallos
    assert any(f.endswith(": falta") for f in fallos)
    assert "total: no coincide con el cálculo de la escala" in fallos


def test_vacio():
    assert vacio("  ") and vacio([]) and vacio({"aplica": True, "descripcion": "", "justificacion_na": "x"})
    assert not vacio(0) and not vacio(False) and not vacio({"descripcion": "", "ods": [3]})


# --- ajustes por la plantilla de sílabo 2026 (docs/api-silabo/plantilla-2026.md) ---------------


@pytest.mark.parametrize("valor", ["", "Gobernanza ética de tecnologías digitales e ia",
                                   "  PENSAMIENTO SOCIOCRITICO Y SISTEMICO PARA LA TOMA DE DECISIONES ESTRATEGICAS "])
def test_metacompetencia_del_catalogo_sin_importar_mayusculas_ni_tildes(valor):
    d = _leer("ejemplo-v2-completo.json")
    d["metacompetencia"] = valor
    assert contrato_v2.reglas(d) == []


def test_metacompetencia_fuera_del_catalogo():
    d = _leer("ejemplo-v2-completo.json")
    d["metacompetencia"] = "Trabaja en equipo"
    assert contrato_v2.reglas(d) == ["metacompetencia: no es una de las 5 del catálogo institucional"]


def test_metacompetencia_queda_con_su_forma_oficial():
    d = _leer("ejemplo-v2-completo.json")
    d["metacompetencia"] = "gobernanza etica de tecnologias digitales e IA"
    assert contrato_v2.a_v1(d)["metacompetencia"] == "Gobernanza ética de tecnologías digitales e IA"
    assert len(contrato_v2.METACOMPETENCIAS) == 5


def test_inclusion_es_un_texto():
    d = _leer("ejemplo-v2-completo.json")
    assert isinstance(d["inclusion"], str) and d["inclusion"]
    assert isinstance(_leer("ejemplo-v2-minimo.json")["inclusion"], str)
