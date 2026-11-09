"""Redacción por etapas y ensamblado del sílabo simulado, con ClienteSimulado."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agentes.facultades import cargar_catalogo, normalizar
from app.llm.cliente import ClienteSimulado
from app.llm.json import JsonInvalido
from app.silabo.modelo import SilaboUTI
from ciencia_datos.sim_esqueleto import crear_esqueleto
from ciencia_datos.sim_plan import cupos
from ciencia_datos.sim_redaccion import (
    TEMPERATURA, VERSION_PROMPTS, ProyectoPropuesto, SimulacionInvalida, proponer_proyectos,
    redactar_silabo,
)

CATALOGO = Path(__file__).resolve().parents[2] / "kb" / "catalogo.yaml"
CUPO = next(c for c in cupos(CATALOGO) if c.sigla == "FING")
PROYECTO = ProyectoPropuesto(nombre="Sistema de gestión de inventarios", nivel=4)
NIVELES = dict(receptivo="r", resolutivo="s", reflexivo="f", critico="c", cocreativo="k")


def _fila(i, tag):
    return {"indicador": f"Indicador {tag} {i}", "niveles": {k: f"{v} {tag} {i}" for k, v in NIVELES.items()}}


def _general(esq, extra=0):
    return json.dumps({
        "competencia_perfil": "Competencia del perfil", "competencia_pf": "Competencia del PF",
        "metacompetencia": "Metacompetencia",
        "resultados": [{"texto": f"Resultado {i}", "evidencia": f"Evidencia RA {i}"}
                       for i in range(esq.n_resultados + extra)],
        "problema": {"descripcion": "Descripción", "reto": "Reto", "producto_final": "Producto"},
        "pis": {"nombre": "Proyecto integrador", "aporte": "Aporte"},
        "metodologias": [f"Metodología {i}" for i in range(esq.n_metodologias + extra)],
        "titulos_momentos": [f"Título {i}" for i in range(4)],
        "rubrica_producto_final": [_fila(i, "pf") for i in range(esq.n_filas_rubrica_pf + extra)],
    })


def _momento(esq, m, actividad=None, sesiones=None, extra=0):
    n = len(esq.momentos[m].sesiones) if sesiones is None else sesiones
    return json.dumps({
        "evidencia": f"Evidencia del momento {m}", "recursos": f"Recursos {m}",
        "politica_ia": f"Política de IA {m}",
        "rubrica": [_fila(i, f"m{m}") for i in range(esq.n_filas_rubrica + extra)],
        "sesiones": [{
            "contenidos": [f"Contenido {m}-{s}-{c}" for c in range(esq.contenidos_por_sesion + extra)],
            "docente": actividad or f"Docente {m}-{s}", "practico": f"Práctico {m}-{s}",
            "autonomo": f"Autónomo {m}-{s}", "entregables": [f"Entregable {m}-{s}"],
        } for s in range(n)],
    })


def _cliente_valido(actividad=None, extra=0):
    e = crear_esqueleto(CUPO)
    return ClienteSimulado({
        "sim_general": [_general(e, extra)],
        "sim_momento": [_momento(e, m, actividad, extra=extra) for m in range(4)],
    })


def _cliente_con_una_sesion():
    e = crear_esqueleto(CUPO)
    return ClienteSimulado({
        "sim_general": [_general(e)],
        "sim_momento": [_momento(e, m, sesiones=0 if m == 0 else None) for m in range(4)],
    })


def _propuesta(nombres):
    return json.dumps({"proyectos": [{"nombre": n, "nivel": 3} for n in nombres]})


def test_ensambla_un_silabo_valido_con_cinco_llamadas():
    cliente = _cliente_valido()
    s = redactar_silabo(cliente, CUPO, PROYECTO, crear_esqueleto(CUPO))
    assert isinstance(s, SilaboUTI)
    assert s.proyecto_formativo.codigo == CUPO.codigo
    assert len(s.momentos) == 4
    assert len(cliente.llamadas) == 5
    assert s.bibliografia.basica == []


def test_campos_fijos_y_coherencia_con_el_esqueleto():
    e = crear_esqueleto(CUPO)
    s = redactar_silabo(_cliente_valido(), CUPO, PROYECTO, e)
    pf = s.proyecto_formativo
    assert (pf.uoc, pf.modalidad, pf.version, pf.nivel) == ("Profesional", "Presencial", "SIM", 4)
    assert pf.nombre == PROYECTO.nombre and pf.horario == []
    assert str(pf.aprobado) == "2026-01-15"
    assert pf.horas.total == e.horas_total and pf.horas.contacto == pf.horas.practico == e.horas_total // 3
    assert pf.horas.autonomo == e.horas_total - 2 * (e.horas_total // 3)
    assert pf.creditos == e.horas_total / 48
    assert (s.facultad, s.carrera) == (CUPO.facultad, CUPO.carrera)
    ids = [r.id for r in s.resultados_aprendizaje]
    assert ids == [f"RA{i}" for i in range(1, e.n_resultados + 1)]
    assert {r for m in s.momentos for r in m.ra} == set(ids)
    assert [len(m.sesiones) for m in s.momentos] == [len(m.sesiones) for m in e.momentos]
    assert [m.titulo for m in s.momentos] == [f"Título {i}" for i in range(4)]
    assert set(s.momentos[0].rubrica[0].niveles) == set(NIVELES)


@pytest.mark.parametrize("nivel,uoc", [(1, "Básica"), (3, "Básica"), (4, "Profesional"), (6, "Profesional"),
                                       (7, "Integración curricular"), (8, "Integración curricular")])
def test_uoc_segun_el_nivel(nivel, uoc):
    s = redactar_silabo(_cliente_valido(), CUPO, ProyectoPropuesto(nombre="P", nivel=nivel),
                        crear_esqueleto(CUPO))
    assert s.proyecto_formativo.uoc == uoc


@pytest.mark.parametrize("nivel", [0, 9])
def test_el_nivel_se_valida_entre_1_y_8(nivel):
    with pytest.raises(ValidationError):
        ProyectoPropuesto(nombre="P", nivel=nivel)


def test_recorta_los_elementos_de_mas():
    e = crear_esqueleto(CUPO)
    s = redactar_silabo(_cliente_valido(extra=1), CUPO, PROYECTO, e)
    assert len(s.resultados_aprendizaje) == e.n_resultados
    assert len(s.metodologias) == e.n_metodologias
    assert len(s.rubrica_producto_final) == e.n_filas_rubrica_pf
    assert all(len(m.rubrica) == e.n_filas_rubrica for m in s.momentos)
    assert all(len(x.contenidos) == e.contenidos_por_sesion for m in s.momentos for x in m.sesiones)


def test_la_facultad_simulada_esta_en_el_catalogo():
    s = redactar_silabo(_cliente_valido(), CUPO, PROYECTO, crear_esqueleto(CUPO))
    assert normalizar(s.facultad) in cargar_catalogo(CATALOGO)


def test_con_sesiones_de_menos_se_rechaza():
    with pytest.raises(SimulacionInvalida):
        redactar_silabo(_cliente_con_una_sesion(), CUPO, PROYECTO, crear_esqueleto(CUPO))


def test_con_menos_de_20_fragmentos_se_rechaza():
    e = crear_esqueleto(CUPO)
    pobre = {"contenidos": ["x"], "docente": "x", "practico": "x", "autonomo": "x", "entregables": []}
    cliente = ClienteSimulado({
        "sim_general": [_general(e)],
        "sim_momento": [json.dumps({**json.loads(_momento(e, m)), "evidencia": "x", "sesiones": [
            {**pobre, "contenidos": ["x"] * e.contenidos_por_sesion} for _ in e.momentos[m].sesiones]})
            for m in range(4)],
    })
    with pytest.raises(SimulacionInvalida):
        redactar_silabo(cliente, CUPO, PROYECTO, e)


@pytest.mark.parametrize("texto", ["Dr. Juan Pérez explica el tema", "Escribir a ana@uti.edu.ec",
                                   "Mgs. María López", "Llamar al 0991234567"])
def test_datos_personales_inventados_descartan_el_silabo(texto):
    with pytest.raises(SimulacionInvalida):
        redactar_silabo(_cliente_valido(actividad=texto), CUPO, PROYECTO, crear_esqueleto(CUPO))


def test_datos_personales_fuera_de_fragmentos_tambien_descartan():
    e = crear_esqueleto(CUPO)
    sucio = json.loads(_momento(e, 0))
    sucio["recursos"] = "Contactar a ana@uti.edu.ec"
    cliente = ClienteSimulado({
        "sim_general": [_general(e)],
        "sim_momento": [json.dumps(sucio)] + [_momento(e, m) for m in range(1, 4)],
    })
    with pytest.raises(SimulacionInvalida):
        redactar_silabo(cliente, CUPO, PROYECTO, e)


def test_el_error_no_contiene_texto_del_silabo():
    with pytest.raises(SimulacionInvalida) as e:
        redactar_silabo(_cliente_valido(actividad="Dr. Juan Pérez"), CUPO, PROYECTO, crear_esqueleto(CUPO))
    assert "Pérez" not in str(e.value)


def test_json_invalido_se_propaga():
    cliente = ClienteSimulado({"sim_general": ["no es json"] * 3, "sim_momento": []})
    with pytest.raises(JsonInvalido):
        redactar_silabo(cliente, CUPO, PROYECTO, crear_esqueleto(CUPO))


def test_usa_los_roles_de_simulacion_sin_razonamiento():
    cliente = _cliente_valido()
    redactar_silabo(cliente, CUPO, PROYECTO, crear_esqueleto(CUPO))
    assert {l["rol"] for l in cliente.llamadas} == {"sim_general", "sim_momento"}
    assert all(l["pensar"] is False for l in cliente.llamadas)
    assert all(l["max_tokens"] == 3500 and l["temperatura"] == TEMPERATURA for l in cliente.llamadas)
    assert VERSION_PROMPTS == "2" and TEMPERATURA == 0.7


def test_los_prompts_declaran_ficticio_y_llevan_la_carrera():
    cliente = _cliente_valido()
    redactar_silabo(cliente, CUPO, PROYECTO, crear_esqueleto(CUPO))
    for llamada in cliente.llamadas:
        texto = " ".join(m["content"] for m in llamada["mensajes"])
        assert "ficticio" in texto and CUPO.carrera in texto and PROYECTO.nombre in texto


def test_proyectos_repetidos_se_quitan():
    cliente = ClienteSimulado({"sim_proyectos": [_propuesta(["Redes", "redes ", "Bases de datos"])]})
    nombres = [p.nombre for p in proponer_proyectos(cliente, "FING", "Facultad", "Software", 2)]
    assert nombres == ["Redes", "Bases de datos"]
    assert cliente.llamadas[0]["rol"] == "sim_proyectos"


def test_proyectos_se_limitan_a_n_en_el_orden_propuesto():
    cliente = ClienteSimulado({"sim_proyectos": [_propuesta(["A", "B", "C", "D"])]})
    assert [p.nombre for p in proponer_proyectos(cliente, "FING", "F", "S", 3)] == ["A", "B", "C"]


def test_todos_los_cupos_del_catalogo_ensamblan_sin_falsos_positivos():
    for cupo in cupos(CATALOGO):
        e = crear_esqueleto(cupo)
        cliente = ClienteSimulado({
            "sim_general": [_general(e)],
            "sim_momento": [_momento(e, m) for m in range(4)],
        })
        redactar_silabo(cliente, cupo, PROYECTO, e)


def _fijos(esquema, n):
    """La lista descrita por `esquema` tiene minItems == maxItems == n."""
    return esquema.get("minItems") == n and esquema.get("maxItems") == n


@pytest.mark.parametrize("n_res,n_met,n_rub,n_pf,n_cont", [(None, None, None, None, None), (3, 2, 2, 5, 4)])
def test_el_esquema_enviado_fija_el_tamano_de_cada_lista(n_res, n_met, n_rub, n_pf, n_cont):
    from dataclasses import replace
    e = crear_esqueleto(CUPO)
    if n_res is not None:
        e = replace(e, n_resultados=n_res, n_metodologias=n_met, n_filas_rubrica=n_rub,
                    n_filas_rubrica_pf=n_pf, contenidos_por_sesion=n_cont)
    cliente = ClienteSimulado({
        "sim_general": [_general(e)],
        "sim_momento": [_momento(e, m) for m in range(4)],
    })
    redactar_silabo(cliente, CUPO, PROYECTO, e)
    general = next(c for c in cliente.llamadas if c["rol"] == "sim_general")["esquema"]
    p = general["properties"]
    assert _fijos(p["resultados"], e.n_resultados)
    assert _fijos(p["metodologias"], e.n_metodologias)
    assert _fijos(p["titulos_momentos"], 4)
    assert _fijos(p["rubrica_producto_final"], e.n_filas_rubrica_pf)
    momentos = [c for c in cliente.llamadas if c["rol"] == "sim_momento"]
    assert len(momentos) == 4
    for i, c in enumerate(momentos):
        esq = c["esquema"]
        assert _fijos(esq["properties"]["rubrica"], e.n_filas_rubrica)
        assert _fijos(esq["properties"]["sesiones"], len(e.momentos[i].sesiones))
        assert _fijos(esq["$defs"]["SesionRedactada"]["properties"]["contenidos"],
                      e.contenidos_por_sesion)


def test_el_esquema_estatico_del_modelo_no_se_modifica():
    from ciencia_datos.sim_redaccion import GeneralRedactado
    redactar_silabo(_cliente_valido(), CUPO, PROYECTO, crear_esqueleto(CUPO))
    assert "minItems" not in GeneralRedactado.model_json_schema()["properties"]["resultados"]


def test_version_de_prompts_es_2():
    assert VERSION_PROMPTS == "2"
