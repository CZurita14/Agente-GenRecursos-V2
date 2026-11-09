"""P3a por HTTP: herramientas sin IA generadas al instante, sin cola ni modelo."""
from app.silabo.modelo import SilaboUTI
from tests.test_generacion_api import HEADERS, compartir, entorno, generar, guardar  # noqa: F401


def _sin_ia(c, aid, herramientas, tipo, ambito_id):
    return generar(c, aid, ambito={"tipo": tipo, "id": ambito_id}, herramientas=herramientas)


def _recurso(c, aid, respuesta):
    trabajo = respuesta.json()["trabajos"][0]
    return c.get(f"/asignaturas/{aid}/recursos/{trabajo['recurso_id']}")


def test_genera_hoja_ruta_al_instante(entorno):
    _, _, d, aid, _ = entorno
    r = _sin_ia(d, aid, ["hoja_ruta", "autoevaluacion_final"], "asignatura", "asignatura")
    assert r.status_code == 202, r.text
    assert [t["estado"] for t in r.json()["trabajos"]] == ["listo", "listo"]
    recurso = _recurso(d, aid, r).json()
    assert recurso["herramienta"] == "hoja_ruta" and recurso["estado"] == "listo"
    assert [s["numero"] for s in recurso["contenido"]["semanas"]] == [2, 3, 4]
    assert recurso["evidencia"]["sin_ia"] is True and recurso["silabo_actualizado"] is False
    estados = {t["herramienta"]: t["estado"] for t in d.get(f"/asignaturas/{aid}/trabajos").json()}
    assert estados == {"hoja_ruta": "listo", "autoevaluacion_final": "listo"}


def test_catalogo_por_ambito(entorno):
    _, _, d, aid, _ = entorno
    momento = [h["id"] for h in d.get(f"/asignaturas/{aid}/herramientas?ambito=momento").json()["herramientas"]]
    # Orden del perfil FING (simulacro, …, autoevaluacion_rubrica, …) y luego las no recomendadas.
    assert momento == ["simulacro", "estudio_caso", "autoevaluacion_rubrica", "repaso_momento",
                       "guia_evidencia", "lista_evidencia", "rubrica_momento"]
    asignatura = [h["id"] for h in d.get(f"/asignaturas/{aid}/herramientas?ambito=asignatura").json()["herramientas"]]
    assert sorted(asignatura) == ["autoevaluacion_final", "guia_producto_final", "hoja_ruta", "rubrica_final"]


def test_ambito_incorrecto_no_crea_nada(entorno):
    _, _, d, aid, _ = entorno
    for herramientas, tipo, ambito_id in ((["hoja_ruta"], "clase", "M2-S1"),
                                          (["autoevaluacion_rubrica"], "momento", "M9"),
                                          (["autoevaluacion_rubrica", "hoja_ruta"], "momento", "M2"),
                                          (["autoevaluacion_rubrica", "cuestionario"], "momento", "M2")):
        assert _sin_ia(d, aid, herramientas, tipo, ambito_id).status_code == 422
    assert d.get(f"/asignaturas/{aid}/trabajos").json() == []
    assert d.get(f"/asignaturas/{aid}/recursos").json() == []


def test_generar_final_sin_rubrica_422(entorno, silabo):
    app, _, d, aid, _ = entorno
    app.state.asignaturas.guardar("dueno@uti.edu.ec",
                                  SilaboUTI.model_validate({**silabo.model_dump(), "rubrica_producto_final": []}))
    assert _sin_ia(d, aid, ["autoevaluacion_final"], "asignatura", "asignatura").status_code == 422
    assert d.get(f"/asignaturas/{aid}/trabajos").json() == []


def test_no_se_editan(entorno):
    _, _, d, aid, _ = entorno
    recurso = _recurso(d, aid, _sin_ia(d, aid, ["lista_evidencia"], "momento", "M3")).json()
    assert guardar(d, aid, recurso).status_code == 422


def test_silabo_actualizado_en_recurso_sin_ia(entorno, silabo):
    app, _, d, aid, _ = entorno
    m2 = _recurso(d, aid, _sin_ia(d, aid, ["autoevaluacion_rubrica"], "momento", "M2")).json()
    m3 = _recurso(d, aid, _sin_ia(d, aid, ["lista_evidencia"], "momento", "M3")).json()
    datos = silabo.model_dump()
    datos["proyecto_formativo"]["version"] = "2.0"
    datos["momentos"][0]["rubrica"][0]["indicador"] = "Indicador cambiado"
    app.state.asignaturas.guardar("dueno@uti.edu.ec", SilaboUTI.model_validate(datos))
    assert d.get(f"/asignaturas/{aid}/recursos/{m2['id']}").json()["silabo_actualizado"] is True
    assert d.get(f"/asignaturas/{aid}/recursos/{m3['id']}").json()["silabo_actualizado"] is False


def test_lector_no_genera_sin_ia(entorno):
    _, cliente, d, aid, _ = entorno
    assert compartir(d, aid, "lector@uti.edu.ec", "lector").status_code in (200, 201)
    lector = cliente("lector@uti.edu.ec")
    assert _sin_ia(lector, aid, ["hoja_ruta"], "asignatura", "asignatura").status_code == 403
    r = _sin_ia(d, aid, ["hoja_ruta"], "asignatura", "asignatura")
    assert _recurso(lector, aid, r).status_code == 200


def test_aislamiento(entorno, silabo):
    app, _, d, aid, _ = entorno
    otro = app.state.asignaturas.guardar("otro@uti.edu.ec",
                                         SilaboUTI.model_validate({**silabo.model_dump()}))["id"]
    r = _sin_ia(d, aid, ["hoja_ruta"], "asignatura", "asignatura")
    rid = r.json()["trabajos"][0]["recurso_id"]
    assert d.get(f"/asignaturas/{otro}/recursos/{rid}").status_code in (403, 404)
