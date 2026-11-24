"""Servidor aparte para el Monitor de Agentes UTI: solo la API UTI v1 (/v1), nada más del Generador.

Puede escuchar en la IP institucional (p. ej. 172.18.3.25:8766) sin exponer en la red el resto de la
API, que sigue en 127.0.0.1. Usa la misma base de datos y el mismo token del monitor
(MONITOR_TOKEN_HASH). Uso: python -m app.monitor_servidor --host 172.18.3.25 --port 8766
"""
import argparse
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.monitor_uti import router
from app.config import Ajustes, ajustes
from app.db.conexion import conectar
from app.db.pool import PoolConexiones


def crear_app_monitor(config: Ajustes | None = None, *, conexion=None) -> FastAPI:
    config = config or ajustes()
    pool = PoolConexiones(conexion or (lambda: conectar(config.database_url)))

    @asynccontextmanager
    async def vida(app):
        logging.getLogger("uvicorn.access").disabled = True  # no registrar rutas ni cabeceras
        try:
            yield
        finally:
            pool.cerrar()

    app = FastAPI(lifespan=vida, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.config = config
    app.state.conexion = pool
    app.include_router(router)
    return app


def main(argv=None):
    import uvicorn
    parser = argparse.ArgumentParser(description="API UTI v1 del Generador para el Monitor de Agentes")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Puerto fuera de rango")
    uvicorn.run("app.monitor_servidor:crear_app_monitor", factory=True, host=args.host, port=args.port,
                proxy_headers=False, access_log=False)


if __name__ == "__main__":
    main()
