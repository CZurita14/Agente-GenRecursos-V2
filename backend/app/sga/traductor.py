"""Traductor del sílabo crudo del SGA al contrato (docs/api-silabo/silabo-api.schema.json).

Lista blanca recursiva: solo pasan las claves que el esquema declara; todo lo demás
(docente, correo, firmas, cédula, ...) se descarta sin mirarlo. Los objetos y listas
que el esquema deja libres (`niveles`, `ra`, `contenidos`, `metodologias`, ...) pasan completos.

El árbol es un espejo del esquema: dict = objeto con propiedades declaradas,
[nodo] = lista de objetos, None = valor que pasa tal cual. Una prueba exige que
sea igual al derivado de silabo-api.schema.json.
"""
import copy

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


def a_contrato(crudo: dict) -> dict:
    """Copia del sílabo crudo con solo las claves del contrato; no muta la entrada."""
    return _filtrar(crudo, _ARBOL)
