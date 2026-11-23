"""Panel de consumo de tokens. Solo los proyectos formativos de la cuenta; administradores o clave del panel.

La clave nunca llega a logs ni a la bitácora (que no guarda cuerpos). El desbloqueo deja una cookie
HttpOnly firmada con AUTH_SECRETO, ligada al hash del token de sesión y válida 30 minutos.
"""
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import hmac
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.control.clave import verificar
from app.control.consumo import resumen

router = APIRouter(prefix="/consumo")
DURACION = timedelta(minutes=30)
COOKIE = dict(max_age=int(DURACION.total_seconds()), httponly=True, secure=True, samesite="lax", path="/")


class Desbloqueo(BaseModel):
    clave: str = Field(min_length=1, max_length=256)

    def __repr__(self):  # La clave no debe aparecer en trazas ni en mensajes de error.
        return "Desbloqueo(...)"


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _firma(request: Request, exp: int) -> str:
    sesion = hashlib.sha256(request.cookies.get("sesion", "").encode()).hexdigest()
    secreto = request.app.state.config.auth_secreto.get_secret_value().encode()
    return hmac.new(secreto, f"{sesion}|{exp}".encode(), hashlib.sha256).hexdigest()


def _desbloqueado(request: Request) -> bool:
    valor = request.cookies.get("consumo", "")
    exp, _, firma = valor.partition(".")
    if not exp.isdigit() or int(exp) <= _ahora().timestamp():
        return False
    return hmac.compare_digest(firma, _firma(request, int(exp)))


def _exigir_acceso(request: Request) -> None:
    if request.state.usuario in request.app.state.config.administradores:
        return
    if not _desbloqueado(request):
        raise HTTPException(403, "Ingresa la clave del panel")


@router.post("/desbloquear", status_code=204)
def desbloquear(datos: Desbloqueo, request: Request, response: Response):
    config = request.app.state.config
    if config.consumo_clave_hash is None or config.auth_secreto is None:
        raise HTTPException(503, "El panel de consumo no tiene clave configurada")
    if request.app.state.control is not None:
        # Cada intento cuenta, acierte o no: 5 cada 15 minutos por usuario.
        request.app.state.control.limites.consumir("consumo_clave_usuario_15min", request.state.usuario)
    if not verificar(datos.clave, config.consumo_clave_hash.get_secret_value()):
        raise HTTPException(403, "Clave incorrecta")
    exp = int((_ahora() + DURACION).timestamp())
    response.set_cookie("consumo", f"{exp}.{_firma(request, exp)}", **COOKIE)


@router.get("")
def consumo(request: Request, desde: date | None = None, hasta: date | None = None, asignatura: UUID | None = None):
    _exigir_acceso(request)
    hasta = hasta or _ahora().date()
    desde = desde or hasta - timedelta(days=6)
    if hasta < desde or (hasta - desde).days >= 31:
        raise HTTPException(422, "Intervalo máximo de 31 días")
    inicio = datetime.combine(desde, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=timezone.utc)
    config = request.app.state.config
    precios = ((config.llm_precio_entrada_usd_mtok, config.llm_precio_salida_usd_mtok)
               if config.llm_precio_entrada_usd_mtok is not None and config.llm_precio_salida_usd_mtok is not None
               else None)
    correo = request.state.usuario
    with closing(request.app.state.conexion()) as conn:
        conn.autocommit = True
        conn.execute("set statement_timeout to '3s'")
        propias = [f["id"] for f in conn.execute(
            "select id from asignatura where dueno=%s or id in "
            "(select asignatura_id from asignatura_acceso where correo=%s)", (correo, correo))]
        if asignatura is not None:
            if asignatura not in propias:
                raise HTTPException(404, "Proyecto Formativo inexistente")
            propias = [asignatura]
        datos = resumen(conn, propias, inicio, fin, precios)
    return {"desde": desde, "hasta": hasta, **datos}
