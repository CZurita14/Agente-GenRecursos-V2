"""Cuentas locales de la etapa de pruebas (CUENTAS_LOCALES=true). Sin el modo encendido, las rutas no existen.

- Administración: crear cuentas con correo institucional (sin verificar el correo), restablecer la
  clave y activar o desactivar. El rol de administrador sale de la configuración.
- Docente con cuenta local: cambiar su clave y subir el PDF de su sílabo.
"""
from contextlib import closing

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.asignaturas import pdf
from app.auth.cuentas import correo_institucional

router = APIRouter()


class NuevaCuenta(BaseModel):
    correo: str = Field(min_length=3, max_length=254)
    nombre: str = Field(default="", max_length=200)
    clave: str = Field(min_length=1, max_length=256)

    def __repr__(self):
        return "NuevaCuenta(...)"


class Clave(BaseModel):
    clave: str = Field(min_length=1, max_length=256)

    def __repr__(self):
        return "Clave(...)"


class CambioClave(BaseModel):
    actual: str = Field(min_length=1, max_length=256)
    nueva: str = Field(min_length=1, max_length=256)

    def __repr__(self):
        return "CambioClave(...)"


class Estado(BaseModel):
    activa: bool


def _modo(request: Request):
    if not request.app.state.config.cuentas_locales:
        raise HTTPException(404, "No encontrado")
    return request.app.state.cuentas


def _admin(request: Request):
    cuentas = _modo(request)
    if request.state.usuario not in request.app.state.config.administradores:
        raise HTTPException(403, "Solo administradores")
    return cuentas


@router.get("/admin/cuentas")
def listar(request: Request):
    return _admin(request).listar()


@router.post("/admin/cuentas", status_code=201)
def crear(datos: NuevaCuenta, request: Request):
    return _admin(request).crear(datos.correo, datos.nombre, datos.clave, request.state.usuario)


@router.post("/admin/cuentas/{correo}/clave", status_code=204)
def restablecer(correo: str, datos: Clave, request: Request):
    _admin(request).restablecer(correo_institucional(correo), datos.clave)


@router.post("/admin/cuentas/{correo}/estado", status_code=204)
def activar(correo: str, datos: Estado, request: Request):
    _admin(request).activar(correo_institucional(correo), datos.activa)


@router.post("/auth/clave", status_code=204)
def cambiar_clave(datos: CambioClave, request: Request):
    if request.app.state.control is not None:
        # Cada intento cuenta, acierte o no: el mismo tope que la clave del panel de consumo.
        request.app.state.control.limites.consumir("consumo_clave_usuario_15min", request.state.usuario)
    _modo(request).cambiar_clave(request.state.usuario, datos.actual, datos.nueva)


@router.post("/silabos/pdf")
async def subir_pdf(request: Request):
    """Cuerpo: el PDF tal cual (Content-Type: application/pdf). Solo para cuentas locales."""
    cuentas = _modo(request)
    correo = request.state.usuario
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/pdf":
        raise HTTPException(415, "Sube el sílabo en PDF")
    if await run_in_threadpool(cuentas.estado, correo) is None:
        raise HTTPException(403, "Tus materias vienen del SGA")
    datos = await request.body()
    return await run_in_threadpool(_importar, request, correo, datos)


def _importar(request: Request, correo: str, datos: bytes):
    try:
        with closing(request.app.state.conexion()) as conn:
            conn.autocommit = True
            estado = pdf.importar(conn, correo, datos, request.app.state.asignaturas)
    except pdf.PdfNoDisponible as e:
        raise HTTPException(503, str(e)) from None
    except pdf.SilaboPdfIlegible as e:
        raise HTTPException(422, str(e)) from None
    return {"codigo_pf": estado.codigo_pf, "nombre": estado.nombre, "estado": estado.estado,
            "fallos": estado.fallos, "asignatura_id": estado.asignatura_id}
