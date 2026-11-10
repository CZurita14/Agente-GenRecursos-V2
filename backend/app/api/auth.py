"""Rutas de ingreso con el SGA y sesiones. El middleware comprueba origen y sesión."""
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth.servicio import AuthError, normalizar_correo

router = APIRouter(prefix="/auth")
INVITADO = "invitado@uti.edu.ec"


class Ingreso(BaseModel):
    usuario: str = Field(min_length=1, max_length=128)
    clave: str = Field(min_length=1, max_length=256)

    def __repr__(self):  # La clave no debe aparecer en trazas ni en mensajes de error.
        return "Ingreso(...)"


class AccesoPrueba(BaseModel):
    correo: str | None = Field(default=None, max_length=254)  # Sin correo: cuenta de invitado compartida.


def servicio(request):
    if request.app.state.auth is None:
        raise AuthError(503, "Autenticación no configurada")
    return request.app.state.auth


COOKIE = dict(max_age=7 * 24 * 3600, httponly=True, secure=True, samesite="lax", path="/")


@router.post("/ingresar")
def ingresar(datos: Ingreso, request: Request, response: Response):
    usuario = datos.usuario.strip()
    if request.app.state.control is not None:
        # Solo la cuota (y el bloqueo, en el servicio) ignoran mayúsculas; el SGA recibe lo tecleado.
        request.app.state.control.usuario_publico(usuario.lower())
    auth = servicio(request)
    token = auth.ingresar(usuario, datos.clave)
    correo = auth.identificar(token)
    request.state.usuario = correo
    response.set_cookie("sesion", token, **COOKIE)
    # Misma consulta y mismo orden que GET /materias.
    return {"correo": correo, "materias": request.app.state.asignaturas.materias(correo)}


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
        request.app.state.control.usuario_publico(correo)
    token = servicio(request).sesion_directa(correo)
    request.state.usuario = correo
    response.set_cookie("sesion", token, **COOKIE)
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
