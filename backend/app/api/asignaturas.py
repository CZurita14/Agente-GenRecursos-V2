"""Subida binaria acotada y rutas de asignaturas; no se conserva el PDF."""
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from uuid import UUID

import anyio
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

router = APIRouter()


class Compartir(BaseModel):
    correo: str = Field(max_length=254)
    rol: Literal["editor", "lector"]


@router.post("/silabos", status_code=201)
async def subir(request: Request):
    config = request.app.state.config
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/pdf":
        raise HTTPException(415, "Se requiere application/pdf")
    declarado = request.headers.get("content-length")
    if declarado is not None:
        try:
            cantidad = int(declarado)
        except ValueError:
            raise HTTPException(400, "Longitud no válida") from None
        if cantidad < 0:
            raise HTTPException(400, "Longitud no válida")
        if cantidad > config.pdf_max_bytes:
            raise HTTPException(413, "PDF demasiado grande")
    cupos = request.app.state.pdf_cupos
    if not cupos.acquire(blocking=False):
        raise HTTPException(503, "Lector ocupado; intente de nuevo")
    try:
        with TemporaryDirectory(prefix="uti-pdf-") as directorio:
            ruta = Path(directorio) / "silabo.pdf"
            total = 0
            with ruta.open("wb") as archivo:
                try:
                    with anyio.fail_after(config.pdf_recepcion_timeout_s):
                        async for bloque in request.stream():
                            total += len(bloque)
                            if total > config.pdf_max_bytes:
                                raise HTTPException(413, "PDF demasiado grande")
                            archivo.write(bloque)
                except TimeoutError:
                    raise HTTPException(408, "Se agotó el tiempo de carga") from None
                except ClientDisconnect:
                    raise HTTPException(400, "Carga interrumpida") from None
            if total == 0:
                raise HTTPException(422, "PDF vacío")
            with ruta.open("rb") as archivo:
                if archivo.read(5) != b"%PDF-":
                    raise HTTPException(415, "El archivo no es un PDF")
            silabo = await run_in_threadpool(request.app.state.lector_pdf, ruta,
                                             timeout_s=config.pdf_timeout_s,
                                             memoria_mb=config.pdf_memoria_mb)
        # El original ya fue eliminado antes de abrir la transacción de asignatura.
        return await run_in_threadpool(request.app.state.asignaturas.guardar,
                                        request.state.usuario, silabo)
    finally:
        cupos.release()


@router.get("/asignaturas")
def listar(request: Request):
    return request.app.state.asignaturas.listar(request.state.usuario)


@router.get("/asignaturas/{asig}/menu")
def menu(asig: UUID, request: Request):
    return request.app.state.asignaturas.menu(asig, request.state.usuario)


@router.post("/asignaturas/{asig}/compartir")
def compartir(asig: UUID, datos: Compartir, request: Request):
    return request.app.state.asignaturas.compartir(asig, request.state.usuario, datos.correo, datos.rol)


@router.delete("/asignaturas/{asig}/compartir/{correo:path}", status_code=204)
def retirar(asig: UUID, correo: str, request: Request):
    request.app.state.asignaturas.retirar(asig, request.state.usuario, correo)
    return Response(status_code=204)
