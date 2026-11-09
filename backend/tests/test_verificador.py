"""Verificador determinista §10.1 (Tarea 11)."""
from uuid import uuid4

import pytest

from app.agentes.mensajes import PlanItem
from app.agentes.verificador import (
    CLAVE_CONTRADICHA, EXPLICACION_PLANTILLA, OTRA_PARECE_CLAVE, fallos_justificacion, revision_claves,
    verificar_distribucion, verificar_ficha, verificar_items,
)
from app.herramientas.esquemas import ItemCuestionario, Opcion
from app.silabo.contexto import contexto_clase

ASIG = uuid4()
CONTEXTO_LARGO = ("Una empresa de telecomunicaciones de Ambato registra durante un mes el tráfico "
                  "de su red para decidir si amplía la capacidad de sus enlaces principales.")


@pytest.fixture
def ctx(silabo):
    return contexto_clase(silabo, "M2-S1")


def _item(ctx, item_id="i1", nivel="reflexivo", **cambios):
    base = dict(
        item_id=item_id, nivel=nivel, ra=ctx.ra[0].id, contenido=ctx.contenidos[0], foco="f",
        contexto=CONTEXTO_LARGO,
        pregunta=f"¿Qué se puede concluir del comportamiento observado en el caso {item_id}?",
        opciones=[Opcion(texto=f"opción {item_id}-{k}", justificacion="j", error_que_representa="e")
                  for k in range(4)],
        correcta=0, razonamiento=["paso 1", "paso 2"],
    )
    base.update(cambios)
    return ItemCuestionario(**base)


def _plan(*items):
    return [PlanItem(item_id=i.item_id, nivel=i.nivel, foco="f") for i in items]


def _verificar(ctx, items, plan=None, previos=(), entrega=ASIG, trabajo=ASIG):
    return verificar_items(items, plan or _plan(*items), ctx, list(previos), entrega, trabajo)


def test_item_correcto_sin_fallos(ctx):
    assert _verificar(ctx, [_item(ctx)]) == {"i1": []}


def test_regla_2_opciones_duplicadas(ctx):
    opciones = [Opcion(texto="Igual", justificacion="j", error_que_representa="e")] * 2 + [
        Opcion(texto=f"distinta {k}", justificacion="j", error_que_representa="e") for k in range(2)]
    fallos = _verificar(ctx, [_item(ctx, opciones=opciones)])["i1"]
    assert len(fallos) == 1 and "duplicad" in fallos[0]


def test_regla_3_ra_ajeno(ctx):
    fallos = _verificar(ctx, [_item(ctx, ra="RA9")])["i1"]
    assert len(fallos) == 1 and "RA9" in fallos[0]


def test_regla_3_contenido_ajeno(ctx):
    fallos = _verificar(ctx, [_item(ctx, contenido="Teoría de colas")])["i1"]
    assert len(fallos) == 1 and "contenido" in fallos[0]


def test_regla_5_sin_contexto(ctx):
    fallos = _verificar(ctx, [_item(ctx, nivel="resolutivo", contexto="Un caso corto.")])["i1"]
    assert len(fallos) == 1 and "contexto" in fallos[0]


def test_regla_5_receptivo_admite_contexto_corto(ctx):
    assert _verificar(ctx, [_item(ctx, nivel="receptivo", contexto="Breve.", razonamiento=[])]) == {"i1": []}


def test_regla_5_un_paso(ctx):
    fallos = _verificar(ctx, [_item(ctx, nivel="reflexivo", razonamiento=["un solo paso"])])["i1"]
    assert len(fallos) == 1 and "razonamiento" in fallos[0]


def test_regla_6_casi_duplicado_de_previo(ctx):
    item = _item(ctx)
    fallos = _verificar(ctx, [item], previos=[item.pregunta.replace("observado", "observada")])["i1"]
    assert len(fallos) == 1 and "duplicad" in fallos[0]


def test_regla_6_casi_duplicado_dentro_del_lote(ctx):
    a = _item(ctx, "i1")
    b = _item(ctx, "i2", pregunta=a.pregunta)
    res = _verificar(ctx, [a, b])
    assert res["i1"] == [] and len(res["i2"]) == 1


def test_regla_7_todas_las_anteriores(ctx):
    opciones = [Opcion(texto=f"opción {k}", justificacion="j", error_que_representa="e") for k in range(3)]
    opciones.append(Opcion(texto="Todas las anteriores", justificacion="j", error_que_representa="e"))
    fallos = _verificar(ctx, [_item(ctx, opciones=opciones)])["i1"]
    assert len(fallos) == 1 and "prohibida" in fallos[0]


