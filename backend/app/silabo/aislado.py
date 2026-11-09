"""Lectura P2 en proceso desechable; no importa configuración de la aplicación."""
from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.silabo.modelo import SilaboUTI

MENSAJE_ERROR = "El sílabo tiene un formato que no se pudo leer."
MAX_RESULTADO = 4 * 1024 * 1024
MAX_PDF = 50 * 1024 * 1024


def _limitar_memoria(memoria_mb: int):
    """Devuelve un cierre del Job; mantiene su handle vivo durante toda la lectura."""
    limite = memoria_mb * 1024 * 1024
    if os.name != "nt":
        import resource
        _, duro = resource.getrlimit(resource.RLIMIT_AS)
        if duro != resource.RLIM_INFINITY:
            limite = min(limite, duro)
        resource.setrlimit(resource.RLIMIT_AS, (limite, limite))
        return lambda: None

    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                              ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError("memory limit unavailable")
    try:
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = limite
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise OSError("memory limit unavailable")
        if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
            raise OSError("memory limit unavailable")
    except BaseException:
        kernel.CloseHandle(job)
        raise
    return lambda: kernel.CloseHandle(job)


def _entorno_hijo() -> dict[str, str]:
    # Lista positiva: no heredar claves API, credenciales ni PYTHONPATH/PYTHONSTARTUP.
    return {k: v for k, v in os.environ.items()
            if k.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}}


def leer_pdf_aislado(ruta: Path, *, timeout_s: float = 20, memoria_mb: int = 512) -> SilaboUTI:
    """La ruta original se abre solo en el hijo y nunca se elimina.

    Timeout incluye arranque e imports. Cada fallo usa el mismo mensaje público.
    El límite Windows controla memoria comprometida; POSIX, espacio virtual.
    """
    try:
        if (isinstance(timeout_s, bool) or not math.isfinite(timeout_s) or timeout_s <= 0
                or isinstance(memoria_mb, bool) or not isinstance(memoria_mb, int)
                or memoria_mb <= 0 or memoria_mb * 1024 * 1024 > sys.maxsize):
            raise ValueError
        origen = Path(ruta).resolve(strict=True)
        with tempfile.TemporaryDirectory(prefix="silabo-aislado-") as temporal:
            salida = Path(temporal) / "resultado.json"
            comando = [sys.executable, "-E", "-s", "-B", "-m", "app.silabo.aislado",
                       "child", str(origen), str(salida), str(memoria_mb)]
            with subprocess.Popen(comando, cwd=Path(__file__).resolve().parents[2],
                                  env=_entorno_hijo(), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  close_fds=True, shell=False) as proceso:
                try:
                    codigo = proceso.wait(timeout=timeout_s)
                except BaseException:
                    proceso.kill()
                    proceso.wait()
                    raise
            if codigo != 0:
                raise ValueError
            with salida.open("rb") as archivo:
                contenido = archivo.read(MAX_RESULTADO + 1)
            if not contenido or len(contenido) > MAX_RESULTADO:
                raise ValueError
            from app.silabo.modelo import SilaboUTI
            return SilaboUTI.model_validate_json(contenido)
    except Exception:
        # Import diferido: ejecutar el módulo child no importa P2 antes del límite.
        from app.silabo.lector.errores import SilaboIlegible
        raise SilaboIlegible(MENSAJE_ERROR) from None


def _child(ruta: Path, salida: Path, memoria_mb: int) -> int:
    cerrar = None
    try:
        if memoria_mb <= 0 or memoria_mb * 1024 * 1024 > sys.maxsize:
            return 1
        cerrar = _limitar_memoria(memoria_mb)
        from app.silabo.lector import leer_silabo
        with ruta.open("rb") as archivo:
            datos = archivo.read(MAX_PDF + 1)
        if len(datos) > MAX_PDF:
            return 1
        resultado = leer_silabo(datos).model_dump_json().encode("utf-8")
        if len(resultado) > MAX_RESULTADO:
            return 1
        with salida.open("xb") as archivo:
            archivo.write(resultado)
        return 0
    except BaseException:
        return 1
    finally:
        if cerrar is not None:
            cerrar()


def _main() -> int:
    try:
        if len(sys.argv) != 5 or sys.argv[1] != "child":
            return 1
        return _child(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]))
    except BaseException:
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
