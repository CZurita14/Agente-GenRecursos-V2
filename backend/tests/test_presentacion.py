"""Vistas por herramienta: orden fijo, títulos legibles y sin claves internas."""
import json

import pytest

from app.exportar.presentacion import VISTAS, legible, nombre_ambito, presentar
from app.herramientas.sin_ia import generar_sin_ia

CLAVES_INTERNAS = ("clase_id", "numero_clase", "item_id", "escenario", "referencia_resolutivo", "para_subir")

FICHA = {"conceptual": {"ideas_clave": ["Idea A", "Idea B", "Idea C"], "relacion_ra": "Se relaciona con RA2",
                        "errores_frecuentes": ["E1"]},
         "aplicacion": {"ejemplo": {"enunciado": "Enun", "pasos": ["P1", "P2"], "resultado": "R"},
                        "autocomprobacion": ["Q1", "Q2", "Q3"]}}
_LARGO = "Texto de prueba con la longitud suficiente para la herramienta."
CON_IA = {
    "presentacion": {"presentacion": {"titulo": "Título de prueba", "diapositivas": [
        {"titulo": "Uno", "puntos": ["a", "b"], "notas": "Notas de prueba para el docente."}]}},
    "practica_guiada": {"practica": {"objetivo": _LARGO, "ejercicios": [
        {"enunciado": _LARGO, "pasos": ["p1", "p2"], "resultado_esperado": "r"}], "errores_a_evitar": ["e"]}},
    "tarjetas": {"mazo": {"tarjetas": [{"frente": "f", "reverso": "r", "contenido": "c"}]}},
    "guia_autonoma": {"guia_autonoma": {"objetivo": _LARGO, "actividad": _LARGO, "pasos": ["a", "b", "c"],
                                        "tiempo_estimado": "2 h", "para_la_siguiente_clase": "x",
                                        "autochequeo": ["q1", "q2", "q3"], "conexion_pis": "Aporte"}},
    "guion_clase": {"guion": {"objetivo": _LARGO, "fases": [
        {"fase": "inicio", "minutos": 10, "docente": "d", "estudiantes": "e"}],
        "preguntas_detonantes": ["q1", "q2"], "conexion_pis": ""}},
    "ficha_clase": FICHA,
    "repaso_momento": {"repaso": {"sesiones": [{"clase_id": "M2-S1", "ideas_clave": ["a", "b", "c"]}],
                                  "conexion_ra": "Conecta", "preguntas_repaso": ["p1", "p2", "p3"]}},
    "guia_evidencia": {"guia": {"que_se_pide": "Pide", "como_se_valora": [{"indicador": "Ind", "que_observar": "Obs"}],
                                "errores_comunes": ["e1"], "autochequeo": ["a1"]}},
    "estudio_caso": {"caso": {"escenario": "interno", "caso": "Caso largo", "ra": "RA2",
                              "preguntas": [{"nivel": "critico", "pregunta": "¿Por qué?", "respuesta_orientativa": "Porque"}]}},
    "guia_producto_final": {"guia_final": {"ruta": [{"momento": "M2", "aporte": "Aporta"}],
                                           "criterios": [{"indicador": "Ind", "como_prepararse": "Prepara"}],
                                           "recomendaciones": ["r1"]}},
}
SIN_IA = [("hoja_ruta", "asignatura"), ("autoevaluacion_rubrica", "M2"), ("autoevaluacion_final", "asignatura"),
          ("lista_evidencia", "M3"),
          ("rubrica_momento", "M2"), ("rubrica_final", "asignatura")]


def _recorrer(bloques):
    for b in bloques:
        assert b["tipo"] in ("texto", "lista", "tabla", "grupo") and b["titulo"]
        yield b
        if b["tipo"] == "grupo":
            yield from _recorrer(b["bloques"])


def _sin_claves(bloques):
    """Ni claves crudas en el texto ni títulos derivados de ellas («Clase id»)."""
    todos = list(_recorrer(bloques))
    texto = json.dumps([{k: v for k, v in b.items() if k != "tipo"} for b in todos], ensure_ascii=False)
    titulos = {b["titulo"] for b in todos} | {c for b in todos if b["tipo"] == "tabla" for c in b["columnas"]}
    assert not any(c in texto for c in CLAVES_INTERNAS if "_" in c)  # «escenario» también es palabra común.
    assert not titulos & {c.replace("_", " ").capitalize() for c in CLAVES_INTERNAS}


def _invertido(valor):
    """Mismo contenido con las claves en orden inverso (como puede devolverlo jsonb)."""
    if isinstance(valor, dict):
        return {k: _invertido(valor[k]) for k in reversed(list(valor))}
    return [_invertido(x) for x in valor] if isinstance(valor, list) else valor


def test_todas_las_herramientas_tienen_vista():
    assert set(VISTAS) == set(CON_IA) | {h for h, _ in SIN_IA}


@pytest.mark.parametrize("herramienta", list(CON_IA))
def test_con_ia_orden_fijo_y_legible(herramienta):
    bloques = presentar(herramienta, CON_IA[herramienta])
    assert bloques and bloques == presentar(herramienta, _invertido(CON_IA[herramienta]))
    _sin_claves(bloques)


