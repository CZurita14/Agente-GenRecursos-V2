"""Ediciones puras: sin BD ni llamadas de IA."""
from copy import deepcopy
import json
from uuid import uuid4

import pytest

from app.recursos.validacion import EdicionInvalida, validar_contenido
from app.silabo.contexto import contexto_clase


@pytest.fixture
def ctx(silabo):
    return contexto_clase(silabo, "M2-S1")


@pytest.fixture
def original(ctx):
    preguntas = [
        "¿Cómo calcularía la mediana de las edades registradas en una encuesta?",
        "Seleccione una estrategia para proteger archivos ante fallos del servidor.",
    ]
    return [dict(
        item_id=f"i{k}", nivel="reflexivo", ra=ctx.ra[0].id,
        contenido=ctx.contenidos[0], foco="Análisis", pregunta=pregunta,
        contexto="Un equipo analiza los registros de una empresa durante varias semanas para decidir cómo mejorar sus procesos internos.",
        opciones=[dict(texto=f"Alternativa {n}", justificacion="Motivo",
                       error_que_representa="Error") for n in range(4)],
        correcta=0, razonamiento=["Analizar datos", "Contrastar resultados"],
    ) for k, pregunta in enumerate(preguntas, 1)]


def validar(ctx, original, contenido, herramienta="cuestionario"):
    return validar_contenido(herramienta, contenido, original, ctx, uuid4())


def test_valido_canonico_sin_mutar(ctx, original):
    copia = deepcopy(original)
    canonico, fallos = validar(ctx, original, original)
    assert canonico == original == copia
    assert canonico is not original
    assert fallos == {"i1": [], "i2": []}
    assert json.loads(json.dumps(canonico)) == canonico


def test_contexto_sin_contenidos_admite_alternativa_del_worker(ctx, original):
    ctx = ctx.model_copy(update={"contenidos": []})
    for item in original:
        item["contenido"] = ctx.momento_titulo
    canonico, fallos = validar(ctx, original, original)
    assert canonico == original
    # El verificador de P1 conserva sus advertencias; guardar no inventa un aprobado.
    assert any("contenido" in f for f in fallos["i1"])


def test_preguntas_gigantes_no_llegan_a_comparacion_cuadratica(ctx, original, monkeypatch):
    editado = deepcopy(original)
    editado[0]["pregunta"] = "abcd" * 20480
    editado[1]["pregunta"] = "bcda" * 20480

    def prohibido(*_, **__):
        pytest.fail("No se debe comparar preguntas gigantes")

    monkeypatch.setattr("app.recursos.validacion.verificar_items", prohibido)
    with pytest.raises(EdicionInvalida):
        validar(ctx, original, editado)


def test_eliminar_reordenar_cambiar_nivel_y_texto(ctx, original):
    editado = deepcopy(original[::-1])
    editado[0]["nivel"] = "critico"
    editado[0]["pregunta"] = "¿Qué mecanismo permite recuperar información perdida después de un corte?"
    assert validar(ctx, original, editado)[1] == {"i2": [], "i1": []}
    assert validar(ctx, original, editado[:1])[1] == {"i2": []}


@pytest.mark.parametrize("campo,valor", [
    ("ra", "RA-INCORRECTO"), ("contenido", "Contenido ajeno"),
])
def test_original_erroneo_permite_corregir_pertenencia(ctx, original, campo, valor):
    editado = deepcopy(original)
    original[0][campo] = valor
    canonico, fallos = validar(ctx, original, editado)
    assert canonico == editado
    assert fallos == {"i1": [], "i2": []}
    assert original[0][campo] == valor
    with pytest.raises(EdicionInvalida):
        validar(ctx, original, original)


def test_original_solo_necesita_ids(ctx, original):
    minimo = [{"item_id": item["item_id"]} for item in original]
    assert validar(ctx, minimo, original)[1] == {"i1": [], "i2": []}
    editado = deepcopy(original)
    editado[0]["item_id"] = "nuevo"
    with pytest.raises(EdicionInvalida):
        validar(ctx, minimo, editado)


@pytest.mark.parametrize("previo", [
    None, {}, [], [{}], [None], [{"item_id": True}],
    [{"item_id": ""}], [{"item_id": " "}],
    [{"item_id": "i1"}, {"item_id": "i1"}],
    [{"item_id": f"i{k}"} for k in range(41)],
])
def test_original_estructura_minima_invalida(ctx, original, previo):
    with pytest.raises(EdicionInvalida):
        validar(ctx, previo, original[:1])


def test_limite_cuarenta_con_ids_distintos(ctx, original):
    editado = [dict(deepcopy(original[0]), item_id=f"i{k}") for k in range(40)]
    previo = [{"item_id": item["item_id"]} for item in editado]
    assert len(validar(ctx, previo, editado)[0]) == 40
    # Un ID repetido no puede usarse para exceder el máximo del lote editado.
    with pytest.raises(EdicionInvalida):
        validar(ctx, previo, editado + [deepcopy(editado[0])])


