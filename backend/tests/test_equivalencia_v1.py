"""Equivalencia con V1: un sílabo que llega como JSON del SGA produce lo mismo que V1 con el mismo SilaboUTI.

El oráculo (`fixtures/v1/huellas_silabo_datos.json`) lo generó el código de la V1 (011bd68).
Los fallos nombran claves, nunca valores.
"""
import copy
import json
from pathlib import Path

import pytest

from app.agentes.facultades import cargar_catalogo, cargar_perfiles, enrutar, estilo_para
from app.agentes.planificador import perfil_por_nivel, planificar
from app.agentes.workers.base import REGLAS_COMUNES
from app.agentes.workers.definiciones import DEFINICIONES
from app.herramientas.sin_ia import HERRAMIENTAS_SIN_IA, generar_sin_ia
from app.llm.prompts import Sello, construir_prompt
from app.silabo.contexto import contexto_por_id
from app.silabo.integridad import cargar_silabo
from app.silabo.menu import construir_menu
from app.silabo.modelo import SilaboUTI
from app.sga.traductor import a_contrato
from ciencia_datos.corpus import fragmentos

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[1]
FIX = AQUI / "fixtures"
CATALOGO = cargar_catalogo(REPO / "kb" / "catalogo.yaml")
PERFILES = cargar_perfiles(REPO / "agentes")
PRIVADAS = ["docente", "correo", "cedula", "firmas"]


def ambitos(s: SilaboUTI):
    return (["asignatura"] + [f"M{m.numero}" for m in s.momentos]
            + [x.id for m in s.momentos for x in m.sesiones])


# Campos que la V2 agrega al contexto (JSON de trabajo: PIS, sesión y actividades por tipo). La V1 no los
# tiene: la huella los quita y así compara la lógica común. Las pruebas de la V2 cubren los campos nuevos.
CAMPOS_V2 = ("pis", "sesion_numero", "semana", "actividad_docente", "actividad_practica", "actividad_autonoma")


def huellas(s: SilaboUTI) -> dict:
    perfil = PERFILES[enrutar(s.facultad, CATALOGO, PERFILES)]
    estilo = estilo_para(perfil, s.carrera)
    out = {"contexto": {}, "prompt": {}, "plan": {}, "requisitos": {}, "sin_ia": {}}
    for a in ambitos(s):
        c = contexto_por_id(s, a).model_copy(update=dict.fromkeys(CAMPOS_V2))
        out["contexto"][a] = c.model_dump(mode="json", exclude=set(CAMPOS_V2))
        msgs = construir_prompt(sello=Sello(c.codigo_pf, c.clase_id, c.fecha), instrucciones=REGLAS_COMUNES,
                                contexto=c, estilo=estilo, ya_generado=[], pedido="(pedido)",
                                salida_max=3500, contar=lambda m: 0)
        out["prompt"][a] = [m["content"] for m in msgs]
        tipo = "asignatura" if a == "asignatura" else "momento" if a.startswith("M") and "-" not in a else "clase"
        for h, dfn in DEFINICIONES.items():
            if dfn.ambito == tipo:
                out["requisitos"][f"{h}@{a}"] = dfn.requisitos(c)
        if tipo in ("clase", "momento"):
            out["plan"][a] = [[p.model_dump() for p in lote]
                              for lote in planificar(c, 12, perfil_por_nivel(c.nivel), escenarios=estilo.escenarios)]
        for h, t in HERRAMIENTAS_SIN_IA.items():
            if t == tipo:
                try:
                    out["sin_ia"][f"{h}@{a}"] = generar_sin_ia(h, s, a)
                except ValueError:
                    out["sin_ia"][f"{h}@{a}"] = "ValueError"
    out["menu"] = [x.model_dump(mode="json") for x in construir_menu(s)]
    out["entrenamiento"] = [(f.tipo, f.momento, f.texto) for f in fragmentos(s)]
    out["agente"] = enrutar(s.facultad, CATALOGO, PERFILES)
    return out


def normalizar(h: dict) -> dict:
    """Mismo tratamiento que el oráculo: JSON con default=str."""
    return json.loads(json.dumps(h, sort_keys=True, default=str))


def entradas(h: dict) -> dict:
    """Aplana a (categoría, ámbito) -> valor; el menú, el agente y el entrenamiento son una entrada cada uno."""
    plano = {}
    for k, v in h.items():
        if isinstance(v, dict):
            for sub, x in v.items():
                plano[f"{k}/{sub}"] = x
        else:
            plano[k] = v
    return plano


def diferencias(a: dict, b: dict) -> list[str]:
    pa, pb = entradas(a), entradas(b)
    return sorted({k for k in pa.keys() | pb.keys() if pa.get(k, "<falta>") != pb.get(k, "<falta>")})


def desde_sga(crudo: dict) -> SilaboUTI:
    return cargar_silabo(a_contrato(crudo))


def test_equivalencia_con_v1():
    oraculo = json.loads((FIX / "v1" / "huellas_silabo_datos.json").read_text(encoding="utf-8"))
    s_v1 = SilaboUTI.model_validate_json((FIX / "silabo_datos.json").read_bytes())
    # camino de V2: modelo -> JSON del contrato -> traductor -> carga validada
    s = desde_sga(s_v1.model_dump(mode="json"))
    dif = diferencias(normalizar(huellas(s)), oraculo)
    n = len(entradas(oraculo))
    assert n > 50
    assert not dif, f"{len(dif)} de {n} entradas difieren: {dif}"


def _privar(crudo: dict) -> dict:
    """Quita a mano las claves privadas y las inventadas."""
    d = copy.deepcopy(crudo)
    for k in PRIVADAS + ["nota_privada"]:
        d.pop(k, None)
    for m in d["momentos"]:
        m.pop("nota_privada", None)
        for se in m["sesiones"]:
            se.pop("nota_privada", None)
    return d


def _crudo_con_ruido(crudo: dict) -> dict:
    d = copy.deepcopy(crudo)
    d.update(docente="DOCENTE FALSO", correo="falso@ejemplo.test", cedula="0000000000",
             firmas=["firma falsa"], nota_privada="x")
    for m in d["momentos"]:
        m["nota_privada"] = "x"
        for se in m["sesiones"]:
            se["nota_privada"] = "x"
    return d


@pytest.mark.parametrize("ruta", sorted((FIX / "sga" / "sga_silabos").glob("*.json")), ids=lambda p: p.stem)
def test_campos_privados_no_cambian_nada(ruta):
    crudo = _crudo_con_ruido(json.loads(ruta.read_text(encoding="utf-8")))
    dif = diferencias(normalizar(huellas(desde_sga(crudo))), normalizar(huellas(desde_sga(_privar(crudo)))))
    assert not dif, f"cambian {len(dif)} entradas: {dif}"
