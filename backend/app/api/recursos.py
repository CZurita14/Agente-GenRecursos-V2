"""Rutas A4: permisos y pertenencia se resuelven en ServicioRecursos."""
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.cola.trabajos import Ambito
from app.exportar.html import cabecera_descarga

router = APIRouter(prefix="/asignaturas/{asig}")


class AmbitoSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["clase", "momento", "asignatura"]
    id: str = Field(min_length=1, max_length=100)


class Generacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ambito: AmbitoSolicitud
    herramientas: list[str] = Field(min_length=1, max_length=20)
    cantidad: StrictInt = Field(default=12, ge=1, le=40)
    instrucciones: str = Field(default="", max_length=4000)
    perfil_dificultad: Literal["fundamentacion", "profesional", "avanzado"] | None = None


class Validacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: StrictInt = Field(ge=0)


class Edicion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: StrictInt = Field(ge=0)
    contenido: list[dict[str, Any]] | dict[str, Any]


@router.get("/herramientas")
def catalogo(asig: UUID, request: Request, ambito: Literal["clase", "momento", "asignatura"] = "clase",
             id: str | None = Query(None, min_length=1, max_length=100)):
    # Con `id`, el catálogo aplica la regla §9.4.2 del momento concreto.
    return request.app.state.recursos.catalogo(asig, request.state.usuario, ambito, id)


@router.post("/generar", status_code=202)
def generar(asig: UUID, datos: Generacion, request: Request):
    return request.app.state.recursos.generar(asig, request.state.usuario,
        Ambito(datos.ambito.tipo, datos.ambito.id), datos.herramientas, datos.cantidad,
        datos.instrucciones, datos.perfil_dificultad)


@router.get("/trabajos")
def trabajos(asig: UUID, request: Request, limite: int = Query(50, ge=1, le=200),
             desde: int = Query(0, ge=0, le=100000), ids: list[UUID] | None = Query(None, max_length=40)):
    return request.app.state.recursos.trabajos(asig, request.state.usuario, limite, desde, ids)


@router.get("/recursos")
def listar(asig: UUID, request: Request, limite: int = Query(50, ge=1, le=200),
           desde: int = Query(0, ge=0, le=100000)):
    return request.app.state.recursos.listar(asig, request.state.usuario, limite, desde)


@router.get("/recursos/{rid}")
def obtener(asig: UUID, rid: UUID, request: Request):
    return request.app.state.recursos.obtener(asig, rid, request.state.usuario)


@router.put("/recursos/{rid}")
def editar(asig: UUID, rid: UUID, datos: Edicion, request: Request):
    return request.app.state.recursos.editar(asig, rid, request.state.usuario, datos.revision, datos.contenido)


@router.post("/recursos/{rid}/validar")
def validar(asig: UUID, rid: UUID, datos: Validacion, request: Request):
    return request.app.state.recursos.validar(asig, rid, request.state.usuario, datos.revision)


@router.get("/recursos/{rid}/exportar")
def exportar(asig: UUID, rid: UUID, request: Request, formato: Literal["html", "pdf", "docx"] = "html",
             version: Literal["estudiante", "docente"] = "estudiante"):
    nombre, contenido = request.app.state.recursos.exportar(asig, rid, request.state.usuario, formato, version)
    mime = {"html": "text/html", "pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    return Response(contenido, media_type=mime[formato], headers={"Content-Disposition": cabecera_descarga(nombre),
                                            "Cache-Control": "private, no-store",
                                            "X-Content-Type-Options": "nosniff"})
