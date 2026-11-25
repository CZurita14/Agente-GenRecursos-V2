"""Norma IEEE en las referencias de la guía y bases bibliográficas por perfil."""
import pytest
from pydantic import ValidationError

from app.agentes.facultades import FuentesBibliograficas, cargar_perfiles
from app.config import RAIZ
from app.fuentes.ieee import autores_scholar, numeracion, referencia_silabo, referencia_web, renumerar


@pytest.mark.parametrize("apa, ieee", [
    ("Walpole, R. E., Myers, R. H., & Myers, S. L. (2012). Probabilidad y estadística para ingeniería. Pearson.",
     "R. E. Walpole, R. H. Myers y S. L. Myers, Probabilidad y estadística para ingeniería, Pearson, 2012."),
    ("Pérez, J. (2020). Usabilidad móvil. Revista de Ingeniería, 12(3), 45-60. https://doi.org/10.1234/abc",
     "J. Pérez, «Usabilidad móvil», Revista de Ingeniería, 12(3), 45-60, 2020. [En línea]. Disponible en: "
     "https://doi.org/10.1234/abc"),
    ("Chapra, S. C.; Canale, R. P. (2015). Métodos numéricos para ingenieros. McGraw-Hill.",
     "S. C. Chapra y R. P. Canale, Métodos numéricos para ingenieros, McGraw-Hill, 2015."),
    ("Matthias Steup; Ram Neta. (2024). Epistemology. Stanford University.",
     "M. Steup y R. Neta, Epistemology, Stanford University, 2024."),
    ("FERNÁNDEZ MARTÍNEZ, ANTONIO; TORRES BERMUDEZ, ALEX ARMANDO (2021). Gobierno de TI. Ra-Ma.",
     "A. FERNÁNDEZ MARTÍNEZ y A. A. TORRES BERMUDEZ, Gobierno de TI, Ra-Ma, 2021."),
    ("Texto sin forma APA", "Texto sin forma APA"),
])
def test_bibliografia_del_silabo_a_ieee(apa, ieee):
    assert referencia_silabo(apa) == ieee


def test_referencia_web_y_autores_de_scholar():
    assert autores_scholar("DE Vázquez, E Hernández…") == "D. E. Vázquez, E. Hernández et al."
    assert autores_scholar("A Uno, B Dos, C Tres") == "A. Uno, B. Dos y C. Tres"
    f = {"titulo": "Widgets", "autores": "RE Walpole", "revista": "IEEE Latin America", "anio": "2018",
         "enlace": "https://ieeexplore.ieee.org/x"}
    assert referencia_web(f) == ("R. E. Walpole, «Widgets», IEEE Latin America, 2018. [En línea]. "
                                 "Disponible en: https://ieeexplore.ieee.org/x")


def test_numeracion_por_orden_de_aparicion():
    orden = numeracion(["Según [F2] y [B1].", "Otra vez [F2], luego [B3]."])
    assert orden == {"F2": 1, "B1": 2, "B3": 3}
    assert renumerar("Ver [B1], [F2] y [F9].", orden) == "Ver [2], [1] y [F9]."


def test_bases_por_perfil():
    perfiles = cargar_perfiles(RAIZ / "agentes")
    fb = perfiles["ingenierias"].fuentes_bibliograficas
    assert fb.bases == ["scopus", "google_scholar", "scielo", "repositorios"] and fb.desde == 2019 and fb.norma == "IEEE"
    assert perfiles["general"].fuentes_bibliograficas.bases == ["google_scholar"]
    with pytest.raises(ValidationError):
        FuentesBibliograficas(bases=["scopus", "biblioteca_inventada"])
