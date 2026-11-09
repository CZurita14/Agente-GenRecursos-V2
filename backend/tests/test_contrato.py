"""Contrato JSON del SGA: entrada del modelo y validación de integridad."""
import copy
import json
from pathlib import Path

import pytest

from app.silabo.integridad import SilaboInvalido, cargar_silabo
from app.silabo.modelo import SilaboUTI

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLO = RAIZ / "docs" / "api-silabo" / "ejemplo-minimo.json"
FIXTURE = Path(__file__).parent / "fixtures" / "silabo_datos.json"


def _ejemplo() -> dict:
    return json.loads(EJEMPLO.read_text(encoding="utf-8"))


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
