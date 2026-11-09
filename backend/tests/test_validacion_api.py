"""P6b T1: el docente valida el recurso; una edición posterior anula la validación."""
from tests.test_generacion_api import HEADERS, compartir, entorno, guardar  # noqa: F401


def _validar(c, aid, recurso, revision=None):
    return c.post(f"/asignaturas/{aid}/recursos/{recurso['id']}/validar",
                  json={"revision": recurso["revision"] if revision is None else revision}, headers=HEADERS)


def test_validar_y_detalle(entorno):
    _, _, d, aid, producir = entorno
    recurso = producir()
    assert recurso["validado"] is False and recurso["validado_por"] is None
    r = _validar(d, aid, recurso)
    assert r.status_code == 200, r.text
    assert r.json()["validado"] is True and r.json()["validado_por"] == "dueno@uti.edu.ec"
    assert r.json()["validado_en"] is not None


def test_lector_no_valida(entorno):
    _, cliente, d, aid, producir = entorno
    recurso = producir()
    compartir(d, aid, "lector@uti.edu.ec", "lector")
    assert _validar(cliente("lector@uti.edu.ec"), aid, recurso).status_code == 403


def test_editar_anula_validacion(entorno):
    _, _, d, aid, producir = entorno
    recurso = producir()
    validado = _validar(d, aid, recurso).json()
    contenido = [dict(i) for i in validado["contenido"]]
    contenido[0]["pregunta"] = contenido[0]["pregunta"] + " (versión del docente)"
    r = guardar(d, aid, validado, contenido)
    assert r.status_code == 200, r.text
    assert r.json()["validado"] is False and r.json()["validado_por"] is None


def test_validar_revision_vieja_409(entorno):
    _, _, d, aid, producir = entorno
    recurso = producir()
    assert _validar(d, aid, recurso, revision=recurso["revision"] + 1).status_code == 409


def test_otra_asignatura_404(entorno, silabo):
    app, _, d, aid, producir = entorno
    recurso = producir()
    from app.silabo.modelo import SilaboUTI
    otra = app.state.asignaturas.guardar("dueno@uti.edu.ec", SilaboUTI.model_validate(
        {**silabo.model_dump(), "proyecto_formativo": {**silabo.proyecto_formativo.model_dump(), "codigo": "OTRA"}}))["id"]
    r = d.post(f"/asignaturas/{otra}/recursos/{recurso['id']}/validar", json={"revision": 0}, headers=HEADERS)
    assert r.status_code == 404
