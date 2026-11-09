"""§9.4 regla 2: si la política del momento excluye la IA en una evaluación, en ese
momento solo se ofrecen repasos de momentos anteriores.

Detección determinista sobre el texto normalizado. Como ninguna lista de frases es
completa, el catálogo muestra además la política del momento para que el docente juzgue.
"""
import re

from app.agentes.facultades import normalizar

_IA = r"(?:(?:EL USO DE |LA )?(?:HERRAMIENTAS DE )?(?:LA )?(?:IA|INTELIGENCIA ARTIFICIAL)\b)"
_RESTRICTIVA = re.compile(
    rf"\bSIN (?:(?:ASISTENCIA|USO|APOYO|AYUDA) DE )?{_IA}"
    rf"|\bNO (?:SE PERMITE|ESTA PERMITID[OA]|SE AUTORIZA|ESTA AUTORIZAD[OA]) {_IA}"
    rf"|\bPROHIBID[OA] (?:EL USO DE )?{_IA}"
)


def excluye_ia_en_evaluacion(politica: str) -> bool:
    return bool(_RESTRICTIVA.search(normalizar(politica or "")))
