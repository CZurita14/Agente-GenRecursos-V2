"""Fábrica ASGI: salud pública y aplicación cerrada hasta autenticar (A2)."""
from contextlib import asynccontextmanager
from threading import BoundedSemaphore
import logging
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
import psycopg

from app.agentes.facultades import cargar_catalogo, cargar_perfiles
from app.api.asignaturas import router as asignaturas_router
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.cuerpo import LimiteJSON
from app.api.recursos import router as recursos_router
from app.api.chat import router as chat_router
from app.api.privacidad import router as privacidad_router
from app.api.errores import registrar_errores
from app.auth.correo import transporte_correo
from app.auth.servicio import ServicioAuth
from app.config import RAIZ, Ajustes, ajustes
from app.db.conexion import conectar
from app.db.pool import PoolConexiones
from app.asignaturas.servicio import ServicioAsignaturas
from app.recursos.servicio import ServicioRecursos
from app.control.identidad import ProxyInvalido, ip_cliente, operacion_segura
from app.control.limites import LimiteExcedido
from app.control.servicio import ControlAcceso
from app.operacion import preparado


def crear_app(config: Ajustes | None = None, *, transporte=None, auth=None, conexion=None, lector_pdf=None) -> FastAPI:
    config = config or ajustes()
    # Toda conexión de la API pasa por el pool: sin él, cada petición abría al menos cinco.
    conexion = PoolConexiones(conexion or (lambda: conectar(config.database_url)))

    @asynccontextmanager
    async def vida(app):
        # El logger de uvicorn imprime rutas y query strings sin sanear.
        logging.getLogger("uvicorn.access").disabled = True
        directorio = config.agentes_dir
        if not directorio.is_absolute():
            directorio = RAIZ / directorio
        app.state.perfiles = cargar_perfiles(directorio)
        app.state.asignaturas = ServicioAsignaturas(conexion, cargar_catalogo(RAIZ / "kb/catalogo.yaml"),
                                                    app.state.perfiles)
        app.state.recursos = ServicioRecursos(conexion, app.state.perfiles)
        async with httpx.AsyncClient(timeout=5, transport=transporte,
                                     headers={"Authorization": f"Bearer {config.llm_api_key}"}) as cliente:
            app.state.ia = cliente
            try:
                yield
            finally:
                conexion.cerrar()

    app = FastAPI(lifespan=vida, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    app.state.conexion = conexion
    if auth is not None and config.auth_secreto is None:
        raise ValueError("La autenticación inyectada requiere AUTH_SECRETO para proteger cuotas y registros")
    app.state.control = ControlAcceso(conexion, config) if config.auth_secreto else None
    app.state.pdf_cupos = BoundedSemaphore(2)
    if lector_pdf is None:
        from app.silabo.aislado import leer_pdf_aislado
        lector_pdf = leer_pdf_aislado
    app.state.lector_pdf = lector_pdf
    app.state.auth = auth
    if auth is None and config.auth_secreto is not None:
        app.state.auth = ServicioAuth(conexion,
                                      config.auth_secreto.get_secret_value(), transporte_correo(config))
    registrar_errores(app)
    app.include_router(auth_router)
    app.include_router(asignaturas_router)
    app.include_router(recursos_router)
    app.include_router(chat_router)
    app.include_router(admin_router)
    app.include_router(privacidad_router)
    # La incorporación previa al middleware de acceso lo deja por dentro:
    # CORS → sesión/Origin → límite de cuerpo → parser JSON/rutas.
    app.add_middleware(LimiteJSON, max_bytes=config.api_json_max_bytes, timeout_s=config.api_json_timeout_s)

    async def proteger(request, siguiente, ip, operacion, proxy_invalido):
        control = app.state.control
        if control is not None:
            await run_in_threadpool(control.ip, ip, operacion, request.method)
        if proxy_invalido:
            return JSONResponse({"detail": "Cadena de proxy inválida"}, status_code=400)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") != config.api_origen:
                return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
        publica = ((request.method in {"GET", "HEAD"} and request.url.path in {"/salud", "/auth/modo"})
                   or (request.method == "POST" and request.url.path in {"/auth/codigo", "/auth/verificar", "/auth/prueba"}))
        if not publica:
            usuario = None
            if app.state.auth is not None and request.cookies.get("sesion"):
                usuario = await run_in_threadpool(app.state.auth.identificar, request.cookies["sesion"])
            if usuario is None:
                return JSONResponse({"detail": "Sesión requerida"}, status_code=401)
            request.state.usuario = usuario
            if control is not None:
                await run_in_threadpool(control.usuario, usuario, operacion, request.method)
        return await siguiente(request)

    @app.middleware("http")
    async def acceso(request: Request, siguiente):
        # Sondas internas exactas y de solo lectura. No dependen de sesión,
        # cuotas ni auditoría: estas también requieren la BD que comprobamos.
        if request.method in {"GET", "HEAD"} and request.url.path in {"/salud/vivo", "/salud/listo"}:
            return await siguiente(request)
        inicio = time.monotonic()
        request.state.usuario = None
        try:
            ip = ip_cliente(request, config.proxies_confiables)
            proxy_invalido = False
        except ProxyInvalido:
            # Cuota separada para rechazos; nunca consume la identidad del proxy.
            ip, proxy_invalido = "proxy-invalido", True
        operacion = operacion_segura(request.url.path)
        try:
            respuesta = await proteger(request, siguiente, ip, operacion, proxy_invalido)
        except LimiteExcedido as exc:
            respuesta = JSONResponse({"detail": "Demasiadas solicitudes"}, status_code=429,
                                     headers={"Retry-After": str(exc.reintentar)})
        except psycopg.Error:
            respuesta = JSONResponse({"detail": "Servicio temporalmente no disponible"}, status_code=503)
        except Exception as exc:
            logging.getLogger(__name__).warning("Solicitud fallida (%s)", type(exc).__name__)
            respuesta = JSONResponse({"detail": "No se pudo completar la solicitud"}, status_code=500)
        if app.state.control is not None:
            await run_in_threadpool(app.state.control.registrar, ip, request.state.usuario, operacion,
                                     request.method, respuesta.status_code, int((time.monotonic() - inicio) * 1000))
        return respuesta

    # CORS envuelve también los rechazos del control de acceso.
    app.add_middleware(CORSMiddleware, allow_origins=[config.api_origen],
                       allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"],
                       allow_headers=["Content-Type"])

    @app.get("/salud")
    async def salud():
        disponible = False
        try:
            r = await app.state.ia.get(config.llm_base_url.rstrip("/") + "/models")
            r.raise_for_status()
            datos = r.json()
            modelos = datos.get("data", []) if isinstance(datos, dict) else []
            disponible = isinstance(modelos, list) and any(
                isinstance(m, dict) and m.get("id") == config.llm_model
                and m.get("max_model_len") == 8192 for m in modelos)
        except (httpx.HTTPError, ValueError):
            pass
        return JSONResponse({"estado": "ok" if disponible else "degradado",
                             "ia": disponible, "agentes": sorted(app.state.perfiles)},
                            status_code=200 if disponible else 503)

    @app.api_route("/salud/vivo", methods=["GET", "HEAD"])
    async def vivo():
        return JSONResponse({"estado": "ok"}, headers={"Cache-Control": "no-store"})

    @app.api_route("/salud/listo", methods=["GET", "HEAD"])
    async def listo():
        ok = await run_in_threadpool(preparado, config, conexion=conexion,
                                    perfiles=getattr(app.state, "perfiles", {}))
        return JSONResponse({"estado": "ok" if ok else "no-listo"},
                            status_code=200 if ok else 503,
                            headers={"Cache-Control": "no-store"})

    return app
