"""Rutas de momentos: trazabilidad, contexto del docente y descarga del perfil docente."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

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


class PesosDocente(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # {"M2-S3/practico/practica_experimental": 7.5, …}: % de cada actividad dentro de su bloque. Solo números
    # finitos (el JSON de Python acepta NaN e Infinity, que esquivarían las comparaciones) y claves acotadas.
    pesos: dict[Annotated[str, StringConstraints(max_length=120)],
                Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]] = Field(max_length=400)


@router.put("/plan-evaluacion/pesos")
def guardar_pesos(asig: UUID, datos: PesosDocente, request: Request):
    """El docente confirma o ajusta los pesos dentro de cada calificación (V4-4); devuelve el plan actualizado."""
    return request.app.state.momentos.guardar_pesos(asig, request.state.usuario, datos.pesos)


class Parcial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bloque: StrictInt = Field(ge=1, le=10)


@router.get("/plan-evaluacion/lote")
def lote_parcial(asig: UUID, request: Request, bloque: int = Query(1, ge=1, le=10)):
    """V5-1: herramientas que «Preparar el parcial» encolaría y su costo estimado (no encola nada)."""
    return request.app.state.momentos.lote_parcial(asig, request.state.usuario, bloque)


@router.post("/plan-evaluacion/lote", status_code=202)
def preparar_parcial(asig: UUID, datos: Parcial, request: Request):
    """V5-1: encola las herramientas de las evaluaciones del bloque (recalculadas en el servidor)."""
    return request.app.state.momentos.preparar_parcial(asig, request.state.usuario, datos.bloque)


@router.delete("/plan-evaluacion/pesos")
def restaurar_pesos(asig: UUID, request: Request):
    """Vuelve a los pesos sugeridos para la versión actual del sílabo."""
    return request.app.state.momentos.restaurar_pesos(asig, request.state.usuario)


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
