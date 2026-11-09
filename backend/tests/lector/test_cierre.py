"""Rúbrica del producto final (V) y bibliografía (VI) (P2, Tarea 4)."""
from app.silabo.lector.cierre import leer_bibliografia, leer_rubrica_final

ENCABEZADO = ["Indicador", "Receptivo", "Resolutivo", "Reflexivo", "Crítico", "Cocreativo"]


def test_rubrica_final():
    tablas = [[["Rúbrica de la evidencia del desempeño central"], ["Expediente técnico…"]],
              [ENCABEZADO, ["Dataset depurado", "a", "b", "c", "d", "e"],
               ["Matrices", "f", "g", "h", "i", "j"]]]
    rubrica = leer_rubrica_final(tablas)
    assert [f["indicador"] for f in rubrica] == ["Dataset depurado", "Matrices"]
    assert rubrica[1]["niveles"]["cocreativo"] == "j"


def test_rubrica_final_partida_con_indicador_en_minuscula():
    # TIC: la fila 4 sigue en la página siguiente y su continuación trae texto en «Indicador».
    tablas = [[ENCABEZADO, ["4. Articulación con los", "Reconoce", "Describe", "Relaciona", "Fundamenta", "Mejora"]],
              [ENCABEZADO, ["demás proyectos\nformativos).", "relaciones", "entre sus", "con otros", "y articula", "la trazabilidad"],
               ["5. Gobernanza crítica", "k", "l", "m", "n", "o"]]]
    rubrica = leer_rubrica_final(tablas)
    assert [f["indicador"] for f in rubrica] == ["4. Articulación con los demás proyectos formativos).",
                                                 "5. Gobernanza crítica"]
    assert rubrica[0]["niveles"]["receptivo"] == "Reconoce relaciones"


TEXTO_VI = """VI. BIBLIOGRAFÍA
Bibliografía básica
BOLOGNA, EDUARDO. (2021). MÉTODOS ESTADÍSTICOS DE INVESTIGACIÓN. EDITORIAL BRUJAS.. https://elibro.
net/es/lc/utiec/titulos/106355
AUTORA UNO, AUTOR DOS. (2021). METODOLOGÍA, ESTADÍSTICA APLICADA E INSTRUMENTOS
EN NEUROPSICOLOGÍA. ENCUENTRO GRUPO EDITOR. https://search.ebscohost.com/login.aspx?
direct=true&db=e086sww
Bibliografía complementaria
JAIME MORENO, LUIS PUERTAS. (2022). Estudio de validez. CIENCIAMÉRICA. https://cienciamerica.edu.ec/index.php/uti/
article/view/385"""


def test_bibliografia_dos_listas():
    b = leer_bibliografia(TEXTO_VI)
    assert b["basica"] == [
        "BOLOGNA, EDUARDO. (2021). MÉTODOS ESTADÍSTICOS DE INVESTIGACIÓN. EDITORIAL BRUJAS.. "
        "https://elibro.net/es/lc/utiec/titulos/106355",
        "AUTORA UNO, AUTOR DOS. (2021). METODOLOGÍA, ESTADÍSTICA APLICADA E INSTRUMENTOS EN NEUROPSICOLOGÍA. "
        "ENCUENTRO GRUPO EDITOR. https://search.ebscohost.com/login.aspx?direct=true&db=e086sww"]
    assert b["complementaria"] == [
        "JAIME MORENO, LUIS PUERTAS. (2022). Estudio de validez. CIENCIAMÉRICA. "
        "https://cienciamerica.edu.ec/index.php/uti/article/view/385"]


def test_bibliografia_vacia():
    assert leer_bibliografia("VI. BIBLIOGRAFÍA") == {"basica": [], "complementaria": []}
