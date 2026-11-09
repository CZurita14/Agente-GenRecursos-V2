from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from app.agentes.facultades import cargar_perfiles, estilo_para
from app.agentes.mensajes import TareaLote
from app.agentes.planificador import (
    PERFILES,
    _focos,
    _indice_foco,
    estilo_razonado,
    perfil_por_nivel,
    planificar,
    tabla_especificaciones,
)
from app.agentes.workers.momento import ESCENARIOS_DE_RESPALDO, escenario_para
from app.razonador import Razonador
from app.silabo.contexto import contexto_clase

RAIZ = Path(__file__).resolve().parents[2]


def test_tabla_12_fundamentacion():
    assert tabla_especificaciones(12, "fundamentacion") == {
        "receptivo": 2, "resolutivo": 5, "reflexivo": 4, "critico": 1,
    }


@pytest.mark.parametrize("perfil", list(PERFILES))
def test_suma_siempre_n(perfil):
    for n in range(1, 31):
        assert sum(tabla_especificaciones(n, perfil).values()) == n


def test_perfil_por_nivel():
    assert perfil_por_nivel(1) == "fundamentacion"
    assert perfil_por_nivel(3) == "fundamentacion"
    assert perfil_por_nivel(4) == "profesional"
    assert perfil_por_nivel(7) == "profesional"
    assert perfil_por_nivel(8) == "avanzado"
    assert perfil_por_nivel(2, posgrado=True) == "avanzado"


