"""Contrato P7: sondas sin IA/cuotas, migraciones y latido por consumidor."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import json

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import Ajustes
from app.api.aplicacion import crear_app
from app.db import migrar


def config(**kw):
    return Ajustes(_env_file=None, database_url='postgresql://no-usar',
                   llm_base_url='http://no-usar/v1', llm_model='prueba',
                   auth_secreto='x' * 32, **kw)


class BD:
    autocommit = True
    closed = False
    broken = False
    def __init__(self, nombres=(), error=False):
        self.nombres, self.error, self.sql = nombres, error, []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def close(self): pass
    def transaction(self): return nullcontext()
    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        if self.error and 'pg_advisory_unlock' not in sql:
            raise psycopg.OperationalError('credencial-privada')
        return self
    def fetchall(self): return [{'nombre': n} for n in self.nombres]


def test_migrar_bloquea_antes_de_descubrir_y_desbloquea(monkeypatch, tmp_path):
    c = BD()
    class Directorio:
        def glob(self, patron):
            assert 'pg_advisory_lock' in c.sql[0][0]
            return []
    monkeypatch.setattr(migrar, 'DIR', Directorio())
    assert migrar.aplicar_migraciones(c) == []
    assert 'pg_advisory_unlock' in c.sql[-1][0]


def test_migrar_desbloquea_si_falla_sql(monkeypatch, tmp_path):
    (tmp_path / '001.sql').write_text('SQL ROTO', encoding='utf-8')
    monkeypatch.setattr(migrar, 'DIR', tmp_path)
    c = BD()
    original = c.execute
    def ejecutar(sql, params=None):
        if sql == 'SQL ROTO': raise ValueError('privado')
        return original(sql, params)
    c.execute = ejecutar
    with pytest.raises(ValueError): migrar.aplicar_migraciones(c)
    assert 'pg_advisory_unlock' in c.sql[-1][0]


@pytest.mark.parametrize('ruta', ['/salud/vivo', '/salud/listo'])
@pytest.mark.parametrize('metodo', ['get', 'head'])
def test_salud_interna_sin_cuotas_ni_ia(ruta, metodo):
    def fallo(): raise psycopg.OperationalError('credencial-privada')
    def ia(_): raise AssertionError('No debe consultar IA')
    app = crear_app(config(), conexion=fallo, transporte=httpx.MockTransport(ia))
    with TestClient(app) as c:
        r = getattr(c, metodo)(ruta)
        assert r.status_code == (200 if ruta.endswith('vivo') else 503)
        if metodo == 'get':
            assert r.json() == {'estado': 'ok' if ruta.endswith('vivo') else 'no-listo'}
        assert 'privada' not in r.text


def test_preparado_exige_migraciones_y_perfiles(monkeypatch):
    from app.operacion import preparado
    nombres = [p.name for p in migrar.DIR.glob('*.sql')]
    assert preparado(config(), conexion=lambda: BD(nombres), perfiles={'general': object()})
    assert not preparado(config(), conexion=lambda: BD(nombres[:-1]), perfiles={'general': object()})
    assert not preparado(config(), conexion=lambda: BD(nombres), perfiles={})


def test_latido_todos_consumidores_y_reinicio(tmp_path):
    from app.operacion import LatidoWorker, salud_worker
    reloj = [100.0]
    identidad = lambda pid: 'inicio-A'
    ruta = tmp_path / 'worker-salud.json'
    latido = LatidoWorker(ruta, 2, reloj=lambda: reloj[0], identidad=identidad)
    latido.pulsar(0)
    latido.escribir()
    cfg = config(llm_max_concurrencia=2)
    assert not salud_worker(cfg, ruta=ruta, reloj=lambda: reloj[0], identidad=identidad)
    latido.pulsar(1)
    latido.escribir()
    assert salud_worker(cfg, ruta=ruta, reloj=lambda: reloj[0], identidad=identidad)
    assert not salud_worker(cfg, ruta=ruta, reloj=lambda: reloj[0], identidad=lambda pid: 'inicio-B')
    reloj[0] += 2 * max(cfg.llm_timeout_s, cfg.llm_timeout_revisor_s) + 61
    latido.pulsar(0)
    latido.escribir()
    assert not salud_worker(cfg, ruta=ruta, reloj=lambda: reloj[0], identidad=identidad)


def test_cli_error_generico(monkeypatch, capsys):
    from app import operacion
    monkeypatch.setattr(operacion, 'ajustes', lambda: (_ for _ in ()).throw(ValueError('secreto')))
    assert operacion.main(['preparado']) == 1
    assert capsys.readouterr().out.strip() == '{"estado": "no-listo"}'
