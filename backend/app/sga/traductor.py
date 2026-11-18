"""Traductor del sílabo crudo del SGA al contrato (docs/api-silabo/silabo-api.schema.json).

Lista blanca recursiva: solo pasan las claves que el esquema declara; todo lo demás
(docente, correo, firmas, cédula, ...) se descarta sin mirarlo. Los objetos y listas
que el esquema deja libres (`niveles`, `ra`, `contenidos`, `metodologias`, ...) pasan completos.

El árbol es un espejo del esquema: dict = objeto con propiedades declaradas,
[nodo] = lista de objetos, None = valor que pasa tal cual. Una prueba exige que
sea igual al derivado de silabo-api.schema.json.
"""
import copy
import re
import unicodedata
from datetime import date, timedelta

from app.sga import contrato_v2

_FILA_RUBRICA = {"indicador": None, "niveles": None}
_ACTIVIDAD = {"texto": None, "horas": None}

_ARBOL = {
    "facultad": None,
    "carrera": None,
    "periodo": {"codigo": None, "inicio": None, "fin": None},
    "proyecto_formativo": {
        "codigo": None, "nombre": None, "version": None, "aprobado": None, "nivel": None,
        "uoc": None, "modalidad": None, "creditos": None,
        "horas": {"total": None, "contacto": None, "autonomo": None, "practico": None},
        "horario": [{"dia": None, "inicio": None, "fin": None}],
    },
    "competencia_perfil": None,
    "competencia_pf": None,
    "metacompetencia": None,
    "resultados_aprendizaje": [{"id": None, "texto": None, "evidencia": None}],
    "problema": {"descripcion": None, "reto": None, "producto_final": None},
    "momentos": [{
        "numero": None, "titulo": None, "fecha_inicio": None, "fecha_fin": None,
        "ra": None, "evidencia": None, "politica_ia": None, "recursos": None,
        "rubrica": [_FILA_RUBRICA],
        "sesiones": [{
            "id": None, "numero": None, "fecha": None, "semana_periodo": None,
            "contenidos": None,
            "docente": {"texto": None, "horas": None, "asincronica": _ACTIVIDAD},
            "practico": _ACTIVIDAD,
            "autonomo": _ACTIVIDAD,
            "entregables": None,
        }],
    }],
    "rubrica_producto_final": [_FILA_RUBRICA],
    "pis": {"nombre": None, "aporte": None},
    "metodologias": None,
    "bibliografia": {"basica": None, "complementaria": None},
}


def arbol_esquema(esquema: dict | None = None) -> dict:
    """Árbol de la lista blanca; con `esquema` lo deriva de él (para comprobar el espejo)."""
    if esquema is None:
        return _ARBOL
    defs = esquema.get("$defs", {})

    def nodo(n: dict):
        if "$ref" in n:
            n = defs[n["$ref"].split("/")[-1]]
        if "properties" in n:
            return {k: nodo(v) for k, v in n["properties"].items()}
        items = n.get("items")
        if n.get("type") == "array" and items and ("$ref" in items or "properties" in items):
            return [nodo(items)]
        return None

    return nodo(esquema)


def _filtrar(valor, nodo):
    if nodo is None:
        return copy.deepcopy(valor)
    if isinstance(nodo, list):
        if not isinstance(valor, list):
            return copy.deepcopy(valor)
        return [_filtrar(v, nodo[0]) for v in valor]
    if not isinstance(valor, dict):
        return copy.deepcopy(valor)
    return {k: _filtrar(valor[k], sub) for k, sub in nodo.items() if k in valor}


_ENTREGABLE = re.compile(r"\b(TAREA|PAE|EVALUACION COGNITIVA)\s+(\d+)\b")
_CANONICO = {"TAREA": "TAREA", "PAE": "PAE", "EVALUACION COGNITIVA": "EVALUACIÓN COGNITIVA"}


def _fecha(valor) -> date | None:
    try:
        return date.fromisoformat(valor) if isinstance(valor, str) else None
    except ValueError:
        return None


