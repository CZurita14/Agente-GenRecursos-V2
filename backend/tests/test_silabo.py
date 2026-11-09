"""Contrato SilaboUTI y contexto por clase."""
import pytest
from pydantic import ValidationError

from app.silabo.contexto import contexto_clase
from app.silabo.modelo import SilaboUTI


def test_fixture_valida(silabo):
    assert silabo.proyecto_formativo.codigo == "B26-SOFT-3-56146-1727"


def test_rechaza_campos_personales(datos):
    datos["docente"] = {"correo": "x@uti.edu.ec"}
    with pytest.raises(ValidationError):
        SilaboUTI.model_validate(datos)


def test_contexto_m2_s1(silabo):
    c = contexto_clase(silabo, "M2-S1")
    assert [r.id for r in c.ra] == ["RA2"] and c.nivel == 3


def test_evidencia_del_momento_es_entregable(silabo):
    # §9.4: la evidencia del momento se protege aunque las sesiones no listen entregables.
    c = contexto_clase(silabo, "M3-S4")
    momento = next(m for m in silabo.momentos if any(s.id == "M3-S4" for s in m.sesiones))
    assert c.entregables_momento[0] == momento.evidencia


def test_clases_con_mismo_contenido_difieren_en_actividades(silabo):
    a, b = contexto_clase(silabo, "M2-S1"), contexto_clase(silabo, "M2-S2")
    assert a.contenidos == b.contenidos
    assert a.actividades != b.actividades


def test_latex_se_conserva(silabo):
    c = contexto_clase(silabo, "M3-S3")
    assert "$H_0" in " ".join(c.actividades + c.contenidos)


def test_clase_inexistente(silabo):
    with pytest.raises(KeyError):
        contexto_clase(silabo, "M9-S9")


def test_modelos_inmutables(silabo):
    with pytest.raises(ValidationError):
        silabo.carrera = "OTRA"


def test_competencia_pf_vacia_aceptada(silabo):
    assert silabo.competencia_pf == ""


def test_semana_del_periodo(silabo):
    assert contexto_clase(silabo, "M3-S3").fecha.isoformat() == "2026-10-28"
    sesion = silabo.momentos[1].sesiones[2]
    assert sesion.semana_periodo == 4


def test_contexto_incluye_politica_rubrica_y_problema(silabo):
    c = contexto_clase(silabo, "M3-S4")
    assert c.politica_ia and c.rubrica and c.problema.reto
    assert c.codigo_pf == "B26-SOFT-3-56146-1727"


def test_contexto_no_comparte_objetos_mutables(silabo):
    a = contexto_clase(silabo, "M2-S1")
    b = contexto_clase(silabo, "M2-S2")
    original = dict(silabo.momentos[1].rubrica[0].niveles)
    a.rubrica[0].niveles["x"] = "mutado"
    assert silabo.momentos[1].rubrica[0].niveles == original
    assert "x" not in b.rubrica[0].niveles


def test_contexto_rechaza_extras_y_es_inmutable(silabo):
    c = contexto_clase(silabo, "M2-S1")
    with pytest.raises(ValidationError):
        c.clase_id = "otro"
    with pytest.raises(ValidationError):
        type(c).model_validate({**c.model_dump(), "extra": 1})


def test_extra_forbid_en_modelos_anidados(datos):
    d = {**datos, "proyecto_formativo": {**datos["proyecto_formativo"], "docente": "x"}}
    with pytest.raises(ValidationError):
        SilaboUTI.model_validate(d)
    momentos = [dict(m) for m in datos["momentos"]]
    momentos[0]["sesiones"] = [{**momentos[0]["sesiones"][0], "correo": "x"}, *momentos[0]["sesiones"][1:]]
    with pytest.raises(ValidationError):
        SilaboUTI.model_validate({**datos, "momentos": momentos})


def test_inmutable_en_modelos_anidados(silabo):
    with pytest.raises(ValidationError):
        silabo.proyecto_formativo.nombre = "otro"
    with pytest.raises(ValidationError):
        silabo.momentos[0].sesiones[0].id = "otro"
