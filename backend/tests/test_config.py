import json
import logging
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.config import Ajustes, RAIZ
from app.operacion import cargar_razonador, validar_configuracion
from app.razonador import Razonador, RazonadorInvalido

VARS = ["DATABASE_URL", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_MAX_CONCURRENCIA",
        "LLM_TIMEOUT_S", "LLM_TIMEOUT_REVISOR_S", "LEASE_S", "AGENTES_DIR"]


def _limpiar(monkeypatch):
    for v in VARS:
        monkeypatch.delenv(v, raising=False)


def test_url_y_modelo_son_obligatorios(monkeypatch):
    _limpiar(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("LLM_MODEL", "m")
    with pytest.raises(ValidationError) as exc:
        Ajustes(_env_file=None)
    assert [e["loc"] for e in exc.value.errors()] == [("llm_base_url",)]


def test_valores_por_defecto(monkeypatch):
    _limpiar(monkeypatch)
    for k, v in {"DATABASE_URL": "postgresql://x", "LLM_BASE_URL": "http://h/v1", "LLM_MODEL": "m"}.items():
        monkeypatch.setenv(k, v)
    a = Ajustes(_env_file=None)
    assert (a.llm_max_concurrencia, a.llm_timeout_s, a.llm_timeout_revisor_s, a.lease_s) == (4, 120, 240, 360)
    assert a.lease_s > a.llm_timeout_revisor_s


# --- Razonador: apagado por omisión --------------------------------------------

BASE = dict(_env_file=None, database_url="postgresql://x", llm_base_url="http://h/v1", llm_model="m")
DESARROLLO = dict(BASE, entorno="desarrollo")


def test_razonador_apagado_por_omision(monkeypatch):
    monkeypatch.delenv("RAZONADOR_RUTA", raising=False)
    config = Ajustes(**BASE)
    assert config.razonador_ruta is None
    assert cargar_razonador(config) is None


def test_ruta_vacia_del_compose_es_apagado(monkeypatch):
    # El compose declara ${RAZONADOR_RUTA:-}: vacía no puede leerse como la carpeta actual.
    monkeypatch.setenv("RAZONADOR_RUTA", "")
    config = Ajustes(**BASE)
    assert config.razonador_ruta is None
    assert cargar_razonador(config) is None
    validar_configuracion(Ajustes(**DESARROLLO))


def test_worker_no_arranca_con_modelo_invalido(tmp_path):
    with pytest.raises(RazonadorInvalido):
        cargar_razonador(Ajustes(razonador_ruta=tmp_path / "no-existe", **BASE))


@pytest.mark.parametrize("entorno,exigir", [("produccion", True), ("desarrollo", False)])
def test_solo_produccion_exige_modelo_aprobado(monkeypatch, tmp_path, entorno, exigir):
    pedidos = []
    monkeypatch.setattr(Razonador, "cargar", classmethod(lambda cls, ruta, *, exigir_aprobado:
                                                         pedidos.append((ruta, exigir_aprobado)) or "modelo"))
    config = Ajustes(razonador_ruta=tmp_path, **{**BASE, "entorno": entorno})
    assert cargar_razonador(config) == "modelo"
    assert pedidos == [(tmp_path, exigir)]


def test_produccion_rechaza_un_modelo_de_humo(tmp_path):
    (tmp_path / "onnx").mkdir()
    (tmp_path / "onnx" / "model.onnx").touch()
    (tmp_path / "tokenizer.json").touch()
    (tmp_path / "metadatos.json").write_text(json.dumps({"humo": True, "aprobado": False}), encoding="utf-8")
    with pytest.raises(RazonadorInvalido, match="humo"):
        cargar_razonador(Ajustes(razonador_ruta=tmp_path, **BASE))


def test_ruta_relativa_cuelga_de_la_raiz(monkeypatch):
    pedidos = []
    monkeypatch.setattr(Razonador, "cargar", classmethod(lambda cls, ruta, *, exigir_aprobado: pedidos.append(ruta)))
    cargar_razonador(Ajustes(razonador_ruta=Path("modelos/v1"), **DESARROLLO))
    assert pedidos == [RAIZ / "modelos" / "v1"]


def test_validar_configuracion_reporta_la_carpeta_que_falta(tmp_path):
    with pytest.raises(ValueError, match="RAZONADOR_RUTA"):
        validar_configuracion(Ajustes(razonador_ruta=tmp_path / "no-existe", **DESARROLLO))
    validar_configuracion(Ajustes(razonador_ruta=tmp_path, **DESARROLLO))


def test_worker_se_detiene_antes_de_lanzar_consumidores(monkeypatch, tmp_path):
    import worker
    monkeypatch.setattr(worker, "ajustes", lambda: Ajustes(razonador_ruta=tmp_path / "no-existe", **DESARROLLO))
    monkeypatch.setattr(worker, "preparar_esquema", lambda config: pytest.fail("no debió llegar al esquema"))
    with pytest.raises(ValueError, match="RAZONADOR_RUTA"):
        worker.main()


def test_worker_registra_la_causa_de_una_carpeta_ausente_sin_imprimir_la_ruta(monkeypatch, tmp_path, caplog):
    import worker
    ausente = tmp_path / "no-existe"
    monkeypatch.setattr(worker, "ajustes", lambda: Ajustes(razonador_ruta=ausente, **DESARROLLO))
    monkeypatch.setattr(worker, "preparar_esquema", lambda config: pytest.fail("no debió llegar al esquema"))
    with caplog.at_level("ERROR"), pytest.raises(ValueError):
        worker.main()
    assert "RAZONADOR_RUTA no es una carpeta" in caplog.text and str(ausente) not in caplog.text


def test_worker_registra_la_causa_de_un_modelo_invalido(monkeypatch, tmp_path, caplog):
    import worker
    from app.razonador import RazonadorInvalido

    def invalido(config):
        raise RazonadorInvalido("el modelo no está aprobado")

    monkeypatch.setattr(worker, "ajustes", lambda: Ajustes(razonador_ruta=tmp_path, **DESARROLLO))
    monkeypatch.setattr(worker, "cargar_razonador", invalido)
    monkeypatch.setattr(worker, "preparar_esquema", lambda config: pytest.fail("no debió llegar al esquema"))
    with caplog.at_level("ERROR"), pytest.raises(RazonadorInvalido):
        worker.main()
    assert "razonador inválido: el modelo no está aprobado" in caplog.text


def test_worker_carga_una_vez_y_entrega_la_instancia_a_los_consumidores(monkeypatch, tmp_path, caplog):
    import worker
    falso = SimpleNamespace(version="v-prueba")
    cargas, recibidos = [], []

    class Alto(Exception):
        pass

    def procesar(conn, cliente, perfiles, worker_id, lease_s, razonador=None):
        recibidos.append(razonador)
        raise Alto

    monkeypatch.setenv("WORKER_SALUD_ARCHIVO", str(tmp_path / "salud.json"))
    monkeypatch.setattr(worker, "ajustes", lambda: Ajustes(llm_max_concurrencia=2, razonador_ruta=tmp_path, **DESARROLLO))
    monkeypatch.setattr(worker, "cargar_razonador", lambda config: cargas.append(config) or falso)
    monkeypatch.setattr(worker, "preparar_esquema", lambda config: None)
    monkeypatch.setattr(worker, "conectar", lambda url: nullcontext(SimpleNamespace(autocommit=False)))
    monkeypatch.setattr(worker, "procesar_uno", procesar)
    with caplog.at_level(logging.INFO, logger="worker"), pytest.raises(Alto):
        worker.main()
    assert len(cargas) == 1
    assert recibidos and all(r is falso for r in recibidos)
    assert "v-prueba" in caplog.text and str(tmp_path) not in caplog.text


def test_produccion_rechaza_el_sga_simulado():
    produccion = dict(BASE, api_origen="https://materiales.example", entorno="produccion",
                      auth_secreto="abcdefgh" * 5, administradores=["admin@uti.edu.ec"])
    with pytest.raises(ValueError, match="simulado"):
        validar_configuracion(Ajustes(**produccion, sga_proveedor="simulado"))
    validar_configuracion(Ajustes(**produccion, sga_proveedor="real"))
    validar_configuracion(Ajustes(**DESARROLLO, sga_proveedor="simulado"))