def test_lotes_de_4(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    lotes = planificar(ctx, 12, "fundamentacion")
    assert [len(lote) for lote in lotes] == [4, 4, 4]
    ids = [p.item_id for lote in lotes for p in lote]
    assert ids == [f"i{k}" for k in range(1, 13)]


def test_orden_de_menor_a_mayor_nivel(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    orden = ["receptivo", "resolutivo", "reflexivo", "critico"]
    niveles = [orden.index(p.nivel) for lote in planificar(ctx, 12, "profesional") for p in lote]
    assert niveles == sorted(niveles)


def test_focos_distintos_m2s1_m2s2(silabo):
    f1 = {p.foco for lote in planificar(contexto_clase(silabo, "M2-S1"), 12, "fundamentacion") for p in lote}
    f2 = {p.foco for lote in planificar(contexto_clase(silabo, "M2-S2"), 12, "fundamentacion") for p in lote}
    assert f1 != f2


def test_determinista(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    assert planificar(ctx, 10, "avanzado") == planificar(ctx, 10, "avanzado")


def _plano(lotes):
    return [p for lote in lotes for p in lote]


def test_n_pequeno_incluye_actividad_y_contenido(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    focos = {p.foco for p in _plano(planificar(ctx, 3, "fundamentacion"))}
    assert len(ctx.actividades) + len(ctx.contenidos) > 3
    assert focos & {a.strip() for a in ctx.actividades}
    assert focos & {c.strip() for c in ctx.contenidos}


def test_focos_desacoplados_de_niveles(silabo):
    plan = _plano(planificar(contexto_clase(silabo, "M2-S1"), 12, "fundamentacion"))
    for a, b in zip(plan, plan[1:]):
        assert a.foco != b.foco
    niveles_por_foco = {}
    for p in plan:
        niveles_por_foco.setdefault(p.foco, set()).add(p.nivel)
    repetidos = [n for f, n in niveles_por_foco.items() if sum(q.foco == f for q in plan) > 1]
    assert repetidos and all(len(n) > 1 for n in repetidos)


def test_perfil_desconocido():
    with pytest.raises(ValueError):
        tabla_especificaciones(5, "inexistente")


def test_n_cero_y_errores(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    assert planificar(ctx, 0, "profesional") == []
    with pytest.raises(ValueError):
        tabla_especificaciones(-1, "profesional")
    with pytest.raises(ValueError):
        planificar(ctx, 4, "profesional", tam_lote=0)


def test_ultimo_lote_parcial(silabo):
    lotes = planificar(contexto_clase(silabo, "M2-S1"), 10, "profesional")
    assert [len(lote) for lote in lotes] == [4, 4, 2]


def test_avanzado_sin_receptivo():
    assert tabla_especificaciones(10, "avanzado")["receptivo"] == 0


ESCENARIOS = ["picos de tráfico en una tienda en línea", "tiempos de respuesta de una API REST",
              "fallos de compilación en un repositorio Git", "consultas lentas en una base de datos"]


def test_casos_evitan_el_escenario_del_entregable(silabo):
    # §9.4 regla 1: el entregable de M3 habla de «picos de tráfico»; ese escenario se descarta.
    ctx = contexto_clase(silabo, "M3-S4")
    plan = [p for lote in planificar(ctx, 12, "fundamentacion", escenarios=ESCENARIOS) for p in lote]
    casos = [p.caso for p in plan]
    assert set(casos) == set(ESCENARIOS[1:])
    assert all(a != b for a, b in zip(casos, casos[1:]))
    assert planificar(ctx, 12, "fundamentacion", escenarios=ESCENARIOS) == planificar(
        ctx, 12, "fundamentacion", escenarios=ESCENARIOS)


def test_casos_varian_entre_clases(silabo):
    a, b = (contexto_clase(silabo, c) for c in ("M2-S1", "M2-S2"))
    caso = lambda ctx: planificar(ctx, 4, "fundamentacion", escenarios=ESCENARIOS[1:])[0][0].caso
    assert {caso(a), caso(b)} <= set(ESCENARIOS[1:])
    assert [p.caso for p in planificar(a, 3, "fundamentacion", escenarios=ESCENARIOS[1:])[0]] != \
           [p.caso for p in planificar(b, 3, "fundamentacion", escenarios=ESCENARIOS[1:])[0]]


def test_sin_escenarios_libres_no_se_asigna_caso(silabo):
    ctx = contexto_clase(silabo, "M3-S4")
    plan = planificar(ctx, 4, "fundamentacion", escenarios=["picos de tráfico de red"])[0]
    assert all(p.caso == "" for p in plan)
    assert all(p.caso == "" for p in planificar(ctx, 4, "fundamentacion")[0])


# --- Con razonador (apagado por omisión) ---------------------------------------

PERFIL = cargar_perfiles(RAIZ / "agentes")["ingenierias"]


class FalsoRazonador:
    """Mismos métodos que `Razonador`; los temas salen de repartir los textos entre `k` grupos."""
    version = "v-prueba"

    def __init__(self, k=3, acepta=True):
        self.k, self.acepta = k, acepta
        self.casos_recibidos = None

    def temas(self, textos):
        return [g for g in (list(range(i, len(textos), self.k)) for i in range(self.k)) if g]

    def casos_libres(self, casos, entregables):
        self.casos_recibidos = list(casos)
        return list(casos) if self.acepta else []


def con_focos(ctx, cantidad=8):
    return ctx.model_copy(update={"actividades": [f"foco {k}" for k in range(cantidad)], "contenidos": []})


def tema_de(foco, k=3):
    return int(foco.split()[1]) % k


def test_sin_razonador_el_plan_no_cambia(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    plan = planificar(ctx, 12, "fundamentacion", razonador=None)
    assert plan == planificar(ctx, 12, "fundamentacion")
    focos = _focos(ctx)
    assert [p.foco for p in _plano(plan)] == [focos[_indice_foco(k, 12, len(focos))] for k in range(12)]


def test_cubre_todos_los_temas_antes_de_repetir(silabo):
    ctx = con_focos(contexto_clase(silabo, "M2-S1"))
    plan = _plano(planificar(ctx, 3, "fundamentacion", razonador=FalsoRazonador()))
    assert len({tema_de(p.foco) for p in plan}) == 3


def test_rotacion_por_tema_con_indice_circular(silabo):
    # Temas [0,3,6], [1,4,7], [2,5]: un foco de cada tema, y el tema agotado se salta.
    ctx = con_focos(contexto_clase(silabo, "M2-S1"))
    plan = _plano(planificar(ctx, 10, "fundamentacion", razonador=FalsoRazonador()))
    assert [int(p.foco.split()[1]) for p in plan] == [0, 1, 2, 3, 4, 5, 6, 7, 0, 1]


def test_con_razonador_es_determinista_y_conserva_tabla_e_ids(silabo):
    ctx = con_focos(contexto_clase(silabo, "M2-S1"))
    razonado = planificar(ctx, 12, "profesional", razonador=FalsoRazonador())
    assert razonado == planificar(ctx, 12, "profesional", razonador=FalsoRazonador())
    base = planificar(ctx, 12, "profesional")
    assert [(p.item_id, p.nivel) for p in _plano(razonado)] == [(p.item_id, p.nivel) for p in _plano(base)]
    assert [p.foco for p in _plano(razonado)] != [p.foco for p in _plano(base)]


def test_estilo_sin_razonador_es_el_de_siempre(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    assert estilo_razonado(PERFIL, "SOFTWARE", ctx, None) == estilo_para(PERFIL, "SOFTWARE")


def test_nunca_es_menos_estricto_que_el_filtro_de_palabras(silabo):
    ctx = contexto_clase(silabo, "M2-S1").model_copy(update={"entregables_momento": ["tienda en línea"]})
    falso = FalsoRazonador()
    estilo = estilo_razonado(PERFIL, "SOFTWARE", ctx, falso)
    assert "tiempos de carga de una tienda en línea" in estilo_para(PERFIL, "SOFTWARE").escenarios
    assert "tiempos de carga de una tienda en línea" not in estilo.escenarios
    assert "tiempos de carga de una tienda en línea" not in falso.casos_recibidos  # el filtro va primero
    assert estilo.escenarios


def test_el_razonador_descarta_lo_que_el_filtro_deja_pasar(silabo):
    ctx = contexto_clase(silabo, "M2-S1")

    class SoloUno(FalsoRazonador):
        def casos_libres(self, casos, entregables):
            return list(casos)[:1]

    estilo = estilo_razonado(PERFIL, "SOFTWARE", ctx, SoloUno())
    assert len(estilo.escenarios) == 1
    casos = {p.caso for p in _plano(planificar(ctx, 4, "fundamentacion", escenarios=estilo.escenarios))}
    assert casos == set(estilo.escenarios)


def test_todos_descartados_usa_el_comportamiento_actual(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    estilo = estilo_razonado(PERFIL, "SOFTWARE", ctx, FalsoRazonador(acepta=False))
    assert estilo.escenarios == []
    assert all(p.caso == "" for p in _plano(planificar(ctx, 4, "fundamentacion", escenarios=estilo.escenarios)))
    tarea = TareaLote(trabajo_id=uuid4(), asignatura_id=uuid4(), lote=1, ronda=0, contexto=ctx, estilo=estilo,
                      plan=[], ya_generado=[])
    assert escenario_para(tarea) in ESCENARIOS_DE_RESPALDO


def test_funciona_con_la_clase_razonador_real(silabo):
    # Sin modelo: vectores fijos por tema, para probar que las firmas de Razonador encajan.
    def codificar(textos):
        ejes = np.eye(3)
        return np.array([ejes[int(t.split()[1]) % 3] for t in textos])

    ctx = con_focos(contexto_clase(silabo, "M2-S1"))
    plan = _plano(planificar(ctx, 3, "fundamentacion", razonador=Razonador(codificar, version="v", umbral=0.6)))
    assert {tema_de(p.foco) for p in plan} == {0, 1, 2}