def _entregables(*textos) -> list[str]:
    """«TAREA n», «PAE n» y «EVALUACIÓN COGNITIVA n» nombrados en las actividades, en orden y sin repetir."""
    hallados: list[str] = []
    for texto in textos:
        if not isinstance(texto, str):
            continue
        plano = "".join(ch for ch in unicodedata.normalize("NFD", texto.upper()) if unicodedata.category(ch) != "Mn")
        for tipo, numero in _ENTREGABLE.findall(plano):
            nombre = f"{_CANONICO[tipo]} {numero}"
            if nombre not in hallados:
                hallados.append(nombre)
    return hallados


def _texto(sesion: dict, clave: str):
    actividad = sesion.get(clave)
    return actividad.get("texto") if isinstance(actividad, dict) else None


def _completar(contrato: dict) -> list[str]:
    """Completa en el sitio lo que el SGA no guarda y devuelve los avisos (rutas, nunca valores).

    - `sesiones[].fecha` nula: la sesión no tiene fecha programada y no se importa (aviso).
    - `sesiones[].id` ausente: `M<momento>-S<numero>`.
    - `sesiones[].semana_periodo` ausente: semana 1 = la del lunes de `periodo.inicio`.
    - `sesiones[].entregables` ausente: los que nombran las actividades de la sesión.
    Lo que venga con un tipo inesperado se deja igual: lo informa la validación.
    """
    avisos: list[str] = []
    periodo = contrato.get("periodo")
    inicio = _fecha(periodo.get("inicio")) if isinstance(periodo, dict) else None
    lunes = inicio - timedelta(days=inicio.weekday()) if inicio else None
    momentos = contrato.get("momentos")
    for i, momento in enumerate(momentos if isinstance(momentos, list) else []):
        if not isinstance(momento, dict) or not isinstance(momento.get("sesiones"), list):
            continue
        conservadas = []
        for j, sesion in enumerate(momento["sesiones"]):
            if not isinstance(sesion, dict):
                conservadas.append(sesion)
                continue
            if "fecha" in sesion and sesion["fecha"] is None:
                avisos.append(f"momentos[{i}].sesiones[{j}].fecha: sin fecha programada; la sesión no se importó")
                continue
            if "id" not in sesion and isinstance(momento.get("numero"), int) and isinstance(sesion.get("numero"), int):
                sesion["id"] = f"M{momento['numero']}-S{sesion['numero']}"
            dia = _fecha(sesion.get("fecha"))
            if "semana_periodo" not in sesion and dia and lunes:
                sesion["semana_periodo"] = (dia - lunes).days // 7 + 1
            if "entregables" not in sesion:
                docente = sesion.get("docente")
                asincronica = docente.get("asincronica") if isinstance(docente, dict) else None
                sesion["entregables"] = _entregables(
                    _texto(sesion, "docente"), asincronica.get("texto") if isinstance(asincronica, dict) else None,
                    _texto(sesion, "practico"), _texto(sesion, "autonomo"))
            conservadas.append(sesion)
        momento["sesiones"] = conservadas
    return avisos


def a_contrato_con_avisos(crudo: dict) -> tuple[dict, list[str]]:
    """Sílabo del contrato (lista blanca y campos derivados) y los avisos de lo que no se importó.

    Acepta el contrato v1.0 y el v2.0 (`"contrato": "2.0"`); el v2.0 se lleva primero a la forma del v1.0.
    """
    if contrato_v2.es_v2(crudo):
        crudo = contrato_v2.a_v1(crudo)
    contrato = _filtrar(crudo, _ARBOL)
    avisos = _completar(contrato) if isinstance(contrato, dict) else []
    return contrato, avisos


def a_contrato(crudo: dict) -> dict:
    """Copia del sílabo crudo con solo las claves del contrato y sus campos derivados; no muta la entrada."""
    return a_contrato_con_avisos(crudo)[0]
