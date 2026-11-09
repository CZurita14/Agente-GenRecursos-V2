"""Aislamiento real y protocolo acotado, sin mostrar contenido de sílabos."""
from pathlib import Path
import subprocess
import sys

import pytest

from app.silabo import aislado
from app.silabo.lector.errores import SilaboIlegible


@pytest.fixture
def entrada(tmp_path):
    ruta = tmp_path / "entrada.pdf"
    ruta.write_bytes(b"invalid PDF personal-data-canary")
    return ruta


@pytest.fixture
def temporales(monkeypatch, tmp_path):
    raiz = tmp_path / "resultados"
    raiz.mkdir()
    monkeypatch.setattr(aislado.tempfile, "tempdir", str(raiz))
    return raiz


def test_pdf_invalido_y_cleanup(entrada, temporales):
    with pytest.raises(SilaboIlegible) as error:
        aislado.leer_pdf_aislado(entrada)
    assert str(error.value) == aislado.MENSAJE_ERROR
    assert entrada.read_bytes() == b"invalid PDF personal-data-canary"
    assert not list(temporales.iterdir())


def test_timeout_real_mata_y_recolecta(entrada, temporales, monkeypatch):
    original = subprocess.Popen
    procesos = []

    def lento(comando, **opciones):
        proceso = original([sys.executable, "-E", "-s", "-B", "-c",
                            "import time; time.sleep(60)"], **opciones)
        procesos.append(proceso)
        return proceso

    monkeypatch.setattr(aislado.subprocess, "Popen", lento)
    with pytest.raises(SilaboIlegible, match=aislado.MENSAJE_ERROR):
        aislado.leer_pdf_aislado(entrada, timeout_s=0.05)
    assert procesos[0].poll() is not None
    assert entrada.exists()
    assert not list(temporales.iterdir())


@pytest.mark.parametrize("opciones", [{"timeout_s": 0}, {"timeout_s": float("nan")},
    {"timeout_s": float("inf")}, {"memoria_mb": 0}, {"memoria_mb": True},
    {"memoria_mb": 0.5}, {"memoria_mb": 2**64}])
def test_limites_invalidos(entrada, opciones, temporales):
    with pytest.raises(SilaboIlegible, match=aislado.MENSAJE_ERROR):
        aislado.leer_pdf_aislado(entrada, **opciones)
    assert not list(temporales.iterdir())


def test_memoria_dura_en_proceso_real():
    # La reserva supera el límite tanto de commit (Windows) como de AS (POSIX).
    codigo = """
from app.silabo.aislado import _limitar_memoria
cerrar = _limitar_memoria(128)
try:
    try:
        datos = bytearray(256 * 1024 * 1024)
    except MemoryError:
        raise SystemExit(0)
    raise SystemExit(3)
finally:
    cerrar()
"""
    resultado = subprocess.run([sys.executable, "-E", "-s", "-B", "-c", codigo],
        cwd=Path(aislado.__file__).resolve().parents[2], env=aislado._entorno_hijo(),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=15, check=False)
    assert resultado.returncode == 0, "No se pudo verificar el límite duro de memoria"


def test_entorno_no_hereda_secretos(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-canary")
    monkeypatch.setenv("PYTHONPATH", "untrusted")
    entorno = aislado._entorno_hijo()
    assert "OPENAI_API_KEY" not in entorno and "PYTHONPATH" not in entorno


@pytest.mark.parametrize("contenido", [b"{}", b"not json", b"x" * (aislado.MAX_RESULTADO + 1)],
                         ids=["schema", "json", "oversize"])
def test_resultado_invalido_acotado(entrada, temporales, monkeypatch, contenido):
    class Proceso:
        def __init__(self, comando, **opciones):
            assert opciones["shell"] is False
            assert opciones["stdout"] == opciones["stderr"] == subprocess.DEVNULL
            Path(comando[-2]).write_bytes(contenido)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def wait(self, **kwargs):
            return 0
    monkeypatch.setattr(aislado.subprocess, "Popen", Proceso)
    with pytest.raises(SilaboIlegible, match=aislado.MENSAJE_ERROR):
        aislado.leer_pdf_aislado(entrada)
    assert not list(temporales.iterdir())


def test_hijo_limita_antes_de_abrir_y_falla_cerrado(entrada, tmp_path, monkeypatch):
    def rechazar(_):
        raise OSError("sensitive failure")
    monkeypatch.setattr(aislado, "_limitar_memoria", rechazar)
    salida = tmp_path / "resultado.json"
    assert aislado._child(entrada, salida, 512) == 1
    assert not salida.exists()
    assert entrada.exists()


def test_pdf_real_si_disponible(temporales, monkeypatch):
    carpeta = Path(__file__).resolve().parents[2] / "Silabos"
    archivos = sorted(carpeta.rglob("*.pdf")) if carpeta.exists() else []
    if not archivos:
        pytest.skip("No hay PDF local para integración")
    # El padre no debe invocar pdfplumber, incluso cuando devuelve un modelo válido.
    import pdfplumber
    def prohibido(*args, **kwargs):
        pytest.fail("El padre intentó abrir el PDF")
    monkeypatch.setattr(pdfplumber, "open", prohibido)
    resultado = aislado.leer_pdf_aislado(archivos[0], timeout_s=60)
    from app.silabo.modelo import SilaboUTI
    assert isinstance(resultado, SilaboUTI)
    assert resultado.momentos
    assert archivos[0].exists()
    assert not list(temporales.iterdir())


def test_modelo_valido_por_protocolo(entrada, temporales, monkeypatch, silabo):
    class Proceso:
        def __init__(self, comando, **opciones):
            Path(comando[-2]).write_text(silabo.model_dump_json(), encoding="utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def wait(self, **kwargs):
            return 0
    monkeypatch.setattr(aislado.subprocess, "Popen", Proceso)
    assert aislado.leer_pdf_aislado(entrada) == silabo
    assert not list(temporales.iterdir())


def test_memoria_insuficiente_es_error_publico(entrada, temporales):
    with pytest.raises(SilaboIlegible, match=aislado.MENSAJE_ERROR):
        aislado.leer_pdf_aislado(entrada, memoria_mb=1)
    assert entrada.exists()
    assert not list(temporales.iterdir())


def test_import_modulo_no_carga_lector_ni_configuracion():
    codigo = """
import sys
import app.silabo.aislado
assert 'pdfplumber' not in sys.modules
assert 'app.silabo.lector' not in sys.modules
assert 'app.config' not in sys.modules
"""
    resultado = subprocess.run([sys.executable, "-E", "-s", "-B", "-c", codigo],
        cwd=Path(aislado.__file__).resolve().parents[2], env=aislado._entorno_hijo(),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=15, check=False)
    assert resultado.returncode == 0
