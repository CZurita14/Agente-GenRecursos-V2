"""Mensajes tipados: inmutables, con ida y vuelta por PostgreSQL."""
import uuid

import pytest
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from app.agentes.mensajes import (
    Cierre, Devolucion, Encargo, EntregaLote, EstiloFacultad, PlanItem, ResultadoItem,
    TareaLote, Veredicto, guardar, leer,
)
from app.cola.trabajos import Ambito, encolar
from app.silabo.contexto import contexto_clase

AMBITO = Ambito("clase", "M2-S1")


@pytest.fixture
def ids(conn):
    asig = conn.execute(
        "insert into asignatura (dueno, codigo_pf, version_silabo, agente, silabo) "
        "values ('d@uti.edu.ec', 'PF-1', 'v1', 'ingenieria', %s) returning id",
        (Jsonb({}),),
    ).fetchone()["id"]
    t = encolar(conn, asignatura_id=asig, agente="ingenieria", ambito=AMBITO,
                herramienta="cuestionario", parametros={})
    return t, asig


def _encargo(t, a):
    return Encargo(trabajo_id=t, asignatura_id=a, codigo_pf="PF-1", version_silabo="v1",
                   carrera="Software", nivel=3, ambito=AMBITO, herramienta="cuestionario",
                   perfil_dificultad="medio")


def test_inmutable(ids):
    e = _encargo(*ids)
    with pytest.raises(ValidationError):
        e.herramienta = "otra"


def test_rechaza_extras(ids):
    with pytest.raises(ValidationError):
        Devolucion(trabajo_id=ids[0], asignatura_id=ids[1], item_id="i", motivo="m",
                   ronda=1, extra=1)


def test_ida_y_vuelta(conn, ids, silabo):
    t, a = ids
    dev = Devolucion(trabajo_id=t, asignatura_id=a, item_id="i1", motivo="vago", ronda=1)
    msgs = [
        _encargo(t, a),
        TareaLote(trabajo_id=t, asignatura_id=a, lote=0, ronda=0,
                  contexto=contexto_clase(silabo, "M2-S1"),
                  estilo=EstiloFacultad(tipos_de_caso=["x"], software_habitual=["Excel"]),
                  plan=[PlanItem(item_id="i1", nivel="receptivo", foco="f")],
                  ya_generado=[], devoluciones=[dev]),
        EntregaLote(trabajo_id=t, asignatura_id=a, lote=0, ronda=0,
                    contenido=[{"k": 1}], tokens=(10, 20)),
        Veredicto(trabajo_id=t, asignatura_id=a, resultados=[
            ResultadoItem(item_id="i1", fallos_verificacion=[], revisor="ok")]),
        Cierre(trabajo_id=t, asignatura_id=a, recurso_id=uuid.uuid4(), estado="listo",
               tokens=(1, 2)),
    ]
    for m in msgs:
        guardar(conn, m)
    leidos = leer(conn, t)
    assert leidos == msgs
    assert [type(m) for m in leidos] == [type(m) for m in msgs]
    assert leidos[1].contexto.ra and isinstance(leidos[1].devoluciones[0], Devolucion)


def test_filtrar_por_tipo(conn, ids):
    t, a = ids
    guardar(conn, _encargo(t, a))
    d1 = Devolucion(trabajo_id=t, asignatura_id=a, item_id="a", motivo="m", ronda=1)
    d2 = Devolucion(trabajo_id=t, asignatura_id=a, item_id="b", motivo="m", ronda=2)
    guardar(conn, d1)
    guardar(conn, d2)
    assert leer(conn, t, Devolucion) == [d1, d2]
    assert leer(conn, uuid.uuid4()) == []
