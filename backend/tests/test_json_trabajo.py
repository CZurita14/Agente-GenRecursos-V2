"""JSON de trabajo de la V2: PIS, sesión con fecha y actividades separadas por tipo."""
from app.agentes.mensajes import EstiloFacultad
from app.llm.prompts import Sello, construir_prompt
from app.silabo.contexto import contexto_asignatura, contexto_clase, contexto_momento
from app.silabo.modelo import Pis


def _prompt(c):
    msgs = construir_prompt(sello=Sello(c.codigo_pf, c.clase_id, c.fecha), instrucciones="reglas", contexto=c,
                            estilo=EstiloFacultad(tipos_de_caso=[], software_habitual=[]), ya_generado=[], pedido="(pedido)", salida_max=1000,
                            contar=lambda m: 0)
    return msgs[1]["content"]


def test_la_clase_trae_sesion_fecha_y_actividades_por_tipo(silabo):
    sesion = next(s for m in silabo.momentos for s in m.sesiones if s.id == "M2-S1")
    c = contexto_clase(silabo, "M2-S1")
    assert (c.sesion_numero, c.semana, c.fecha) == (sesion.numero, sesion.semana_periodo, sesion.fecha)
    assert c.actividad_practica.texto == sesion.practico.texto
    assert c.actividad_autonoma.texto == sesion.autonomo.texto
    assert c.actividad_docente.texto.startswith(sesion.docente.texto)
    assert c.pis == silabo.pis


def test_json_trabajo_tiene_los_campos_del_docente(silabo):
    j = contexto_clase(silabo, "M2-S1").json_trabajo()
    assert set(j) == {"proyecto_formativo", "pis", "sesion", "actividades_docente", "actividades_practicas",
                      "actividades_autonomas", "contenidos", "momento"}
    assert j["sesion"]["id"] == "M2-S1" and j["sesion"]["fecha"]
    assert j["contenidos"] and j["actividades_autonomas"]["texto"]


def test_el_prompt_de_clase_separa_actividades_y_muestra_la_sesion(silabo):
    c = contexto_clase(silabo, "M2-S1")
    texto = _prompt(c)
    assert f"Sesión {c.sesion_numero} · semana {c.semana} · {c.fecha:%d/%m/%Y}" in texto
    assert "Actividades de trabajo autónomo" in texto and "Actividades:\n" not in texto
    if c.actividad_docente.texto.strip():
        assert "Actividades con el docente" in texto


def test_el_pis_va_en_el_prompt_de_todos_los_ambitos(silabo):
    s = silabo.model_copy(update={"pis": Pis(nombre="Sistema de turnos", aporte="Módulo de reportes")})
    for c in (contexto_clase(s, "M2-S1"), contexto_momento(s, "M2"), contexto_asignatura(s)):
        assert "Proyecto integrador de saberes (PIS): Sistema de turnos" in _prompt(c)


def test_sin_pis_no_hay_linea_de_pis(silabo):
    c = contexto_clase(silabo.model_copy(update={"pis": None}), "M2-S1")
    assert c.json_trabajo()["pis"] is None and "Proyecto integrador de saberes" not in _prompt(c)


def test_el_momento_sigue_listando_actividades_por_sesion(silabo):
    texto = _prompt(contexto_momento(silabo, "M2"))
    assert "Actividades:\n" in texto and "Actividades de trabajo autónomo" not in texto
