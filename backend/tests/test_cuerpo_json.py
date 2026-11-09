"""El límite precede a la decodificación JSON, incluso en carga fragmentada."""
import anyio
import pytest

from app.api.cuerpo import LimiteJSON


@pytest.mark.parametrize("escenario,estado", [("largo", 413), ("fragmentado", 413),
    ("lento", 408), ("desconexion", 400), ("valido", 200)])
def test_cuerpo_json_acotado(escenario, estado):
    invocado, enviados = [], []

    async def ejecutar():
        leidos = 0

        async def recibir():
            nonlocal leidos
            leidos += 1
            if escenario == "lento":
                await anyio.sleep(5)
            if escenario == "desconexion":
                return {"type": "http.disconnect"}
            if escenario == "fragmentado":
                return {"type": "http.request", "body": b"xxxx", "more_body": leidos == 1}
            return {"type": "http.request", "body": b"xxxxxxxx" if escenario == "largo" else b"{}",
                    "more_body": False}

        async def enviar(mensaje):
            enviados.append(mensaje)

        async def app(scope, receive, send):
            invocado.append((await receive())["body"])
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        middleware = LimiteJSON(app, max_bytes=6, timeout_s=0.03)
        await middleware({"type": "http", "method": "PUT", "path": "/asignaturas/x/recursos/y",
                          "headers": [(b"content-length", b"1")]}, recibir, enviar)

    anyio.run(ejecutar)
    assert enviados[0]["status"] == estado
    assert invocado == ([b"{}"] if escenario == "valido" else [])
