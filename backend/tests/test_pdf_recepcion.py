"""Recepción lenta/desconectada: cancela, limpia el PDF y libera cupos."""
import anyio
from fastapi import HTTPException
import pytest
from starlette.requests import Request

from app.api import asignaturas
from app.api.aplicacion import crear_app
from app.config import Ajustes


@pytest.mark.parametrize("escenario,estado", [("lento", 408), ("desconectado", 400)])
def test_recepcion_interrumpida_limpia_y_libera(tmp_path, monkeypatch, escenario, estado):
    config = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1",
                     llm_model="m", pdf_recepcion_timeout_s=0.03)
    llamadas = []
    app = crear_app(config, lector_pdf=lambda *a, **k: llamadas.append(a))
    original = asignaturas.TemporaryDirectory
    monkeypatch.setattr(asignaturas, "TemporaryDirectory", lambda **kw: original(dir=tmp_path, **kw))

    async def ejecutar():
        recibidos = 0

        async def recibir():
            nonlocal recibidos
            recibidos += 1
            if recibidos == 1:
                return {"type": "http.request", "body": b"%PDF-", "more_body": True}
            if escenario == "lento":
                await anyio.sleep(5)
            return {"type": "http.disconnect"}

        scope = {"type": "http", "app": app, "state": {"usuario": "dueno@uti.edu.ec"},
                 "headers": [(b"content-type", b"application/pdf")]}
        with pytest.raises(HTTPException) as exc:
            await asignaturas.subir(Request(scope, receive=recibir))
        assert exc.value.status_code == estado

    anyio.run(ejecutar)
    assert llamadas == [] and list(tmp_path.iterdir()) == []
    assert app.state.pdf_cupos.acquire(blocking=False)
    assert app.state.pdf_cupos.acquire(blocking=False)
    assert not app.state.pdf_cupos.acquire(blocking=False)
    app.state.pdf_cupos.release()
    app.state.pdf_cupos.release()
