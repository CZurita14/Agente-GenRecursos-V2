"""Comando `simular`: reanudable, atómico, con ClienteSimulado (nunca el servidor real)."""
import itertools
import json
import threading
from pathlib import Path

import httpx
import openai
import pytest

from app.llm.cliente import ClienteSimulado, ErrorDelServidor, ServidorNoDisponible
from app.silabo.modelo import SilaboUTI
from ciencia_datos import simular
from ciencia_datos.corpus import leer_carpeta
from ciencia_datos.sim_plan import cupos
from ciencia_datos.sim_redaccion import TEMPERATURA, VERSION_PROMPTS
from ciencia_datos.simular import generar, ruta_silabo

CATALOGO = Path(__file__).resolve().parents[2] / "kb" / "catalogo.yaml"
TODOS = cupos(CATALOGO)
CUPOS = TODOS[:3]  # tres facultades distintas por la rotación
NIVELES = dict(receptivo="r", resolutivo="s", reflexivo="f", critico="c", cocreativo="k")


_UNICO = itertools.count()  # textos distintos en cada llamada: los fragmentos repetidos se descartan


def _fila(i, tag):
    u = next(_UNICO)
    return {"indicador": f"Indicador {tag} {i} {u}",
            "niveles": {k: f"{v} {tag} {i} {u}" for k, v in NIVELES.items()}}


def _general(_mensajes):
    # Siempre de sobra: el ensamblado recorta lo que excede el esqueleto de cada cupo.
    return json.dumps({
        "competencia_perfil": "Competencia del perfil", "competencia_pf": "Competencia del PF",
        "metacompetencia": "Metacompetencia",
        "resultados": [{"texto": f"Resultado {i} {next(_UNICO)}", "evidencia": f"Evidencia RA {i} {next(_UNICO)}"} for i in range(4)],
        "problema": {"descripcion": "Descripción", "reto": "Reto", "producto_final": "Producto"},
        "pis": {"nombre": "Proyecto integrador", "aporte": "Aporte"},
        "metodologias": [f"Metodología {i} {next(_UNICO)}" for i in range(4)],
        "titulos_momentos": [f"Título {i}" for i in range(4)],
        "rubrica_producto_final": [_fila(i, "pf") for i in range(5)],
    })


def _momento(actividad):
    def f(_mensajes):
        return json.dumps({
            "evidencia": "Evidencia", "recursos": "Recursos", "politica_ia": "Política de IA",
            "rubrica": [_fila(i, "m") for i in range(6)],
            "sesiones": [{
                "contenidos": [f"Contenido {s}-{c} {next(_UNICO)}" for c in range(3)],
                "docente": actividad or f"Docente {s} {next(_UNICO)}", "practico": f"Práctico {s} {next(_UNICO)}",
                "autonomo": f"Autónomo {s} {next(_UNICO)}", "entregables": [f"Entregable {s}"],
            } for s in range(4)],
        })
    return f


def _proyectos(_mensajes):
    return json.dumps({"proyectos": [{"nombre": f"Proyecto {i}", "nivel": 4} for i in range(12)]})


def _respuestas(actividad=None, general=_general):
    return {"sim_proyectos": _proyectos, "sim_general": general, "sim_momento": _momento(actividad)}


def _cliente_valido(actividad=None):
    return ClienteSimulado(_respuestas(actividad))


def _general_que(accion):
    """Una respuesta general que llama a `accion(n)` con el número de llamada (1, 2, ...)."""
    n = {"v": 0}
    candado = threading.Lock()

    def f(m):
        with candado:
            n["v"] += 1
            actual = n["v"]
        return accion(actual, m)
    return f


def _cliente_que_falla_el_primero():
    return ClienteSimulado(_respuestas(
        general=_general_que(lambda n, m: "no es json" if n <= 3 else _general(m))))


def _cliente_que_cae_tras(n):
    def accion(actual, m):
        if actual > n:
            raise ServidorNoDisponible("caído")
        return _general(m)
    return ClienteSimulado(_respuestas(general=_general_que(accion)))


def _de_la_carrera(c):
    return [x for x in TODOS if (x.sigla, x.carrera) == (c.sigla, c.carrera)]


def test_genera_y_valida_contra_el_contrato(tmp_path):
    r = generar(_cliente_valido(), CUPOS, tmp_path / "s", tmp_path / "t")
    assert r.generados == 3
    archivos = list((tmp_path / "s").rglob("*.json"))
    assert len(archivos) == 3
    assert all(SilaboUTI.model_validate_json(a.read_bytes()) for a in archivos)
    assert {a.stem for a in archivos} == {c.codigo for c in CUPOS}
    assert {a.parent.parent.name for a in archivos} == {c.sigla for c in CUPOS}


