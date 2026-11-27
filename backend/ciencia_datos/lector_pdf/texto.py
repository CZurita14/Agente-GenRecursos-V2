"""Utilidades puras de texto del lector (sin PDF)."""
import re
from datetime import date, timedelta

from app.agentes.facultades import normalizar

Tabla = list[list[str | None]]

_ENTREGABLE = re.compile(r"\b(TAREA|PAE|EVALUACION COGNITIVA)\s+(\d+)\b")
_CANONICO = {"TAREA": "TAREA", "PAE": "PAE", "EVALUACION COGNITIVA": "EVALUACIÓN COGNITIVA"}


def normalizar_clave(texto: str | None) -> str:
    """Para comparar: mayúsculas, sin tildes, sin saltos ni espacios repetidos."""
    return normalizar(texto or "")


def limpio(texto: str | None) -> str:
    """Para mostrar: une las líneas partidas por el PDF y conserva el resto tal cual."""
    return " ".join((texto or "").split())


def fecha_dmy(texto: str) -> date:
    dia, mes, anio = (int(x) for x in texto.strip().split("/"))
    return date(anio, mes, dia)


def fecha_o_none(texto: str | None) -> date | None:
    """Fecha dd/mm/aaaa, o None si el sílabo trae otra cosa («Por definir»)."""
    try:
        return fecha_dmy(texto or "")
    except ValueError:
        return None


def horas(texto: str | None) -> float:
    texto = (texto or "").strip().replace(",", ".")
    return float(texto) if texto else 0.0


def semana_periodo(fecha: date | None, inicio: date) -> int | None:
    """Semana 1 = la que empieza el lunes de la semana de `inicio`."""
    if fecha is None:
        return None
    lunes = inicio - timedelta(days=inicio.weekday())
    return (fecha - lunes).days // 7 + 1


def entregables_en(*textos: str) -> list[str]:
    """«TAREA n», «PAE n» y «EVALUACIÓN COGNITIVA n», canónicos, en orden y sin repetir."""
    hallados: list[str] = []
    for texto in textos:
        for tipo, numero in _ENTREGABLE.findall(normalizar_clave(texto)):
            canonico = f"{_CANONICO[tipo]} {numero}"
            if canonico not in hallados:
                hallados.append(canonico)
    return hallados


def filas(tablas: list[Tabla]):
    """Todas las filas de todas las tablas, con sus celdas en texto ('' si vacías)."""
    for tabla in tablas:
        for fila in tabla:
            yield [c or "" for c in fila]
