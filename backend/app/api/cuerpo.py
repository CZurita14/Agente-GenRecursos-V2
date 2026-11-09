"""Acota JSON antes de que FastAPI lo decodifique; se ejecuta tras autenticar."""
import anyio
from starlette.responses import JSONResponse


class LimiteJSON:
    def __init__(self, app, *, max_bytes: int, timeout_s: float):
        self.app, self.max_bytes, self.timeout_s = app, max_bytes, timeout_s

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}
                or scope["path"] == "/silabos"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            declarado = int(headers.get(b"content-length", b"0"))
        except ValueError:
            await JSONResponse({"detail": "Longitud no válida"}, status_code=400)(scope, receive, send)
            return
        if declarado < 0 or declarado > self.max_bytes:
            await JSONResponse({"detail": "Solicitud demasiado grande"}, status_code=413)(scope, receive, send)
            return
        cuerpo = bytearray()
        try:
            with anyio.fail_after(self.timeout_s):
                while True:
                    mensaje = await receive()
                    if mensaje["type"] == "http.disconnect":
                        await JSONResponse({"detail": "Carga interrumpida"}, status_code=400)(scope, receive, send)
                        return
                    bloque = mensaje.get("body", b"")
                    if len(cuerpo) + len(bloque) > self.max_bytes:
                        await JSONResponse({"detail": "Solicitud demasiado grande"}, status_code=413)(scope, receive, send)
                        return
                    cuerpo.extend(bloque)
                    if not mensaje.get("more_body", False):
                        break
        except TimeoutError:
            await JSONResponse({"detail": "Se agotó el tiempo de carga"}, status_code=408)(scope, receive, send)
            return
        entregado = False

        async def recibir():
            nonlocal entregado
            if entregado:
                return await receive()
            entregado = True
            return {"type": "http.request", "body": bytes(cuerpo), "more_body": False}

        await self.app(scope, recibir, send)
