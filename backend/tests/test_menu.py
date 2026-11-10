"""Menú por semana y día (§8.1, criterio 2) y versiones del sílabo (§2.2)."""
import json
from datetime import date
from pathlib import Path

import pytest

from app.sga.traductor import a_contrato
from app.silabo.integridad import cargar_silabo
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


FIXTURES = Path(__file__).parent / "fixtures"


# Semanas esperadas de cada sílabo simulado del SGA (criterio 2): se contaron una vez a partir de los
# `semana_periodo` de sus sesiones. Los tres traen las sesiones en las semanas 2, 3 y 4 del período
# (6 clases en total), igual que `silabo_datos.json`; por eso el menú debe tener 3 semanas.
@pytest.mark.parametrize("ruta, semanas, clases", [
    ("sga/sga_silabos/S91-SIMU-3-90001-9001.json", 3, 6),
    ("sga/sga_silabos/S91-SIMU-3-90002-9002.json", 3, 6),
    ("sga/sga_silabos/S91-SIMU-2-90003-9003.json", 3, 6),
])
def test_criterio_2_silabos_simulados_del_sga(ruta, semanas, clases):
    silabo = cargar_silabo(a_contrato(json.loads((FIXTURES / ruta).read_text(encoding="utf-8"))))
    menu = construir_menu(silabo)
    assert len(menu) == semanas and sum(len(s.clases) for s in menu) == clases


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
