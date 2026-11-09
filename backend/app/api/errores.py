"""Errores HTTP sin el contenido de peticiones, PDF ni excepciones internas."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import psycopg

from app.auth.servicio import AuthError
from app.control.limites import LimiteExcedido
from app.llm.cliente import ServidorNoDisponible
from app.silabo.lector.errores import SilaboIlegible


def registrar_errores(app: FastAPI) -> None:
    @app.exception_handler(LimiteExcedido)
    async def cuota(request: Request, exc: LimiteExcedido):
        return JSONResponse({"detail": "Demasiadas solicitudes"}, status_code=429,
                            headers={"Retry-After": str(exc.reintentar)})
    @app.exception_handler(AuthError)
    async def auth(request: Request, exc: AuthError):
        headers = {"Retry-After": str(exc.reintentar)} if exc.reintentar else {}
        return JSONResponse({"detail": exc.mensaje}, status_code=exc.codigo, headers=headers)

    @app.exception_handler(psycopg.Error)
    async def base_datos(request: Request, exc: psycopg.Error):
        return JSONResponse({"detail": "Servicio temporalmente no disponible"}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def validacion(request: Request, exc: RequestValidationError):
        # El manejador predeterminado incluye los valores recibidos.
        return JSONResponse({"detail": "Solicitud no válida"}, status_code=422)

    @app.exception_handler(SilaboIlegible)
    async def silabo(request: Request, exc: SilaboIlegible):
        return JSONResponse({"detail": "Sílabo no interpretable"}, status_code=422)

    @app.exception_handler(ServidorNoDisponible)
    async def servidor(request: Request, exc: ServidorNoDisponible):
        return JSONResponse({"detail": "Servidor de IA no disponible"}, status_code=503)
