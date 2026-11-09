"""P3b T7: herramientas con IA de momento y asignatura por HTTP, con la regla §9.4.2."""
import json

import pytest

from app.agentes.orquestador import procesar_uno
from app.llm.cliente import ClienteSimulado
from app.silabo.modelo import SilaboUTI
from tests.test_coordinador import WorkerPrueba
from tests.test_generacion_api import HEADERS, entorno, generar, guardar  # noqa: F401
from tests.test_workers_momento import _respuestas, _revisor

RESTRICTIVA = "La evaluación individual se desarrolla sin asistencia de IA."


def _restringir_m3(app, silabo):
    datos = silabo.model_dump()
    datos["proyecto_formativo"]["version"] = "2.0"
    datos["momentos"][1]["politica_ia"] = RESTRICTIVA
    app.state.asignaturas.guardar("dueno@uti.edu.ec", SilaboUTI.model_validate(datos))


def _momento(c, aid, herramientas, id_="M3"):
    return generar(c, aid, ambito={"tipo": "momento", "id": id_}, herramientas=herramientas)


def test_generar_simulacro_encola(entorno, conn, monkeypatch):
    app, _, d, aid, _ = entorno
    from app.agentes.workers import WORKERS
    monkeypatch.setitem(WORKERS, "simulacro", WorkerPrueba("simulacro"))
    r = _momento(d, aid, ["simulacro"])
    assert r.status_code == 202 and r.json()["trabajos"][0]["estado"] == "en_cola"
    from tests.test_coordinador import cliente_revisor
    assert procesar_uno(conn, cliente_revisor(), app.state.perfiles, "w", 360)
    recurso = d.get(f"/asignaturas/{aid}/recursos").json()[0]
    assert (recurso["herramienta"], recurso["ambito_id"], recurso["estado"]) == ("simulacro", "M3", "listo")


def test_generar_restringido_422(entorno, silabo):
    app, _, d, aid, _ = entorno
    _restringir_m3(app, silabo)
    assert _momento(d, aid, ["simulacro"]).status_code == 422
    assert _momento(d, aid, ["repaso_momento"]).status_code == 422
    assert generar(d, aid, ambito={"tipo": "clase", "id": "M3-S1"}, herramientas=["cuestionario"]).status_code == 422
    assert _momento(d, aid, ["autoevaluacion_rubrica"]).status_code == 202  # Sin IA: el sílabo tal cual.
    assert _momento(d, aid, ["repaso_momento"], "M2").status_code == 202  # Momento anterior, permitido.
    assert generar(d, aid, ambito={"tipo": "asignatura", "id": "asignatura"},
                   herramientas=["guia_producto_final"]).status_code == 202


def test_catalogo_restringido(entorno, silabo):
    app, _, d, aid, _ = entorno
    _restringir_m3(app, silabo)
    r = d.get(f"/asignaturas/{aid}/herramientas?ambito=momento&id=M3").json()
    assert r["restringido"] is True and "IA" in r["motivo"]
    assert {h["id"] for h in r["herramientas"]} == {"autoevaluacion_rubrica", "lista_evidencia", "rubrica_momento"}
    clase = d.get(f"/asignaturas/{aid}/herramientas?ambito=clase&id=M3-S2").json()
    assert clase["restringido"] is True and clase["herramientas"] == []
    libre = d.get(f"/asignaturas/{aid}/herramientas?ambito=momento&id=M2").json()
    assert libre["restringido"] is False and "simulacro" in {h["id"] for h in libre["herramientas"]}


@pytest.fixture
def guia(entorno, conn, silabo):
    app, _, d, aid, _ = entorno
    from app.silabo.contexto import contexto_momento
    datos = _respuestas(contexto_momento(silabo, "M3"))["guia_evidencia"]
    assert _momento(d, aid, ["guia_evidencia"]).status_code == 202
    cliente = ClienteSimulado({"worker": lambda m: json.dumps(datos), "revisor": _revisor()})
    assert procesar_uno(conn, cliente, app.state.perfiles, "w", 360)
    rid = d.get(f"/asignaturas/{aid}/recursos").json()[0]["id"]
    return d, aid, d.get(f"/asignaturas/{aid}/recursos/{rid}").json()


def test_edicion_de_guia_valida(guia):
    d, aid, recurso = guia
    assert recurso["estado"] == "listo" and recurso["silabo_actualizado"] is False
    contenido = json.loads(json.dumps(recurso["contenido"]))
    contenido["guia"]["errores_comunes"][0] = "Confundir no rechazar H0 con aceptarla."
    r = guardar(d, aid, recurso, contenido)
    assert r.status_code == 200 and r.json()["estado"] == "requiere_revision"
    assert r.json()["verificacion_edicion"] == {"guia": []}


def test_edicion_de_guia_que_copia_la_evidencia_queda_marcada(guia, silabo):
    d, aid, recurso = guia
    m3 = next(m for m in silabo.momentos if m.numero == 3)
    contenido = json.loads(json.dumps(recurso["contenido"]))
    contenido["guia"]["autochequeo"][0] = " ".join(m3.evidencia.split()[:14])
    r = guardar(d, aid, recurso, contenido)
    assert r.status_code == 200 and "copia" in " ".join(r.json()["verificacion_edicion"]["guia"])


def test_edicion_con_campo_extra_422(guia):
    d, aid, recurso = guia
    contenido = json.loads(json.dumps(recurso["contenido"]))
    contenido["guia"]["respuesta"] = "la solución de la evidencia"
    assert guardar(d, aid, recurso, contenido).status_code == 422


def test_catalogo_oculta_lo_que_el_silabo_no_permite(entorno, silabo):
    app, _, d, aid, _ = entorno
    datos = silabo.model_dump()
    datos["proyecto_formativo"]["version"] = "2.0"
    datos["momentos"][1]["rubrica"] = []
    app.state.asignaturas.guardar("dueno@uti.edu.ec", SilaboUTI.model_validate(datos))
    ids = {h["id"] for h in d.get(f"/asignaturas/{aid}/herramientas?ambito=momento&id=M3").json()["herramientas"]}
    assert "guia_evidencia" not in ids and "simulacro" in ids
    assert _momento(d, aid, ["guia_evidencia"]).status_code == 422


def test_catalogo_con_id_inexistente_404(entorno):
    _, _, d, aid, _ = entorno
    assert d.get(f"/asignaturas/{aid}/herramientas?ambito=momento&id=M99").status_code == 404


def test_catalogo_muestra_la_politica(entorno, silabo):
    _, _, d, aid, _ = entorno
    r = d.get(f"/asignaturas/{aid}/herramientas?ambito=momento&id=M2").json()
    assert r["politica_ia"] == silabo.momentos[0].politica_ia
