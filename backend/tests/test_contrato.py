"""Contrato JSON del SGA: entrada del modelo y validación de integridad."""
import copy
import json
from pathlib import Path

import pytest

from app.sga.traductor import a_contrato, a_contrato_con_avisos
from app.silabo.integridad import SilaboInvalido, cargar_silabo
from app.silabo.modelo import SilaboUTI

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLO = RAIZ / "docs" / "api-silabo" / "ejemplo-minimo.json"
FIXTURE = Path(__file__).parent / "fixtures" / "silabo_datos.json"


COMPLETO = RAIZ / "docs" / "api-silabo" / "ejemplo-completo.json"


def _crudo(ruta=EJEMPLO) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def _ejemplo() -> dict:
    """El ejemplo mínimo ya traducido: con id, semana y entregables derivados."""
    return a_contrato(_crudo())


# --- campos derivados y sesiones sin fecha (contrato v1.0) ---------------------------------


def test_el_minimo_no_trae_derivados_y_el_sistema_los_completa():
    sesion = _crudo()["momentos"][0]["sesiones"][0]
    assert not {"id", "semana_periodo", "entregables"} & set(sesion)
    s = cargar_silabo(a_contrato(_crudo())).momentos[0].sesiones[0]
    assert (s.id, s.semana_periodo, s.entregables) == ("M1-S1", 1, [])


def test_el_completo_entra_y_avisa_la_sesion_sin_fecha():
    contrato, avisos = a_contrato_con_avisos(_crudo(COMPLETO))
    s = cargar_silabo(contrato)
    assert avisos == ["momentos[0].sesiones[2].fecha: sin fecha programada; la sesión no se importó"]
    sesiones = [x for m in s.momentos for x in m.sesiones]
    assert [x.id for x in sesiones] == ["M1-S1", "M1-S2", "M2-S4"]
    assert [x.semana_periodo for x in sesiones] == [1, 1, 5]
    assert sesiones[0].entregables == ["PAE 1", "TAREA 1"] and sesiones[2].entregables == ["EVALUACIÓN COGNITIVA 1"]
    assert s.pis is not None and s.momentos[0].sesiones[0].docente.asincronica is not None


def test_lo_que_envia_el_sga_se_respeta():
    d = _crudo()
    d["momentos"][0]["sesiones"][0].update(id="M1-S7", semana_periodo=3, entregables=["Informe"])
    s = cargar_silabo(a_contrato(d)).momentos[0].sesiones[0]
    assert (s.id, s.semana_periodo, s.entregables) == ("M1-S7", 3, ["Informe"])


def test_traducir_no_muta_ni_falla_con_tipos_raros():
    d = _crudo()
    antes = copy.deepcopy(d)
    a_contrato(d)
    assert d == antes
    for raro in ({"momentos": "x"}, {"momentos": [None, {"sesiones": [3, {"fecha": 7}]}]}, {"periodo": 5, "momentos": []}):
        a_contrato(raro)  # no lanza: lo informa la validación


def test_si_todas_las_sesiones_van_sin_fecha_el_silabo_es_invalido():
    d = _crudo()
    d["momentos"][0]["sesiones"][0]["fecha"] = None
    with pytest.raises(SilaboInvalido) as e:
        cargar_silabo(a_contrato(d))
    assert "momentos[0].sesiones: vacío" in e.value.fallos


def test_esquema_json_acepta_los_ejemplos():
    jsonschema = pytest.importorskip("jsonschema")
    esquema = json.loads((RAIZ / "docs" / "api-silabo" / "silabo-api.schema.json").read_text(encoding="utf-8"))
    validador = jsonschema.Draft202012Validator(esquema, format_checker=jsonschema.FormatChecker())
    for ruta in (EJEMPLO, COMPLETO):
        assert not list(validador.iter_errors(_crudo(ruta))), ruta.name


def test_ejemplo_minimo_entra():
    assert isinstance(cargar_silabo(_ejemplo()), SilaboUTI)


def test_fixture_completo_igual():
    original = json.loads(FIXTURE.read_text(encoding="utf-8"))
    volcado = SilaboUTI.model_validate(original).model_dump(mode="json")
    assert cargar_silabo(volcado).model_dump(mode="json") == volcado


def _ra_inexistente(d):
    d["momentos"][0]["ra"] = ["RA99"]


def _id_formato(d):
    d["momentos"][0]["sesiones"][0]["id"] = "2-1"


def _id_repetido(d):
    s = d["momentos"][0]["sesiones"]
    s.append(copy.deepcopy(s[0]))


def _fecha_fuera(d):
    d["momentos"][0]["sesiones"][0]["fecha"] = "2030-01-01"


def _sin_sesiones(d):
    d["momentos"][0]["sesiones"] = []


def _contenido_vacio(d):
    d["momentos"][0]["sesiones"][0]["contenidos"][0] = ""


def _momento_repetido(d):
    m = copy.deepcopy(d["momentos"][0])
    d["momentos"].append(m)


@pytest.mark.parametrize("mutar,fallo", [
    (_ra_inexistente, "momentos[0].ra[0]: resultado de aprendizaje inexistente"),
    (_id_formato, "momentos[0].sesiones[0].id: debe ser M<momento>-S<n>"),
    (_id_repetido, "momentos[0].sesiones[1].id: repetido"),
    (_fecha_fuera, "momentos[0].sesiones[0].fecha: fuera del periodo"),
    (_sin_sesiones, "momentos[0].sesiones: vacío"),
    (_contenido_vacio, "momentos[0].sesiones[0].contenidos[0]: vacío"),
    (_momento_repetido, "momentos[1].numero: repetido"),
])
def test_integridad(mutar, fallo):
    d = _ejemplo()
    mutar(d)
    with pytest.raises(SilaboInvalido) as e:
        cargar_silabo(d)
    assert fallo in e.value.fallos


def test_campo_extra_rechazado():
    d = _ejemplo()
    d["correo_docente"] = "x@y.z"
    with pytest.raises(SilaboInvalido) as e:
        cargar_silabo(d)
    assert "correo_docente: extra_forbidden" in e.value.fallos


def test_errores_sin_valores():
    d = _ejemplo()
    d["correo_docente"] = "XYZ-SECRETO"
    d["momentos"][0]["titulo"] = 123
    d["momentos"][0]["ra"] = ["XYZ-SECRETO"]
    with pytest.raises(SilaboInvalido) as e:
        cargar_silabo(d)
    assert e.value.fallos
    assert "XYZ-SECRETO" not in " ".join(e.value.fallos) + str(e.value)

    d = _ejemplo()
    d["momentos"][0]["ra"] = ["XYZ-SECRETO"]
    d["momentos"][0]["sesiones"][0]["id"] = "XYZ-SECRETO"
    with pytest.raises(SilaboInvalido) as e:
        cargar_silabo(d)
    assert "XYZ-SECRETO" not in " ".join(e.value.fallos) + str(e.value)