@pytest.mark.parametrize("herramienta,ambito", SIN_IA)
def test_sin_ia_desde_el_silabo(silabo, herramienta, ambito):
    contenido = generar_sin_ia(herramienta, silabo, ambito)
    bloques = presentar(herramienta, contenido)
    assert bloques == presentar(herramienta, _invertido(contenido))
    _sin_claves(bloques)


def test_ficha_en_orden_de_estudio():
    titulos = [b["titulo"] for b in presentar("ficha_clase", _invertido(FICHA))]
    assert titulos == ["Ideas clave", "Relación con el resultado de aprendizaje", "Errores frecuentes", "Ejemplo resuelto", "Autocomprobación"]
    pasos = presentar("ficha_clase", FICHA)[3]["bloques"][1]
    assert pasos == {"tipo": "lista", "titulo": "Pasos", "items": ["P1", "P2"], "numerada": True,
                     "ruta": ["aplicacion", "ejemplo", "pasos"]}


def test_rubrica_como_tabla(silabo):
    contenido = generar_sin_ia("autoevaluacion_rubrica", silabo, "M2")
    tabla = next(b for b in presentar("autoevaluacion_rubrica", contenido) if b["tipo"] == "tabla")
    assert tabla["columnas"][:3] == ["Indicador", "Receptivo", "Resolutivo"] and "Crítico" in tabla["columnas"]
    assert len(tabla["filas"]) == len(contenido["indicadores"])
    assert all(len(f) == len(tabla["columnas"]) for f in tabla["filas"])


def test_caso_oculta_el_escenario():
    texto = json.dumps(presentar("estudio_caso", CON_IA["estudio_caso"]), ensure_ascii=False)
    assert "interno" not in texto and "Crítico" in texto


def test_forma_desconocida_usa_respaldo_sin_perder_texto():
    editado = {"conceptual": {"ideas_clave": ["X"]}, "extra_docente": "Nota del docente"}  # Falta «aplicacion».
    bloques = presentar("ficha_clase", editado)
    texto = json.dumps(bloques, ensure_ascii=False)
    assert "Nota del docente" in texto and "Extra docente" in texto and "X" in texto
    assert bloques == presentar("ficha_clase", _invertido(editado))


def test_cuestionario_no_tiene_bloques():
    assert presentar("cuestionario", [{"item_id": "i1", "opciones": []}]) == []


# --- P6c: rutas editables -----------------------------------------------------------

def _resolver(contenido, ruta):
    for paso in ruta:
        contenido = contenido[paso]
    return contenido


def _rutas(bloques):
    """(ruta, texto mostrado) de cada texto editable."""
    for b in _recorrer(bloques):
        if b["tipo"] in ("texto", "lista") and b["ruta"] is not None:
            yield b["ruta"], b["texto"] if b["tipo"] == "texto" else b["items"]
        if b["tipo"] == "tabla":
            assert len(b["rutas"]) == len(b["filas"])
            for fila, rutas in zip(b["filas"], b["rutas"]):
                yield from ((r, celda) for celda, r in zip(fila, rutas) if r is not None)


@pytest.mark.parametrize("herramienta", list(CON_IA))
def test_rutas_resuelven_al_texto_mostrado(herramienta):
    rutas = list(_rutas(presentar(herramienta, CON_IA[herramienta])))
    assert rutas
    for ruta, mostrado in rutas:
        guardado = _resolver(CON_IA[herramienta], ruta)
        # Se muestra con nombres completos; lo que se edita y se guarda es el texto original.
        assert ([legible(x) for x in guardado] if isinstance(guardado, list) else legible(guardado)) == mostrado


def test_listas_cerradas_no_son_editables():
    guia = presentar("guia_evidencia", CON_IA["guia_evidencia"])[1]
    assert guia["rutas"] == [[None, ["guia", "como_se_valora", 0, "que_observar"]]]
    caso = presentar("estudio_caso", CON_IA["estudio_caso"])
    assert caso[1]["titulo"] == "Se relaciona con" and caso[1]["ruta"] is None


@pytest.mark.parametrize("herramienta,ambito", SIN_IA)
def test_sin_ia_no_se_edita(silabo, herramienta, ambito):
    assert not list(_rutas(presentar(herramienta, generar_sin_ia(herramienta, silabo, ambito))))


@pytest.mark.parametrize("codigo,nombre", [("M1-S2", "Momento 1, sesión 2"), ("M2", "Momento 2"), ("asignatura", "Proyecto Formativo")])
def test_nombre_ambito(codigo, nombre):
    assert nombre_ambito(codigo) == nombre


def test_legible_no_altera_otras_palabras():
    texto = "RAM, M2M, MAPA y formato M0 siguen igual"
    assert legible(texto) == texto
    assert legible("Con RA3 en M4") == "Con Resultado de aprendizaje 3 en Momento 4"


def test_el_contenido_guardado_no_cambia():
    original = json.dumps(FICHA, sort_keys=True)
    presentar("ficha_clase", FICHA)
    assert json.dumps(FICHA, sort_keys=True) == original