def test_nivel_distinto_al_plan(ctx):
    item = _item(ctx, nivel="reflexivo")
    plan = [PlanItem(item_id="i1", nivel="critico", foco="f")]
    fallos = _verificar(ctx, [item], plan=plan)["i1"]
    assert len(fallos) == 1 and "nivel" in fallos[0]


def test_a7_otra_asignatura(ctx):
    res = _verificar(ctx, [_item(ctx, "i1"), _item(ctx, "i2")], entrega=uuid4(), trabajo=ASIG)
    assert all(f == ["entrega de otra asignatura"] for f in res.values())


def test_distribucion_fuera_de_tolerancia(ctx):
    items = [_item(ctx, f"i{k}", nivel="receptivo", razonamiento=[]) for k in range(1, 5)]
    tabla = {"receptivo": 1, "resolutivo": 2, "reflexivo": 1, "critico": 0}
    fallos = verificar_distribucion(items, tabla)
    assert any("receptivo" in f for f in fallos) and any("resolutivo" in f for f in fallos)


def test_distribucion_dentro_de_tolerancia(ctx):
    items = [_item(ctx, "i1", nivel="receptivo", razonamiento=[]), _item(ctx, "i2", nivel="resolutivo")]
    assert verificar_distribucion(items, {"receptivo": 1, "resolutivo": 2, "reflexivo": 0, "critico": 0}) == []


def test_ficha_valida_y_con_fallos(ctx):
    buena = {"ideas_clave": ["a", "b", "c"], "relacion_ra": "r", "errores_frecuentes": ["e"]}
    assert verificar_ficha(buena, ctx) == []
    mala = {"ideas_clave": ["a", " ", "Ninguna de las anteriores"], "relacion_ra": "", "errores_frecuentes": ["e"]}
    fallos = verificar_ficha(mala, ctx)
    assert any("prohibida" in f for f in fallos) and any("vac" in f for f in fallos)


# --- Coherencia entre la clave y sus explicaciones ---

def _explicaciones(*textos):
    return list(textos) + ["Otra explicación neutra."] * (4 - len(textos))


def test_clave_contradicha_por_su_explicacion():
    """Caso real: Análisis de Datos, Momento 1, sesión 1, pregunta 10."""
    f = fallos_justificacion(1, ["Sin problema.", "Esta opción confunde la asimetría positiva con negativa.",
                                 "Esta opción interpreta correctamente la asimetría positiva.", "Neutra."])
    assert CLAVE_CONTRADICHA in f and OTRA_PARECE_CLAVE in f


@pytest.mark.parametrize("texto", ["Esta opción describe correctamente el procedimiento.",
                                   "Identifica el error típico.", "Es correcta, porque la media lo muestra."])
def test_clave_coherente_no_alerta(texto):
    assert fallos_justificacion(0, _explicaciones(texto)) == []


@pytest.mark.parametrize("distractor", ["Esta opción no interpreta correctamente el resultado.", "Esta opción no es correcta.",
                                        "Algunas personas ingresan incorrectamente sus credenciales."])
def test_distractor_que_no_se_da_por_correcto_no_alerta(distractor):
    assert fallos_justificacion(0, _explicaciones("Es la adecuada.", distractor)) == []


@pytest.mark.parametrize("distractor", ["Esta opción interpreta correctamente la asimetría.", "Esta es la opción correcta."])
def test_distractor_presentado_como_correcto(distractor):
    assert fallos_justificacion(0, _explicaciones("Es la adecuada.", distractor)) == [OTRA_PARECE_CLAVE]


def test_explicacion_de_plantilla():
    assert EXPLICACION_PLANTILLA in fallos_justificacion(0, _explicaciones("El error que representa: ignorar un supuesto"))


def test_verificar_items_incluye_la_coherencia(ctx):
    item = _item(ctx)
    item.opciones[item.correcta].justificacion = "Esta opción confunde dos conceptos."
    assert CLAVE_CONTRADICHA in verificar_items([item], [], ctx, [], ASIG, ASIG)["i1"]


def test_revision_claves_sobre_lo_guardado():
    item = {"item_id": "i1", "correcta": 0, "opciones": [{"justificacion": "Confunde todo."}, {"justificacion": "Bien."}]}
    assert revision_claves([item, {"item_id": "i2", "correcta": 0, "opciones": [{"justificacion": "Bien."}]}]) == {"i1": [CLAVE_CONTRADICHA]}
    assert revision_claves({"conceptual": {}}) == {} and revision_claves([{"sin": "forma"}]) == {}
