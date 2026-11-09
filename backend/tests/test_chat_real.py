"""Humo optativo del intérprete con Qwen local; sin recursos ni usuarios reales."""
import os
from uuid import UUID

import httpx
import pytest

from app.chat.interprete import interpretar
from app.config import ajustes
from app.llm.cliente import ClienteVLLM


@pytest.mark.servidor
@pytest.mark.skipif(os.environ.get('HUMO_CHAT') != '1', reason='Activar explícitamente HUMO_CHAT=1')
def test_interprete_qwen_real():
    config = ajustes()
    try:
        r = httpx.get(config.llm_base_url.rstrip('/')+'/models', timeout=5,
                      headers={'Authorization':'Bearer '+config.llm_api_key})
        r.raise_for_status()
    except httpx.HTTPError:
        pytest.skip('Servidor de IA no disponible para el humo')
    rid = UUID('00000000-0000-4000-8000-000000000003')
    contexto = {'facultad':'ingenierias','catalogo':[{'id':'cuestionario','tipo':'clase'}],
                'ambitos':['M2-S1'], 'recurso':{'id':str(rid),'revision':0,'herramienta':'cuestionario',
                'items':[{'numero':n,'item_id':f'i{n}','nivel':'resolutivo','pregunta':'¿Qué método compara dos medias independientes?'} for n in (1,2,3)]}}
    llamadas = []
    cliente = ClienteVLLM(config.llm_base_url,config.llm_model,45,1,llamadas.append,config.llm_api_key)
    from app.llm.json import ultimo_json
    trazas = []
    completar = cliente.completar
    def observar(*args, **kw):
        salida = completar(*args, **kw)
        trazas.append(ultimo_json(salida.texto))
        return salida
    cliente.completar = observar
    try:
        accion = interpretar(cliente,mensaje='Haz más difícil la pregunta 3, manteniendo su nivel académico.',contexto=contexto,
                            historial=[],trabajo_id=UUID(int=100),asignatura_id=UUID(int=101))
        assert accion.accion=='ajustar_recurso', trazas
        assert accion.items==['i3'] and accion.recurso_id==rid
        fuera = interpretar(cliente,mensaje='Cambia las calificaciones oficiales de los estudiantes en el sistema institucional.',
                            contexto=contexto,historial=[],trabajo_id=UUID(int=102),asignatura_id=UUID(int=101))
        assert fuera.accion=='fuera_de_alcance', trazas[-1]
        assert llamadas and all(x['ok'] for x in llamadas)
    finally:
        cliente.close()
