"""Proceso de consumidores: python worker.py; SIGTERM/SIGINT drenan trabajos.

MIGRAR_AL_INICIO=0 exige esquema preparado sin aplicar SQL. WORKER_GRACIA_S
(default 570, máximo 590) acota el drenaje antes del límite de Compose (600 s).
"""
import logging
import os
import signal
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg

from app.agentes.facultades import cargar_perfiles
from app.agentes.orquestador import procesar_uno
from app.config import RAIZ, ajustes
from app.db.conexion import conectar
from app.db.migrar import aplicar_migraciones, migraciones_preparadas
from app.llm.cliente import ClienteVLLM
from app.operacion import LatidoWorker, cargar_razonador, plazo_latido, ruta_latido, validar_configuracion
from app.razonador import RazonadorInvalido

registro = logging.getLogger(__name__)


def registrar_llamada(conn, datos):
    """Registra metadatos de uso; nunca persiste prompts ni razonamiento."""
    with conn.transaction():
        conn.execute(
            "insert into llamada_llm (trabajo_id,asignatura_id,rol,tokens_entrada,tokens_salida,segundos,ok) "
            "values (%(trabajo_id)s,%(asignatura_id)s,%(rol)s,%(tokens_entrada)s,%(tokens_salida)s,%(segundos)s,%(ok)s)", datos,
        )


def preparar_esquema(config):
    with conectar(config.database_url) as conn:
        conn.autocommit = True
        if os.environ.get('MIGRAR_AL_INICIO', '1') == '0':
            if not migraciones_preparadas(conn):
                raise RuntimeError('Esquema no preparado')
        else:
            aplicar_migraciones(conn)


class ClienteConLatido(ClienteVLLM):
    """Renueva progreso en límites de llamadas, nunca desde un hilo paralelo.

    contar_tokens separa sus dos intentos de los dos de completar. Un trabajo
    puede incluir muchos lotes; cada llamada acotada prueba progreso real.
    """
    def __init__(self, *args, pulsar, **kwargs):
        self._pulsar = pulsar
        super().__init__(*args, **kwargs)

    def contar_tokens(self, mensajes):
        self._pulsar()
        try:
            return super().contar_tokens(mensajes)
        finally:
            self._pulsar()

    def completar(self, *args, **kwargs):
        self._pulsar()
        try:
            return super().completar(*args, **kwargs)
        finally:
            self._pulsar()


def cerrar_consumidores(pool, cliente, gracia, *, forzar=os._exit):
    """Los hilos Python no son cancelables; un watchdog acota hasta su cierre."""
    temporizador = threading.Timer(gracia, lambda: forzar(1))
    temporizador.daemon = True
    temporizador.start()
    try:
        pool.shutdown(wait=True, cancel_futures=True)
        cliente.close()
    finally:
        temporizador.cancel()


def main():
    config = ajustes()
    try:
        validar_configuracion(config)
    except ValueError as error:
        registro.error('configuración inválida: %s', error)  # Mensajes fijos, sin rutas ni valores.
        raise
    plazo_latido(config)  # Rechaza timeouts sin límite antes de lanzar consumidores.
    gracia = float(os.environ.get('WORKER_GRACIA_S', '570'))
    if not 0 < gracia <= 590 or config.llm_max_concurrencia < 1:
        raise ValueError('Configuración de worker inválida')
    directorio = config.agentes_dir if config.agentes_dir.is_absolute() else RAIZ / config.agentes_dir
    perfiles = cargar_perfiles(directorio)
    try:
        razonador = cargar_razonador(config)  # Una sola vez; un modelo inválido detiene el arranque.
    except RazonadorInvalido as error:
        registro.error('razonador inválido: %s', error)  # El mensaje nombra la causa, nunca un texto.
        raise
    if razonador is not None:
        registro.info('razonador cargado: version=%s', razonador.version)
    preparar_esquema(config)
    latido = LatidoWorker(ruta_latido(), config.llm_max_concurrencia)
    latido.escribir()  # Invalida cualquier archivo de un arranque anterior.
    detener = threading.Event()
    local = threading.local()

    def pulsar():
        latido.pulsar(local.numero)

    def registrar(datos):
        with conectar(config.database_url) as conn:
            registrar_llamada(conn, datos)

    cliente = ClienteConLatido(config.llm_base_url, config.llm_model, config.llm_timeout_s,
                              config.llm_max_concurrencia, registrar, config.llm_api_key,
                              proveedor=config.llm_proveedor, tls_estricto=config.llm_tls_estricto,
                              pulsar=pulsar)

    def consumir(numero):
        local.numero = numero
        worker_id = f'{uuid.uuid4()}-{numero}'
        while not detener.is_set():
            latido.pulsar(numero)
            try:
                with conectar(config.database_url) as conn:
                    conn.autocommit = True
                    while not detener.is_set():
                        latido.pulsar(numero)
                        trabajo = procesar_uno(conn, cliente, perfiles, worker_id, config.lease_s,
                                               razonador=razonador)
                        latido.pulsar(numero)
                        if not trabajo:
                            detener.wait(2)
            except psycopg.Error:
                registro.error('conexión de base de datos interrumpida (worker %s)', numero)
                detener.wait(2)

    anteriores = {}
    def solicitar_cierre(signum, frame):
        detener.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        anteriores[sig] = signal.signal(sig, solicitar_cierre)
    pool = ThreadPoolExecutor(max_workers=config.llm_max_concurrencia)
    try:
        futuros = [pool.submit(consumir, n) for n in range(config.llm_max_concurrencia)]
        while not detener.wait(1):
            for futuro in futuros:
                if futuro.done():
                    futuro.result()  # No dejar morir un consumidor silenciosamente.
                    raise RuntimeError('Consumidor detenido')
            latido.escribir()
    except KeyboardInterrupt:
        detener.set()
    finally:
        detener.set()
        try:
            latido.detener()
        finally:
            try:
                cerrar_consumidores(pool, cliente, gracia)
            finally:
                for sig, anterior in anteriores.items():
                    signal.signal(sig, anterior)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        main()
    except Exception:
        registro.error('No se pudo ejecutar el worker')
        raise SystemExit(1) from None
