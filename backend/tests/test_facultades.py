"""Perfiles de facultad, estilo por carrera y enrutamiento (spec §4.1-§4.3)."""
from pathlib import Path

import pytest

from app.agentes.facultades import (
    cargar_catalogo,
    cargar_perfiles,
    enrutar,
    estilo_para,
    normalizar,
)

RAIZ = Path(__file__).resolve().parents[2]
DIRECTORIO_AGENTES = RAIZ / "agentes"
RUTA_CATALOGO = RAIZ / "kb" / "catalogo.yaml"


@pytest.fixture(scope="module")
def perfiles():
    return cargar_perfiles(DIRECTORIO_AGENTES)


@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo(RUTA_CATALOGO)


@pytest.fixture(scope="module")
def fing(perfiles):
    return perfiles["ingenierias"]


def test_normalizar_quita_tildes_mayusculas_y_espacios():
    assert normalizar("  facultad  de ingenierías ") == "FACULTAD DE INGENIERIAS"
    assert normalizar("Tecnologías de la Información") == "TECNOLOGIAS DE LA INFORMACION"


def test_enrutar_variantes_de_la_facultad_de_ingenierias(perfiles, catalogo):
    assert enrutar("FACULTAD DE INGENIERIAS", catalogo, perfiles) == "ingenierias"
    assert enrutar("Facultad de Ingenierías", catalogo, perfiles) == "ingenierias"
    assert enrutar("facultad  de ingenierías", catalogo, perfiles) == "ingenierias"


def test_enrutar_facultad_desconocida_va_a_general(perfiles, catalogo):
    assert enrutar("FACULTAD DE ASTRONOMÍA", catalogo, perfiles) == "general"


def test_cargar_perfiles_exige_general(tmp_path):
    (tmp_path / "ingenierias.yaml").write_text(
        (DIRECTORIO_AGENTES / "ingenierias.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        cargar_perfiles(tmp_path)


def test_estilo_por_carrera(fing):
    assert "JASP" in estilo_para(fing, "SOFTWARE").software_habitual


def test_estilo_por_carrera_ignora_acentos_y_mayusculas(fing):
    assert estilo_para(fing, "Software") == estilo_para(fing, "SOFTWARE")


def test_carrera_sin_ajustes_hereda(fing):
    assert estilo_para(fing, "CIVIL") == fing.estilo


def test_carrera_desconocida(fing):
    assert estilo_para(fing, "ASTRONAUTICA") == fing.estilo


def test_escenarios_de_software(perfiles):
    estilo = estilo_para(perfiles["ingenierias"], "SOFTWARE")
    assert len(estilo.escenarios) >= 6
    assert estilo_para(perfiles["general"], "X").escenarios == []
