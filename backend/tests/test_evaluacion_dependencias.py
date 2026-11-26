"""Dependencias entre sesiones (prompt institucional §6) (V4-2).

Sílabo de prueba de Análisis de Datos (momentos 2 y 3); cada prueba reescribe las columnas que necesita.
"""
import pytest

from app.evaluacion.dependencias import alertas_dependencias, dependencias, productos_de
from app.evaluacion.herramientas import herramientas_de
from app.silabo.modelo import SilaboUTI


def _con(datos, cambios: dict) -> SilaboUTI:
    """cambios: {"M3-S1/autonomo": "texto" | ("texto", horas)}."""
    for m in datos["momentos"]:
        for s in m["sesiones"]:
            for columna in ("practico", "autonomo"):
                valor = cambios.get(f"{s['id']}/{columna}")
                if valor is None:
                    continue
                texto, horas = valor if isinstance(valor, tuple) else (valor, s[columna]["horas"])
                s[columna] = {"texto": texto, "horas": horas}
    return SilaboUTI.model_validate(datos)


def _de(silabo, clave):
    sesion, columna = clave.split("/")
    return next(d for d in dependencias(silabo) if (d.sesion, d.columna) == (sesion, columna))


def test_una_tarea_que_continua_un_producto_encuentra_su_origen(datos):
    s = _con(datos, {"M2-S2/practico": "Elaboración del prototipo del tablero de indicadores.",
                     "M3-S1/autonomo": "Versión corregida del prototipo con las observaciones de la revisión."})
    d = _de(s, "M3-S1/autonomo")
    assert (d.tipo, d.insumo, d.origen, d.roto, d.revisar) == ("complementaria", "prototipo", "M2-S2/practico", False, False)
    assert _de(s, "M2-S1/autonomo").tipo == "independiente"
    assert alertas_dependencias(s) == []


def test_la_fase_y_la_entrega_de_una_practica_vienen_de_donde_empieza(datos):
    s = _con(datos, {"M3-S1/practico": "Práctica 3: diseño del muestreo en JASP.",
                     "M3-S2/practico": "Práctica 3, fase de desarrollo. Estimación de parámetros.",
                     "M3-S4/practico": "Práctica 3, entrega. Informe con las pruebas aplicadas."})
    assert (_de(s, "M3-S2/practico").insumo, _de(s, "M3-S2/practico").origen) == ("Práctica 3", "M3-S1/practico")
    assert _de(s, "M3-S4/practico").origen == "M3-S1/practico"


def test_un_momento_que_no_existe_es_un_eslabon_roto(datos):
    s = _con(datos, {"M3-S3/autonomo": "Revisión del prototipo elaborado en el Momento 1 y ajuste de sus vistas."})
    d = _de(s, "M3-S3/autonomo")
    assert (d.insumo, d.origen, d.roto) == ("Momento 1", None, True)
    [alerta] = alertas_dependencias(s)
    assert alerta.startswith("M3-S3 (trabajo autónomo)") and "no existe en el sílabo" in alerta


def test_un_origen_sin_horas_en_su_columna_es_un_eslabon_roto(datos):
    s = _con(datos, {"M2-S2/practico": ("Elaboración del prototipo del tablero.", 0.0),
                     "M3-S1/autonomo": "Versión final del prototipo."})
    d = _de(s, "M3-S1/autonomo")
    assert (d.origen, d.roto) == ("M2-S2/practico", True)
    assert "no tiene horas" in alertas_dependencias(s)[0]


def test_sin_origen_claro_se_pide_revisar_sin_afirmar_que_falta(datos):
    s = _con(datos, {"M3-S2/autonomo": "Ajuste final del portafolio según la retroalimentación recibida."})
    d = _de(s, "M3-S2/autonomo")
    assert (d.tipo, d.insumo, d.origen, d.roto, d.revisar) == ("complementaria", "portafolio", None, False, True)
    [alerta] = alertas_dependencias(s)
    assert alerta.startswith("Revisa el insumo previo") and "M3-S2 (trabajo autónomo)" in alerta


@pytest.mark.parametrize("texto", [
    "Prerrequisito (lectura previa): temas 3.2.1 y 3.2.2, con el informe del caso.",
    "Selección de estrategias con ajustes razonables para estudiantes con discapacidad.",
    "Análisis del caso clínico. La actividad incorpora retroalimentación formativa.",
    "Reflexión y recomendaciones de mejora del plan de seguimiento.",
    "Uso de Numiqo para resolver problemas de probabilidad discreta y continua.",
])
def test_lo_que_no_continua_un_producto_es_independiente(datos, texto):
    assert _de(_con(datos, {"M3-S2/autonomo": texto}), "M3-S2/autonomo").tipo == "independiente"


def test_productos_ambiguos_no_cuentan():
    assert productos_de("Programas e indicadores del PDOT") == []
    assert productos_de("Integración al prototipo del PIS") == []
    assert productos_de("Aplicación de las mejoras al programa en Python") == ["programa"]


def test_el_insumo_de_respaldo_solo_en_tareas_complementarias_con_su_origen(datos):
    s = _con(datos, {"M2-S2/practico": "Elaboración del prototipo del tablero.",
                     "M3-S1/autonomo": "Entrega de la versión corregida del prototipo."})
    d = _de(s, "M3-S1/autonomo")
    con = herramientas_de("entrega_avance", "M3-S1", None, d)
    assert [h["herramienta"] for h in con] == ["guia_entrega", "insumo_respaldo"]
    assert "Momento 2, sesión 2 (práctico-experimental)" in con[1]["instrucciones"]
    assert [h["herramienta"] for h in herramientas_de("entrega_avance", "M3-S1")] == ["guia_entrega"]
    independiente = _de(s, "M2-S1/autonomo")
    assert "insumo_respaldo" not in [h["herramienta"] for h in herramientas_de("ensayo", "M2-S1", None, independiente)]
    # Una prueba no es una tarea: no lleva insumo de respaldo aunque su texto continúe algo.
    assert "insumo_respaldo" not in [h["herramienta"] for h in herramientas_de("prueba_sumativa", "M3-S1", None, d)]
