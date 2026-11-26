"""Rutas de momentos: trazabilidad, contexto del docente y descarga del perfil docente."""
from uuid import UUID

from fastapi import APIRouter, Path, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.exportar.html import cabecera_descarga

router = APIRouter(prefix="/asignaturas/{asig}")


class ContextoMomento(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: StrictInt = Field(ge=0)
    texto: str = Field(max_length=8000)


@router.get("/momentos")
def momentos(asig: UUID, request: Request):
    return request.app.state.momentos.momentos(asig, request.state.usuario)


@router.get("/plan-evaluacion")
def plan_evaluacion(asig: UUID, request: Request):
    """Plan de evaluación implícito en el sílabo (norma del RRA, bloques, pesos sugeridos y alertas)."""
    return request.app.state.momentos.plan_evaluacion(asig, request.state.usuario)


@router.put("/momentos/{numero}/contexto")
def guardar_contexto(asig: UUID, datos: ContextoMomento, request: Request, numero: int = Path(ge=1, le=20)):
    return request.app.state.momentos.guardar_contexto(asig, request.state.usuario, numero, datos.revision,
                                                       datos.texto)


@router.get("/descarga/resumen")
def resumen_descarga(asig: UUID, request: Request):
    return request.app.state.momentos.resumen_descarga(asig, request.state.usuario)


@router.get("/descarga")
def descarga(asig: UUID, request: Request):
    nombre, contenido = request.app.state.momentos.descarga(asig, request.state.usuario)
    return Response(contenido, media_type="application/zip",
                    headers={"Content-Disposition": cabecera_descarga(nombre), "Cache-Control": "private, no-store",
                             "X-Content-Type-Options": "nosniff"})
