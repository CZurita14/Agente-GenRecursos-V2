"""P3b T1: contexto de momento y de asignatura sobre el mismo contrato ContextoClase."""
from types import SimpleNamespace

import pytest

from app.llm.prompts import Sello, construir_prompt
from app.agentes.mensajes import EstiloFacultad
from app.silabo.contexto import contexto_ambito, contexto_asignatura, contexto_clase, contexto_momento
from app.silabo.modelo import SilaboUTI


def _momento(silabo, n):
    return next(m for m in silabo.momentos if m.numero == n)


def test_contexto_momento_m3(silabo):
    c = contexto_momento(silabo, "M3")
    m = _momento(silabo, 3)
    assert (c.clase_id, c.fecha, c.momento_titulo) == ("M3", m.fecha_inicio, m.titulo)
    esperados = list(dict.fromkeys(x for s in m.sesiones for x in s.contenidos))
    assert c.contenidos == esperados
    assert len(c.actividades) == len(m.sesiones) == 4
    assert c.entregables_momento[0] == m.evidencia
    assert [r.id for r in c.ra] == m.ra and c.rubrica == m.rubrica and c.politica_ia == m.politica_ia


def test_contexto_asignatura(silabo):
    c = contexto_asignatura(silabo)
    assert (c.clase_id, c.fecha) == ("asignatura", silabo.periodo.inicio)
    assert [r.id for r in c.ra] == [r.id for r in silabo.resultados_aprendizaje]
    assert c.rubrica == silabo.rubrica_producto_final
    assert c.entregables_momento[0] == silabo.problema.producto_final
    assert all(f"M{m.numero}:" in c.politica_ia for m in silabo.momentos)


def test_contexto_ambito_despacha(silabo):
    amb = lambda tipo, id_: SimpleNamespace(tipo=tipo, id=id_)
    assert contexto_ambito(silabo, amb("clase", "M2-S1")) == contexto_clase(silabo, "M2-S1")
    assert contexto_ambito(silabo, amb("momento", "M2")) == contexto_momento(silabo, "M2")
    assert contexto_ambito(silabo, amb("asignatura", "asignatura")) == contexto_asignatura(silabo)
    with pytest.raises(KeyError):
        contexto_ambito(silabo, amb("asignatura", "otra"))


@pytest.mark.parametrize("ambito", ["M9", "M", "2", "M2-S1"])
def test_momento_inexistente(silabo, ambito):
    with pytest.raises(KeyError):
        contexto_momento(silabo, ambito)


def test_momento_sin_politica(silabo):
    datos = silabo.model_dump()
    datos["momentos"][0]["politica_ia"] = ""
    assert contexto_momento(SilaboUTI.model_validate(datos), "M2").politica_ia == ""


def _prompt(contexto, contar=lambda m: sum(len(x["content"]) for x in m) // 3):
    return construir_prompt(sello=Sello(codigo_pf=contexto.codigo_pf, clase_id=contexto.clase_id,
                                        fecha=contexto.fecha),
                            instrucciones="Instrucciones.", contexto=contexto,
                            estilo=EstiloFacultad(tipos_de_caso=[], software_habitual=[]),
                            ya_generado=[], pedido="Pedido.", salida_max=3500, contar=contar)


def test_prompt_dice_momento_y_asignatura(silabo):
    momento = _prompt(contexto_momento(silabo, "M2"))
    assert "Momento M2" in momento[1]["content"] and "Clase M2" not in momento[1]["content"]
    asignatura = _prompt(contexto_asignatura(silabo))
    assert "Asignatura" in asignatura[1]["content"]


def test_contexto_asignatura_no_crece_con_las_sesiones(silabo):
    # Revisión P3b: la sección del ámbito nunca se recorta; no debe depender del n.º de sesiones.
    datos = silabo.model_dump()
    for m in datos["momentos"]:
        extra = [dict(s, id=f"{s['id']}x", contenidos=[c + " (ampliado)" for c in s["contenidos"]])
                 for s in m["sesiones"]]
        m["sesiones"] = m["sesiones"] + extra
    grande = SilaboUTI.model_validate(datos)
    a, b = contexto_asignatura(silabo), contexto_asignatura(grande)
    assert a.contenidos == [] and b.contenidos == []
    assert len(_prompt(a)[1]["content"]) == len(_prompt(b)[1]["content"])