@pytest.mark.parametrize("campo,valor", [
    ("item_id", "ajeno"), ("ra", "RA-AJENO"),
    ("contenido", "Contenido de otra clase"), ("nivel", "inexistente"),
    ("correcta", True), ("correcta", False), ("correcta", "1"),
    ("correcta", 1.0), ("correcta", -1), ("correcta", 4),
    ("pregunta", "Corta"), ("extra", "dato privado"),
])
def test_campos_invalidos_genericos(ctx, original, campo, valor):
    editado = deepcopy(original)
    editado[0][campo] = valor
    with pytest.raises(EdicionInvalida, match="^El contenido editado no es válido\\.$"):
        validar(ctx, original, editado)


@pytest.mark.parametrize("cantidad", [0, 3, 5])
def test_opciones_cantidad(ctx, original, cantidad):
    editado = deepcopy(original)
    editado[0]["opciones"] = [deepcopy(original[0]["opciones"][0]) for _ in range(cantidad)]
    with pytest.raises(EdicionInvalida):
        validar(ctx, original, editado)


def test_opcion_extra_y_tipo_estricto(ctx, original):
    for campo, valor in [("extra", "privado"), ("texto", 123)]:
        editado = deepcopy(original)
        editado[0]["opciones"][0][campo] = valor
        with pytest.raises(EdicionInvalida):
            validar(ctx, original, editado)


@pytest.mark.parametrize("caso", ["vacio", "demasiados", "ids_duplicados", "objeto", "tupla"])
def test_estructura_lista(ctx, original, caso):
    editado = {"vacio": [], "demasiados": original * 21,
               "ids_duplicados": [original[0], original[0]],
               "objeto": {"items": original}, "tupla": tuple(original)}[caso]
    with pytest.raises(EdicionInvalida):
        validar(ctx, original, editado)


def test_contexto_ajeno_y_mezcla(ctx, original):
    ajeno = ctx.model_copy(update={"contenidos": ["Otra clase"]})
    with pytest.raises(EdicionInvalida):
        validar(ajeno, original, original)
    mezcla = deepcopy(original)
    mezcla[1]["ra"] = "RA-OTRA-CLASE"
    with pytest.raises(EdicionInvalida):
        validar(ctx, original, mezcla)


def test_fallos_deterministas_no_impiden_canonizar(ctx, original):
    editado = deepcopy(original)
    editado[1]["pregunta"] = editado[0]["pregunta"]
    editado[0]["opciones"][0]["texto"] = "Todas las anteriores"
    editado[0]["opciones"][1]["texto"] = "Todas las anteriores"
    editado[0]["contexto"] = "Breve"
    editado[0]["razonamiento"] = []
    canonico, fallos = validar(ctx, original, editado)
    assert canonico == editado
    assert any("duplicad" in f for f in fallos["i2"])
    for fragmento in ["prohibida", "opciones duplicadas", "contexto", "razonamiento"]:
        assert any(fragmento in f for f in fallos["i1"])


@pytest.fixture
def ficha():
    return {"conceptual": {"ideas_clave": ["Idea A", "Idea B", "Idea C"],
                           "relacion_ra": "Relación", "errores_frecuentes": ["Error"]},
            "aplicacion": {"ejemplo": {"enunciado": "Caso", "pasos": ["Resolver"],
                                       "resultado": "Resultado"},
                           "autocomprobacion": ["Revisar", "Comparar", "Explicar"]}}


def test_ficha_valida_y_verificacion(ctx, ficha):
    assert validar(ctx, ficha, ficha, "ficha_clase") == (ficha, {"ficha": []})
    ficha["conceptual"]["ideas_clave"][0] = " "
    ficha["aplicacion"]["ejemplo"]["resultado"] = "Ninguna de las anteriores"
    _, fallos = validar(ctx, ficha, ficha, "ficha_clase")
    assert len(fallos["ficha"]) == 2


@pytest.mark.parametrize("ruta", [(), ("conceptual",), ("aplicacion",), ("aplicacion", "ejemplo")])
def test_ficha_extra_recursivo(ctx, ficha, ruta):
    destino = ficha
    for clave in ruta:
        destino = destino[clave]
    destino["extra"] = "privado"
    with pytest.raises(EdicionInvalida):
        validar(ctx, ficha, ficha, "ficha_clase")


def test_ficha_estructura_y_tipos(ctx, ficha):
    for valor in [[], {"conceptual": ficha["conceptual"]}]:
        with pytest.raises(EdicionInvalida):
            validar(ctx, ficha, valor, "ficha_clase")
    ficha["aplicacion"]["ejemplo"]["pasos"] = [True]
    with pytest.raises(EdicionInvalida):
        validar(ctx, ficha, ficha, "ficha_clase")


def test_herramienta_no_soportada(ctx, original):
    with pytest.raises(EdicionInvalida):
        validar(ctx, original, original, "otra")
