"""Herramientas sin IA (catálogo #12, #13, #15, #17): el sílabo tal cual, ordenado.

Cada texto viene del sílabo; lo único que agrega el código son instrucciones fijas.
El formato final lo dará la plantilla académica (B3); aquí el contenido es JSON.
"""
import re

from app.silabo.menu import construir_menu
from app.silabo.modelo import FilaRubrica, Momento, SilaboUTI

NIVELES = ("receptivo", "resolutivo", "reflexivo", "critico", "cocreativo")
HERRAMIENTAS_SIN_IA = {
    "hoja_ruta": "asignatura",
    "autoevaluacion_rubrica": "momento",
    "autoevaluacion_final": "asignatura",
    "lista_evidencia": "momento",
    "rubrica_momento": "momento",
    "rubrica_final": "asignatura",
}
INSTRUCCIONES_AUTOEVALUACION = (
    "Lee los descriptores de cada indicador y marca el nivel que mejor describe tu trabajo "
    "actual. Para subir, compara tu trabajo con el descriptor del nivel siguiente."
)


def _momento(silabo: SilaboUTI, ambito_id: str) -> Momento:
    m = re.fullmatch(r"M(\d+)", ambito_id)
    momento = next((x for x in silabo.momentos if m and x.numero == int(m.group(1))), None)
    if momento is None:
        raise ValueError("momento inexistente en el sílabo")
    return momento


def _indicadores(rubrica: list[FilaRubrica]) -> list[dict]:
    if not rubrica:
        raise ValueError("el sílabo no trae la rúbrica necesaria")
    return [{"indicador": f.indicador,
             "descriptores": {n: f.niveles.get(n, "") for n in NIVELES},
             "para_subir": {n: (f.niveles.get(NIVELES[k + 1], "") if k + 1 < len(NIVELES) else None)
                            for k, n in enumerate(NIVELES)}}
            for f in rubrica]


def _politicas(silabo: SilaboUTI) -> list[dict]:
    return [{"momento": m.numero, "politica_ia": m.politica_ia} for m in silabo.momentos]


def _hoja_ruta(silabo: SilaboUTI) -> dict:
    pf = silabo.proyecto_formativo
    return {
        "asignatura": pf.nombre, "codigo": pf.codigo,
        "periodo": silabo.periodo.model_dump(mode="json"),
        "semanas": [s.model_dump(mode="json") for s in construir_menu(silabo)],
        "momentos": [{"numero": m.numero, "titulo": m.titulo,
                      "fecha_inicio": m.fecha_inicio.isoformat(), "fecha_fin": m.fecha_fin.isoformat(),
                      "ra": list(m.ra), "evidencia": m.evidencia, "politica_ia": m.politica_ia}
                     for m in silabo.momentos],
        "producto_final": silabo.problema.producto_final,
    }


def _autoevaluacion_momento(silabo: SilaboUTI, momento: Momento) -> dict:
    return {
        "momento": momento.numero, "titulo": momento.titulo, "evidencia": momento.evidencia,
        "ra": [{"id": r.id, "texto": r.texto} for r in silabo.resultados_aprendizaje if r.id in momento.ra],
        "niveles": list(NIVELES), "indicadores": _indicadores(momento.rubrica),
        "instrucciones": INSTRUCCIONES_AUTOEVALUACION, "politica_ia": momento.politica_ia,
    }


def _autoevaluacion_final(silabo: SilaboUTI) -> dict:
    return {
        "evidencia": silabo.problema.producto_final,
        "niveles": list(NIVELES), "indicadores": _indicadores(silabo.rubrica_producto_final),
        "instrucciones": INSTRUCCIONES_AUTOEVALUACION, "politica_ia": _politicas(silabo),
    }


def _lista_evidencia(momento: Momento) -> dict:
    return {
        "momento": momento.numero, "titulo": momento.titulo, "evidencia": momento.evidencia,
        "entregables": sorted({e for s in momento.sesiones for e in s.entregables}),
        # «Resolutivo» como referencia del mínimo esperado: decisión provisional hasta B3.
        "items": [{"indicador": f["indicador"], "referencia_resolutivo": f["descriptores"]["resolutivo"]}
                  for f in _indicadores(momento.rubrica)],
        "politica_ia": momento.politica_ia,
    }


def _rubrica_momento(silabo: SilaboUTI, momento: Momento) -> dict:
    return {
        "momento": momento.numero, "titulo": momento.titulo, "evidencia": momento.evidencia,
        "ra": [{"id": r.id, "texto": r.texto} for r in silabo.resultados_aprendizaje if r.id in momento.ra],
        "niveles": list(NIVELES), "indicadores": _indicadores(momento.rubrica),
    }


def _rubrica_final(silabo: SilaboUTI) -> dict:
    return {"evidencia": silabo.problema.producto_final, "niveles": list(NIVELES),
            "indicadores": _indicadores(silabo.rubrica_producto_final)}


def generar_sin_ia(herramienta: str, silabo: SilaboUTI, ambito_id: str) -> dict:
    """Contenido de la herramienta; ValueError si la herramienta o el ámbito no corresponden."""
    tipo = HERRAMIENTAS_SIN_IA.get(herramienta)
    if tipo is None:
        raise ValueError("herramienta sin IA desconocida")
    if tipo == "asignatura":
        if ambito_id != "asignatura":
            raise ValueError("esta herramienta es de la asignatura")
        if herramienta == "rubrica_final":
            return _rubrica_final(silabo)
        return _hoja_ruta(silabo) if herramienta == "hoja_ruta" else _autoevaluacion_final(silabo)
    momento = _momento(silabo, ambito_id)
    if herramienta == "rubrica_momento":
        return _rubrica_momento(silabo, momento)
    if herramienta == "autoevaluacion_rubrica":
        return _autoevaluacion_momento(silabo, momento)
    return _lista_evidencia(momento)
