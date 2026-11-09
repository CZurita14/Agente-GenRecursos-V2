"""Rutas de códigos y sesiones. El middleware comprueba origen y sesión."""
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth.servicio import AuthError, normalizar_correo

router = APIRouter(prefix="/auth")
INVITADO = "invitado@uti.edu.ec"


class PedidoCodigo(BaseModel):
    correo: str = Field(max_length=254)


class VerificarCodigo(PedidoCodigo):
    codigo: str = Field(max_length=64)


class AccesoPrueba(BaseModel):
    correo: str | None = Field(default=None, max_length=254)  # Sin correo: cuenta de invitado compartida.


def servicio(request):
    if request.app.state.auth is None:
        raise AuthError(503, "Autenticación no configurada")
    return request.app.state.auth


@router.post("/codigo")
def pedir(datos: PedidoCodigo, request: Request):
    correo = normalizar_correo(datos.correo)
    if request.app.state.control is not None:
        request.app.state.control.correo_publico(correo, "codigo")
    servicio(request).pedir(datos.correo)
    return {"mensaje": "Se ha solicitado un código de acceso"}


@router.post("/verificar")
def verificar(datos: VerificarCodigo, request: Request, response: Response):
    correo = normalizar_correo(datos.correo)
    if request.app.state.control is not None:
        request.app.state.control.correo_publico(correo, "verificar")
    token = servicio(request).verificar(datos.correo, datos.codigo)
    request.state.usuario = correo
    response.set_cookie("sesion", token, max_age=7 * 24 * 3600,
                        httponly=True, secure=True, samesite="lax", path="/")
    return {"mensaje": "Sesión iniciada"}


@router.get("/modo")
def modo(request: Request):
    """Público: la pantalla de ingreso decide si ofrece entrar sin código."""
    return {"acceso_prueba": request.app.state.config.acceso_prueba}


@router.post("/prueba")
def prueba(datos: AccesoPrueba, request: Request, response: Response):
    # La ruta no existe para quien no tenga el modo encendido; en producción la configuración lo prohíbe.
    if not request.app.state.config.acceso_prueba:
        raise HTTPException(404, "No encontrado")
    correo = normalizar_correo(datos.correo or INVITADO)
    if request.app.state.control is not None:
        request.app.state.control.correo_publico(correo, "verificar")
    token = servicio(request).sesion_directa(correo)
    request.state.usuario = correo
    response.set_cookie("sesion", token, max_age=7 * 24 * 3600,
                        httponly=True, secure=True, samesite="lax", path="/")
    return {"mensaje": "Sesión iniciada"}


@router.get("/yo")
def yo(request: Request):
    rol = "administrador" if request.state.usuario in request.app.state.config.administradores else "docente"
    return {"correo": request.state.usuario, "rol": rol}


@router.post("/salir")
def salir(request: Request, response: Response):
    servicio(request).salir(request.cookies.get("sesion"))
    response.delete_cookie("sesion", path="/", secure=True, httponly=True, samesite="lax")
    return {"mensaje": "Sesión cerrada"}
