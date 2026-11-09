import json
from copy import deepcopy

import pytest

from app.chat.ajustes import regenerar
from app.llm.cliente import Respuesta
from tests.test_chat_ajustes import entorno, _ficha, _accion
from tests.test_chat_interprete import llamar, cliente_para, AJUSTE


def test_regeneracion_sanea_worker_y_revisor_sin_alterar_original(entorno):
    recurso = _ficha()
    recurso['contenido']['conceptual']['relacion_ra'] += ' privado@example.org'
    recurso['contenido']['aplicacion']['ejemplo']['enunciado'] += ' otro@example.org'
    original = deepcopy(recurso)
    roles = []
    class Cliente:
        def contar_tokens(self, mensajes):
            assert '@example.org' not in json.dumps(mensajes)
            return 100
        def completar(self,mensajes,**kw):
            assert '@example.org' not in json.dumps(mensajes)
            roles.append(kw['rol'])
            salida = ({'textos':[{'indice':0,'texto':'Una empresa ficticia analiza datos agregados de ventas durante un trimestre.'}]}
                      if kw['rol']=='worker' else {'resuelve_entregable':False,'motivo':'','entregable':''})
            return Respuesta(json.dumps(salida),'',100,50,0)
    contenido, _, _ = regenerar(Cliente(),recurso=recurso,
        accion=_accion(rutas=[['aplicacion','ejemplo','enunciado']]),**entorno)
    assert roles==['worker','revisor']
    assert recurso==original
    assert contenido['conceptual']==original['contenido']['conceptual']


@pytest.mark.parametrize('mensaje', ['Haz más difíciles las preguntas 3 y 7', 'Ajusta preguntas 3, 7'])
def test_numeros_explicitos_acotan_esquema_y_resultado(mensaje):
    datos = AJUSTE | {'items':['q-rev2-3','q-rev2-7']}
    cliente = cliente_para(datos)
    resultado = llamar(cliente,mensaje=mensaje)
    assert resultado.items==datos['items']
    campo = cliente.llamadas[0]['esquema']['$defs']['Ajustar']['properties']['items']
    assert campo['minItems']==campo['maxItems']==2
    assert campo['items']['enum']==datos['items']
    assert 'uniqueItems' not in campo  # No soportado por el servidor real.


@pytest.mark.parametrize('mensaje', ['Pregunta 999', 'Ajusta preguntas 3 a 7', 'No cambies la pregunta 3'])
def test_referencia_ambigua_o_inexistente_aclara_sin_modelo(mensaje):
    cliente = cliente_para(AJUSTE)
    assert llamar(cliente,mensaje=mensaje).accion=='aclarar'
    assert not cliente.llamadas


def test_modelo_no_puede_ampliar_seleccion_explicita():
    assert llamar(cliente_para(AJUSTE | {'items':['q-rev2-3','q-rev2-7']}),mensaje='Ajusta la pregunta 3').accion=='aclarar'


def test_referencias_contextuales_no_se_convierten_en_objetivos():
    cliente = cliente_para(AJUSTE | {'items':['q-rev2-3','q-rev2-7']})
    assert llamar(cliente,mensaje='Haz más difícil la pregunta 3; usa la pregunta 7 como referencia').accion=='aclarar'
    assert not cliente.llamadas


def test_lista_con_articulos_conserva_todos_los_objetivos():
    datos = AJUSTE | {'items':['q-rev2-3','q-rev2-7']}
    assert llamar(cliente_para(datos),mensaje='Haz más difíciles la pregunta 3 y la 7').items==datos['items']


def test_correos_en_enums_no_llegan_al_transporte():
    from app.chat.ajustes import _Presupuestado
    from app.recursos.validacion import EdicionInvalida
    class Cliente:
        def completar(self,*a,**k):
            pytest.fail('No debe transportar un esquema con correo')
    with pytest.raises(EdicionInvalida):
        _Presupuestado(Cliente()).completar([{'content':'Contenido académico'}], esquema={'enum':['privado@example.org']}, max_tokens=256)
