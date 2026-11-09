"""Menú por semana y día (§8.1, criterio 2) y versiones del sílabo (§2.2)."""
from datetime import date

import pytest

from app.silabo.menu import clases_cambiadas, construir_menu
from app.silabo.modelo import SilaboUTI


def test_menu_con_la_fixture(silabo):
    menu = construir_menu(silabo)
    assert [s.numero for s in menu] == [2, 3, 4]
    semana = menu[0]
    assert (semana.inicio, semana.fin) == (date(2026, 10, 12), date(2026, 10, 18))
    assert [(c.clase_id, c.dia, c.fecha) for c in semana.clases] == [
        ("M2-S1", "mie", date(2026, 10, 14)), ("M2-S2", "jue", date(2026, 10, 15))]
    assert semana.cierra_momentos == [2]
    assert menu[1].cierra_momentos == [] and menu[2].cierra_momentos == [3]
    clase = semana.clases[0]
    assert (clase.momento, clase.ra, clase.contenidos) == (2, ["RA2"], ["DISTRIBUCIONES ESTADÍSTICAS"])
    assert clase.momento_titulo.startswith("Planeación y Diseño")


def test_numero_de_clase_cronologico(silabo):
    numeros = [c.numero_clase for s in construir_menu(silabo) for c in s.clases]
    assert numeros == list(range(1, 7))


@pytest.mark.parametrize("nombre, semanas", [("datos", 6), ("tic", 4)])
def test_criterio_2_reales(nombre, semanas):
    from tests.lector.conftest import PDFS
    if not PDFS[nombre].exists():
        pytest.skip("PDF real no disponible en Silabos/ (no se versiona)")
    from app.silabo.lector import leer_silabo
    assert len(construir_menu(leer_silabo(PDFS[nombre].read_bytes()))) == semanas


def _con_cambios(silabo, version="1.0", contenido_m3_s2=None):
    datos = silabo.model_dump()
    datos["proyecto_formativo"]["version"] = version
    if contenido_m3_s2:
        for m in datos["momentos"]:
            for s in m["sesiones"]:
                if s["id"] == "M3-S2":
                    s["contenidos"] = [contenido_m3_s2]
    return SilaboUTI.model_validate(datos)


def test_version_marca_solo_lo_cambiado(silabo):
    assert clases_cambiadas(silabo, silabo) == set()
    # Una versión nueva cambia version_silabo en todos los contextos; eso solo no es un cambio de clase.
    assert clases_cambiadas(silabo, _con_cambios(silabo, version="2.0")) == set()
    assert clases_cambiadas(silabo, _con_cambios(silabo, "2.0", "OTRO CONTENIDO")) == {"M3-S2"}


def test_clase_nueva_cuenta_como_cambiada(silabo):
    datos = silabo.model_dump()
    nueva = dict(datos["momentos"][0]["sesiones"][-1], id="M2-S3", numero=3)
    datos["momentos"][0]["sesiones"].append(nueva)
    assert clases_cambiadas(silabo, SilaboUTI.model_validate(datos)) == {"M2-S3"}


def test_versiones_de_otra_asignatura(silabo):
    datos = silabo.model_dump()
    datos["proyecto_formativo"]["codigo"] = "OTRO-CODIGO"
    with pytest.raises(ValueError):
        clases_cambiadas(silabo, SilaboUTI.model_validate(datos))