def test_leer_con_origen_no_ve_rechazados(tmp_path):
    generar(_cliente_valido(), CUPOS, tmp_path / "s", tmp_path / "t")
    silabos, rechazados = leer_carpeta(tmp_path / "s")
    assert len(silabos) == 3 and rechazados == []


def test_reanudar_no_repite_ni_llama_de_nuevo(tmp_path):
    generar(_cliente_valido(), CUPOS, tmp_path / "s", tmp_path / "t")
    otro = _cliente_valido()
    r = generar(otro, CUPOS, tmp_path / "s", tmp_path / "t")
    assert (r.generados, r.existentes) == (0, 3)
    assert otro.llamadas == []


def test_un_json_danado_se_regenera(tmp_path):
    generar(_cliente_valido(), CUPOS[:1], tmp_path / "s", tmp_path / "t")
    next((tmp_path / "s").rglob("*.json")).write_text("{a medias", encoding="utf-8")
    assert generar(_cliente_valido(), CUPOS[:1], tmp_path / "s", tmp_path / "t").generados == 1
    assert len(leer_carpeta(tmp_path / "s")[0]) == 1


def test_un_descartado_no_detiene_la_corrida(tmp_path):
    # Las 3 primeras respuestas generales son inválidas: agotan los reintentos del primer cupo.
    r = generar(_cliente_que_falla_el_primero(), CUPOS, tmp_path / "s", tmp_path / "t", hilos=1)
    assert (r.generados, r.descartados) == (2, 1)
    assert len(list((tmp_path / "s").rglob("*.json"))) == 2


def test_no_quedan_temporales(tmp_path):
    generar(_cliente_valido(), CUPOS, tmp_path / "s", tmp_path / "t")
    assert [p for p in (tmp_path / "s").rglob("*") if p.is_file() and p.suffix != ".json"] == []


def test_proyectos_y_manifiesto_van_fuera_de_la_carpeta_de_silabos(tmp_path):
    generar(_cliente_valido(), CUPOS, tmp_path / "s", tmp_path / "t", modelo="qwen-x", semilla=7)
    assert len(json.loads((tmp_path / "t" / "proyectos.json").read_text(encoding="utf-8"))) == 3
    m = json.loads((tmp_path / "t" / "manifiesto.json").read_text(encoding="utf-8"))
    assert m["modelo"] == "qwen-x" and m["semilla"] == 7
    assert m["temperatura"] == TEMPERATURA and m["version_prompts"] == VERSION_PROMPTS
    assert (m["generados"], m["existentes"], m["descartados"]) == (3, 0, 0)


def test_los_proyectos_se_reutilizan_y_el_cupo_i_usa_el_proyecto_i_menos_1(tmp_path):
    carrera = _de_la_carrera(CUPOS[0])
    generar(_cliente_valido(), carrera[:1], tmp_path / "s", tmp_path / "t", cupos_totales=TODOS)
    otro = _cliente_valido()
    generar(otro, carrera[1:2], tmp_path / "s", tmp_path / "t", cupos_totales=TODOS)
    assert "sim_proyectos" not in [x["rol"] for x in otro.llamadas]
    s = SilaboUTI.model_validate_json(ruta_silabo(tmp_path / "s", carrera[1]).read_bytes())
    assert s.proyecto_formativo.nombre == "Proyecto 1"


def test_pide_proyectos_segun_el_total_de_cupos_de_la_carrera(tmp_path):
    cliente = _cliente_valido()
    generar(cliente, CUPOS[:1], tmp_path / "s", tmp_path / "t", cupos_totales=TODOS)
    total = len(_de_la_carrera(CUPOS[0]))
    pedido = next(x for x in cliente.llamadas if x["rol"] == "sim_proyectos")
    assert f"Propón {total} " in pedido["mensajes"][-1]["content"]


def test_si_faltan_proyectos_se_pide_una_vez_mas_y_luego_se_descarta(tmp_path):
    def pocos(_m):
        return json.dumps({"proyectos": [{"nombre": "Único", "nivel": 2}]})
    cliente = ClienteSimulado({**_respuestas(), "sim_proyectos": pocos})
    carrera = _de_la_carrera(CUPOS[0])
    r = generar(cliente, carrera[:2], tmp_path / "s", tmp_path / "t", cupos_totales=TODOS)
    assert sum(1 for x in cliente.llamadas if x["rol"] == "sim_proyectos") == 2
    assert (r.generados, r.descartados) == (1, 1)


