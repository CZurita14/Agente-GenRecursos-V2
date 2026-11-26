"""Fase de cada momento en la cadena de trazabilidad del Proyecto Formativo.

M1 socialización y teoría → M2 diagnóstico inicial → M3 implementación → M4 resultados y
retroalimentación. Si el sílabo trae más momentos, los siguientes repiten la última fase.
"""
import re

FASES = {
    1: ("Socialización y fundamentación teórica",
        "presenta el proyecto, socializa la teoría que lo sostiene y la vincula con la práctica"),
    2: ("Diagnóstico inicial",
        "levanta y analiza la situación de partida del problema con la teoría del momento 1"),
    3: ("Implementación",
        "aplica la teoría para implementar la solución: requerimientos, diseño y construcción"),
    4: ("Resultados y retroalimentación",
        "evalúa los resultados de la implementación, los comunica y retroalimenta el proceso"),
}


def numero_momento(ambito_id: str) -> int | None:
    """Momento del ámbito; en un rango de momentos («M1-M2», V3-6), el último: el que cierra el parcial."""
    m = re.fullmatch(r"M(\d+)(?:-S\d+|-M(\d+))?", ambito_id or "")
    return int(m.group(2) or m.group(1)) if m else None


def fase(numero: int) -> tuple[str, str]:
    return FASES[min(max(numero, 1), max(FASES))]
