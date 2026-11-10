"""Rutas de materias y asignaturas del docente; los sílabos llegan del SGA, no se suben."""
from uuid import UUID

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/materias")
def materias(request: Request):
    return request.app.state.asignaturas.materias(request.state.usuario)


@router.get("/asignaturas")
def listar(request: Request):
    return request.app.state.asignaturas.listar(request.state.usuario)


@router.get("/asignaturas/{asig}/menu")
def menu(asig: UUID, request: Request):
    return request.app.state.asignaturas.menu(asig, request.state.usuario)