def test_servidor_caido_conserva_lo_generado_y_sale_con_2(tmp_path, monkeypatch, capsys):
    _entorno(monkeypatch)
    monkeypatch.setattr(simular, "_crear_cliente", lambda a: _cliente_que_cae_tras(1))
    assert simular.main(["--salida", str(tmp_path), "--limite", "3", "--hilos", "1"]) == 2
    assert len(list((tmp_path / "silabos_simulados").rglob("*.json"))) == 1
    assert "Traceback" not in capsys.readouterr().err
    assert (tmp_path / "simulacion" / "manifiesto.json").exists()


def test_la_consola_no_imprime_texto(tmp_path, monkeypatch, capsys):
    _entorno(monkeypatch)
    monkeypatch.setattr(simular, "_crear_cliente", lambda a: _cliente_valido(actividad="TEXTO-SECRETO"))
    assert simular.main(["--salida", str(tmp_path), "--limite", "1"]) == 0
    salida = capsys.readouterr()
    assert "TEXTO-SECRETO" not in salida.out + salida.err
    assert "generados=1" in salida.out


def test_limite_toma_los_primeros_cupos(tmp_path, monkeypatch):
    _entorno(monkeypatch)
    monkeypatch.setattr(simular, "_crear_cliente", lambda a: _cliente_valido())
    simular.main(["--salida", str(tmp_path), "--limite", "3"])
    codigos = {a.stem for a in (tmp_path / "silabos_simulados").rglob("*.json")}
    assert codigos == {c.codigo for c in TODOS[:3]}


def test_configuracion_invalida_sale_con_2_sin_valores(tmp_path, monkeypatch, capsys):
    for v in ("DATABASE_URL", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(simular, "Ajustes", _ajustes_sin_env)
    assert simular.main(["--salida", str(tmp_path)]) == 2
    assert "Traceback" not in capsys.readouterr().err


def _ajustes_sin_env():
    from app.config import Ajustes
    return Ajustes(_env_file=None)


def _entorno(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@localhost/x")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1/v1")
    monkeypatch.setenv("LLM_MODEL", "modelo-prueba")
    monkeypatch.setattr(simular, "Ajustes", _ajustes_sin_env)


def _estado_4xx():
    resp = httpx.Response(401, request=httpx.Request("POST", "http://x/v1/chat/completions"))
    return openai.AuthenticationError("TEXTO-ERROR", response=resp, body=None)


def _lanza(error):
    def f(_m):
        raise error
    return f


@pytest.mark.parametrize("rol,error", [
    ("sim_proyectos", _estado_4xx),            # 4xx del chat en la fase de proyectos
    ("sim_general", _estado_4xx),              # 4xx del chat en el pool
    ("sim_general", lambda: ErrorDelServidor("TEXTO-ERROR")),
    ("sim_general", lambda: RuntimeError("TEXTO-ERROR")),  # excepción inesperada
])
def test_errores_fatales_salen_con_2_con_manifiesto_y_sin_texto(tmp_path, monkeypatch, capsys, rol, error):
    _entorno(monkeypatch)
    respuestas = _respuestas()
    respuestas[rol] = _lanza(error())
    monkeypatch.setattr(simular, "_crear_cliente", lambda a: ClienteSimulado(respuestas))
    assert simular.main(["--salida", str(tmp_path), "--limite", "3", "--hilos", "1"]) == 2
    salida = capsys.readouterr()
    assert "TEXTO-ERROR" not in salida.out + salida.err
    assert "Traceback" not in salida.err
    m = json.loads((tmp_path / "simulacion" / "manifiesto.json").read_text(encoding="utf-8"))
    assert (m["generados"], m["descartados"]) == (0, 0)


def test_un_error_fatal_no_envia_cupos_nuevos(tmp_path):
    cliente = ClienteSimulado({**_respuestas(), "sim_general": _lanza(_estado_4xx())})
    with pytest.raises(simular.ServidorCaido) as e:
        generar(cliente, CUPOS, tmp_path / "s", tmp_path / "t", hilos=1)
    assert e.value.motivo == simular.RECHAZO
    assert sum(1 for x in cliente.llamadas if x["rol"] == "sim_general") == 1


@pytest.mark.parametrize("args", [["--hilos", "0"], ["--hilos", "-1"], ["--limite", "-1"]])
def test_hilos_y_limite_invalidos_los_rechaza_argparse(tmp_path, args):
    with pytest.raises(SystemExit) as e:
        simular.main(["--salida", str(tmp_path), *args])
    assert e.value.code == 2
