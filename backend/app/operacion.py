"""Operación interna: python -m app.operacion {migrar,preparado,salud-worker}.

Salida JSON mínima y código 0/1. No consulta IA. El contenedor usa
/tmp/worker-salud.json (WORKER_SALUD_ARCHIVO permite una ruta alternativa).
WORKER_GRACIA_S limita el cierre a 570 s por defecto, siempre menos de 600 s.
"""
import argparse
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time

import psycopg

from app.agentes.facultades import cargar_perfiles
from app.config import RAIZ, ajustes
from app.db.conexion import conectar
from app.db.migrar import aplicar_migraciones, migraciones_preparadas


def validar_configuracion(config):
    """Validación técnica de producción, sin banderas de aprobación humana."""
    if config.razonador_ruta is not None and not _ruta_razonador(config).is_dir():
        raise ValueError('RAZONADOR_RUTA no es una carpeta')
    if config.entorno != 'produccion':
        return
    secreto = config.auth_secreto.get_secret_value() if config.auth_secreto else ''
    if (len(secreto) < 32 or len(set(secreto)) < 8
            or not config.api_origen.startswith('https://')
            or not config.administradores):
        raise ValueError('Configuración de producción incompleta')
    if config.sga_proveedor == 'simulado':
        raise ValueError('SGA_PROVEEDOR=simulado no se permite en producción')


def _ruta_razonador(config) -> Path:
    ruta = config.razonador_ruta
    return ruta if ruta.is_absolute() else RAIZ / ruta


def cargar_razonador(config):
    """Modelo del worker, o None sin RAZONADOR_RUTA. Solo producción exige modelo aprobado."""
    if config.razonador_ruta is None:
        return None
    from app.razonador import Razonador  # Las sondas y la API no necesitan numpy.
    return Razonador.cargar(_ruta_razonador(config), exigir_aprobado=config.entorno == 'produccion')


def preparado(config, *, conexion=None, perfiles=None) -> bool:
    try:
        if perfiles is None:
            directorio = config.agentes_dir
            perfiles = cargar_perfiles(directorio if directorio.is_absolute() else RAIZ / directorio)
        if not perfiles or 'general' not in perfiles:
            return False
        with (conexion or (lambda: psycopg.connect(config.database_url, connect_timeout=5,
                                                 row_factory=psycopg.rows.dict_row)))() as conn:
            conn.autocommit = True
            conn.execute("set statement_timeout = '5s'")
            return migraciones_preparadas(conn)
    except Exception:
        return False


def ruta_latido() -> Path:
    return Path(os.environ.get('WORKER_SALUD_ARCHIVO', '/tmp/worker-salud.json'))


def identidad_proceso(pid: int) -> str:
    """Identidad del arranque del SO y proceso; detecta PID reutilizados."""
    if pid <= 0:
        raise ValueError('PID inválido')
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            raise OSError('Proceso no disponible')
        try:
            tiempos = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in tiempos)):
                raise OSError('Proceso no disponible')
            return str((tiempos[0].dwHighDateTime << 32) | tiempos[0].dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    estado = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    if estado[0] in {'Z', 'X'}:
        raise OSError('Proceso terminado')
    arranque = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    return f'{arranque}:{estado[19]}'


def plazo_latido(config) -> float:
    plazo = 2 * max(config.llm_timeout_s, config.llm_timeout_revisor_s) + 60
    if not math.isfinite(plazo) or plazo <= 60:
        raise ValueError('Timeout inválido')
    return plazo


class LatidoWorker:
    """El supervisor escribe, pero solo cada consumidor renueva su progreso.

    Usamos reloj monotónico del SO (compartido entre procesos) e identidad de
    inicio; los ajustes del reloj civil no ocultan un consumidor bloqueado.
    """
    def __init__(self, ruta, consumidores, *, reloj=time.monotonic, identidad=identidad_proceso):
        if consumidores < 1:
            raise ValueError('Consumidores inválidos')
        self.ruta, self.reloj = Path(ruta), reloj
        self.pid = os.getpid()
        self.inicio = identidad(self.pid)
        self.consumidores = {str(n): None for n in range(consumidores)}
        self.candado = threading.Lock()
        self.detenido = False

    def pulsar(self, numero):
        with self.candado:
            self.consumidores[str(numero)] = self.reloj()

    def escribir(self):
        with self.candado:
            datos = dict(pid=self.pid, inicio=self.inicio, actualizado=self.reloj(),
                         consumidores=dict(self.consumidores), detenido=self.detenido)
        # Reemplazo atómico y permisos 0600; no requiere escribir en el código.
        fd, temporal = tempfile.mkstemp(prefix='.worker-salud-', dir=self.ruta.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as archivo:
                json.dump(datos, archivo)
            os.replace(temporal, self.ruta)
        finally:
            if os.path.exists(temporal):
                os.unlink(temporal)

    def detener(self):
        with self.candado:
            self.detenido = True
        self.escribir()


def salud_worker(config, *, ruta=None, reloj=time.monotonic, identidad=identidad_proceso) -> bool:
    try:
        archivo = Path(ruta) if ruta is not None else ruta_latido()
        if archivo.stat().st_size > 65536:
            return False
        datos = json.loads(archivo.read_text(encoding='utf-8'))
        if datos['detenido'] is not False or identidad(datos['pid']) != datos['inicio']:
            return False
        consumidores = datos['consumidores']
        if set(consumidores) != {str(n) for n in range(config.llm_max_concurrencia)}:
            return False
        ahora, plazo = reloj(), plazo_latido(config)
        def reciente(valor, limite):
            return (isinstance(valor, (int, float)) and not isinstance(valor, bool)
                    and math.isfinite(valor) and 0 <= ahora - valor <= limite)
        return (reciente(datos['actualizado'], 10)
                and all(reciente(t, plazo) for t in consumidores.values()))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('comando', choices=['migrar', 'preparado', 'salud-worker', 'health-worker'])
    comando = parser.parse_args(argv).comando
    ok = False
    try:
        config = ajustes()
        if comando in {'migrar', 'preparado'}:
            validar_configuracion(config)
        if comando == 'migrar':
            with conectar(config.database_url) as conn:
                conn.autocommit = True
                aplicar_migraciones(conn)
            ok = True
        elif comando == 'preparado':
            ok = preparado(config)
        else:
            ok = salud_worker(config)
    except Exception:
        pass  # Nunca imprimir configuración, SQL ni excepciones con credenciales.
    print(json.dumps({'estado': 'ok' if ok else 'no-listo'}))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
