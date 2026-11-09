from copy import deepcopy
from uuid import uuid4

import pytest

from app.agentes.orquestador import procesar_uno
from tests.acceso import dar_acceso, quitar_acceso
from tests.test_generacion_api import HEADERS, entorno
from tests.test_coordinador import cliente_revisor


def enviar(d, aid, recurso=None, **extra):
    cuerpo = {'peticion_id':str(uuid4()), 'mensaje':'Haz más precisa la pregunta 1',
              'recurso_id':recurso['id'] if recurso else None, 'revision':recurso['revision'] if recurso else None}
    cuerpo.update(extra)
    return d.post(f'/asignaturas/{aid}/chat', json=cuerpo, headers=HEADERS)


def test_encolado_privado_deduplicado_y_cuota(entorno, conn):
    _, clientes, d, aid, producir = entorno
    r = producir()
    clave = str(uuid4())
    p = enviar(d,aid,r,peticion_id=clave)
    assert p.status_code == 202, p.text
    assert p.json()['estado'] == 'en_cola'
    assert enviar(d,aid,r,peticion_id=clave).json()['id'] == p.json()['id']
    assert enviar(d,aid,r,peticion_id=clave,mensaje='Otro pedido').status_code == 409
    e = clientes('editor@uti.edu.ec')
    dar_acceso(conn,aid,'editor@uti.edu.ec','editor')
    assert e.get(f'/asignaturas/{aid}/chat').json()['pedidos'] == []
    assert e.get(f"/asignaturas/{aid}/chat/{p.json()['id']}").status_code == 404
    assert all(x['herramienta'] != 'chat' for x in d.get(f'/asignaturas/{aid}/trabajos').json())
    assert enviar(d,aid,r).status_code == 202
    assert enviar(d,aid,r).status_code == 202
    assert enviar(d,aid,r).status_code == 429


def test_validacion_revision_y_lector(entorno, conn):
    _, clientes, d, aid, producir = entorno
    r = producir()
    l = clientes('lector@uti.edu.ec')
    dar_acceso(conn,aid,'lector@uti.edu.ec','lector')
    assert enviar(l,aid,r).status_code == 403
    assert l.get(f'/asignaturas/{aid}/chat').status_code == 403
    assert enviar(d,aid,r,revision=100).status_code == 409
    assert enviar(d,aid,r,revision=True).status_code == 422
    assert enviar(d,aid,mensaje=' ').status_code == 422
    assert enviar(d,aid,r,recurso_id=str(uuid4())).status_code == 404
    assert enviar(d,aid,r,revision=None).status_code == 422


def test_paginacion_historial(entorno):
    _, _, d, aid, _ = entorno
    for _ in range(3):
        assert enviar(d,aid).status_code == 202
    primero = d.get(f'/asignaturas/{aid}/chat?limite=2').json()
    segundo = d.get(f"/asignaturas/{aid}/chat?limite=2&antes={primero['siguiente']}").json()
    assert len(primero['pedidos']) == 2 and len(segundo['pedidos']) == 1
    assert segundo['siguiente'] is None
    assert {p['id'] for p in primero['pedidos']}.isdisjoint({p['id'] for p in segundo['pedidos']})


def _interpretar(monkeypatch, datos):
    from app.chat.acciones import validar_accion
    monkeypatch.setattr('app.chat.interprete.interpretar', lambda *args, **kw: validar_accion(datos))


def test_aclaracion_sin_mutacion_y_dedup_despues_de_procesar(entorno, conn, monkeypatch):
    app, _, d, aid, producir = entorno
    r = producir()
    _interpretar(monkeypatch, {'accion':'aclarar','mensaje_al_docente':'¿Qué pregunta deseas ajustar?'})
    clave = str(uuid4())
    p = enviar(d,aid,r,peticion_id=clave).json()
    assert procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-test',360)
    actual = d.get(f"/asignaturas/{aid}/chat/{p['id']}").json()
    assert actual['estado'] == 'completado'
    assert d.get(f"/asignaturas/{aid}/recursos/{r['id']}").json()['revision']==0
    assert enviar(d,aid,r,peticion_id=clave).json()['id'] == p['id']


def test_ajuste_atomico_revalida_y_no_toca_otros_items(entorno, conn, monkeypatch):
    app, _, d, aid, producir = entorno
    r = producir()
    _interpretar(monkeypatch, {'accion':'ajustar_recurso','mensaje_al_docente':'Ajustaré la primera pregunta.',
                  'recurso_id':r['id'],'items':[r['contenido'][0]['item_id']],'rutas':[],'instrucciones':'Mayor precisión'})
    nuevo = deepcopy(r['contenido'])
    nuevo[0]['pregunta'] = '¿Qué procedimiento debe emplearse para analizar los datos de este contexto?'
    monkeypatch.setattr('app.chat.ajustes.regenerar', lambda *args, **kw: (nuevo,{}, {'alcance':[nuevo[0]['item_id']], 'veredictos':[{'item_id':nuevo[0]['item_id'],'revisor':'ok','motivo':''}]}))
    d.post(f"/asignaturas/{aid}/recursos/{r['id']}/validar",json={'revision':0},headers=HEADERS)
    p = enviar(d,aid,r).json()
    assert procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-test',360)
    actual = d.get(f"/asignaturas/{aid}/recursos/{r['id']}").json()
    assert actual['revision']==1 and actual['validado'] is False
    assert actual['contenido'][1:] == r['contenido'][1:]
    assert d.get(f"/asignaturas/{aid}/chat/{p['id']}").json()['revision_resultado']==1
    assert conn.execute('select count(*) n from recurso_edicion').fetchone()['n']==1
    assert d.get(f"/asignaturas/{aid}/recursos/{r['id']}/exportar").status_code==409


def test_conflicto_antes_de_procesar_no_pisa_edicion(entorno,conn,monkeypatch):
    app, _, d, aid, producir = entorno
    r = producir()
    p = enviar(d,aid,r).json()
    nuevo = deepcopy(r['contenido'])
    nuevo[0]['pregunta'] = '¿Qué procedimiento corresponde para analizar los datos de esta situación?'
    assert d.put(f"/asignaturas/{aid}/recursos/{r['id']}",json={'revision':0,'contenido':nuevo},headers=HEADERS).status_code==200
    monkeypatch.setattr('app.chat.interprete.interpretar', lambda *a, **k: pytest.fail('No debe llamar al modelo'))
    procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-test',360)
    assert d.get(f"/asignaturas/{aid}/chat/{p['id']}").json()['estado']=='conflicto'
    assert d.get(f"/asignaturas/{aid}/recursos/{r['id']}").json()['contenido']==nuevo


def test_recorrido_interprete_worker_y_revisor(entorno,conn,monkeypatch):
    import json
    from app.llm.cliente import Respuesta
    from app.agentes.workers import WORKERS
    from tests.test_coordinador import WorkerPrueba
    app, _, d, aid, producir = entorno
    r = producir()
    objetivo = r['contenido'][2]['item_id']
    accion = {'accion':'ajustar_recurso','mensaje_al_docente':'Ajustaré solo la pregunta 3.',
              'recurso_id':r['id'],'items':[objetivo],'rutas':[],'instrucciones':'Aumentar la complejidad dentro del mismo nivel'}
    llamadas = []
    class Cliente:
        def contar_tokens(self, mensajes):
            return 100
        def completar(self,mensajes,**kw):
            llamadas.append(kw['rol'])
            assert not conn.info.transaction_status.value, 'No debe mantener transacción durante IA'
            if kw['rol']=='coordinador':
                return Respuesta(json.dumps({'accion':accion}), '',100,100,0)
            return cliente_revisor().completar(mensajes,**kw)
    class Worker(WorkerPrueba):
        def generar(self,tarea,cliente):
            assert [p.item_id for p in tarea.plan] == [objetivo]
            entrega = super().generar(tarea,cliente)
            entrega.contenido[0]['pregunta'] += ' Considera además la interpretación del resultado.'
            return entrega
    monkeypatch.setitem(WORKERS,'cuestionario',Worker())
    p = enviar(d,aid,r,mensaje='Haz más difícil la pregunta 3').json()
    procesar_uno(conn,Cliente(),app.state.perfiles,'chat-test',360)
    resultado = d.get(f"/asignaturas/{aid}/chat/{p['id']}").json()
    assert resultado['estado']=='completado', resultado
    actual = d.get(f"/asignaturas/{aid}/recursos/{r['id']}").json()
    assert actual['revision']==1 and actual['revision_ia']['alcance']['items']==[objetivo]
    assert 'coordinador' in llamadas and 'revisor' in llamadas
    for n,item in enumerate(r['contenido']):
        if n!=2:
            assert actual['contenido'][n]==item


@pytest.mark.parametrize('revocar', [False,True])
def test_concurrencia_durante_modelo_no_publica(entorno,conn,monkeypatch,revocar):
    app, clientes, d, aid, producir = entorno
    r = producir()
    editor = clientes('editor@uti.edu.ec')
    dar_acceso(conn,aid,'editor@uti.edu.ec','editor')
    _interpretar(monkeypatch, {'accion':'ajustar_recurso','mensaje_al_docente':'Ajustaré la primera pregunta.',
                  'recurso_id':r['id'],'items':[r['contenido'][0]['item_id']],'rutas':[],'instrucciones':'Precisar'})
    nuevo = deepcopy(r['contenido'])
    nuevo[0]['pregunta'] = '¿Qué método debe emplearse para analizar este conjunto de observaciones?'
    def durante(*args,**kw):
        if revocar:
            quitar_acceso(conn,aid,'editor@uti.edu.ec')
        else:
            assert d.put(f"/asignaturas/{aid}/recursos/{r['id']}",json={'revision':0,'contenido':nuevo},headers=HEADERS).status_code==200
        return nuevo,{}, {'veredictos':[]}
    monkeypatch.setattr('app.chat.ajustes.regenerar',durante)
    p = enviar(editor,aid,r).json()
    procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-test',360)
    fila = conn.execute('select estado from chat_pedido where id=%s',(p['id'],)).fetchone()
    assert fila['estado']==('error' if revocar else 'conflicto')
    actual = d.get(f"/asignaturas/{aid}/recursos/{r['id']}").json()
    assert actual['revision']==(0 if revocar else 1)
    assert actual['contenido']==(r['contenido'] if revocar else nuevo)


def test_generar_usa_cola_normal_y_no_duplica(entorno,conn,monkeypatch):
    app, _, d, aid, _ = entorno
    _interpretar(monkeypatch, {'accion':'generar','mensaje_al_docente':'Generaré un cuestionario.',
        'ambito':{'tipo':'clase','id':'M2-S1'},'herramientas':['cuestionario'],'cantidad':4,'instrucciones':''})
    p = enviar(d,aid).json()
    procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-test',360)
    resultado = d.get(f"/asignaturas/{aid}/chat/{p['id']}").json()
    assert resultado['estado']=='completado' and len(resultado['trabajos'])==1
    assert conn.execute("select count(*) n from trabajo where tipo='generacion'").fetchone()['n']==1


def test_regeneracion_directa_comparte_ejecutor(entorno,conn,monkeypatch):
    app, _, d, aid, producir = entorno
    r = producir()
    item = r['contenido'][0]['item_id']
    cuerpo = {'peticion_id':str(uuid4()),'revision':0,'motivo':'Aclara el contexto'}
    url = f"/asignaturas/{aid}/recursos/{r['id']}/items/{item}/regenerar"
    p = d.post(url,json=cuerpo,headers=HEADERS)
    assert p.status_code==202,p.text
    assert d.post(url,json=cuerpo,headers=HEADERS).json()['id']==p.json()['id']
    monkeypatch.setattr('app.chat.interprete.interpretar',lambda *a,**k: pytest.fail('La acción ya está definida'))
    monkeypatch.setattr('app.chat.ajustes.regenerar',lambda *a,**k: (r['contenido'],{},{'veredictos':[]}))
    procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-test',360)
    assert d.get(f"/asignaturas/{aid}/chat/{p.json()['id']}").json()['estado']=='completado'


def test_lease_perdido_no_publica_y_recuperacion_no_duplica(entorno,conn,monkeypatch):
    from psycopg.types.json import Jsonb
    app, _, d, aid, producir = entorno
    r = producir()
    _interpretar(monkeypatch, {'accion':'ajustar_recurso','mensaje_al_docente':'Ajustaré la primera pregunta.',
                  'recurso_id':r['id'],'items':[r['contenido'][0]['item_id']],'rutas':[],'instrucciones':'Precisar'})
    nuevo = deepcopy(r['contenido'])
    nuevo[0]['pregunta'] = '¿Qué procedimiento se recomienda para analizar estas observaciones y por qué?'
    veces = []
    def durante(*args,**kw):
        if not veces:
            conn.execute("update trabajo set lease_hasta=clock_timestamp()-interval '1 second' where tipo='chat'")
        veces.append(1)
        return nuevo,{}, {'veredictos':[]}
    monkeypatch.setattr('app.chat.ajustes.regenerar',durante)
    p = enviar(d,aid,r).json()
    procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-viejo',360)
    assert d.get(f"/asignaturas/{aid}/recursos/{r['id']}").json()['revision']==0
    procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-nuevo',360)
    assert d.get(f"/asignaturas/{aid}/recursos/{r['id']}").json()['revision']==1
    assert conn.execute('select count(*) n from recurso_edicion').fetchone()['n']==1


def test_modelo_invalido_estado_seguro_sin_mutacion(entorno,conn,monkeypatch):
    from app.llm.cliente import JsonInvalido
    app, _, d, aid, producir = entorno
    r = producir()
    def fallar(*a,**k):
        raise JsonInvalido('CONTENIDO PRIVADO QUE NO DEBE MOSTRARSE')
    monkeypatch.setattr('app.chat.interprete.interpretar',fallar)
    p = enviar(d,aid,r).json()
    procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-test',360)
    resultado = d.get(f"/asignaturas/{aid}/chat/{p['id']}").json()
    assert resultado['estado']=='error' and 'PRIVADO' not in str(resultado)
    assert d.get(f"/asignaturas/{aid}/recursos/{r['id']}").json()['revision']==0


def test_chat_permite_herramientas_sin_ia_en_momento_restringido(entorno,conn,monkeypatch,silabo):
    from psycopg.types.json import Jsonb
    app, _, d, aid, _ = entorno
    datos = silabo.model_dump(mode='json')
    for m in datos['momentos']:
        if m['numero']==2:
            m['politica_ia']='No se permite el uso de IA en la evaluación de este momento.'
    conn.execute('update asignatura set silabo=%s where id=%s',(Jsonb(datos),aid))
    _interpretar(monkeypatch, {'accion':'generar','mensaje_al_docente':'Crearé una lista de verificación.',
        'ambito':{'tipo':'momento','id':'M2'},'herramientas':['lista_evidencia'],'cantidad':4,'instrucciones':''})
    p = enviar(d,aid).json()
    procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-test',360)
    resultado = d.get(f"/asignaturas/{aid}/chat/{p['id']}").json()
    assert resultado['estado']=='completado', resultado
    assert conn.execute("select count(*) n from recurso where herramienta='lista_evidencia'").fetchone()['n']==1


def test_trabajos_por_id_incluye_antiguos_y_excluye_chat(entorno,conn):
    app, _, d, aid, _ = entorno
    antiguo = conn.execute("insert into trabajo(asignatura_id,agente,ambito_tipo,ambito_id,herramienta,parametros,creado) "
                           "values (%s,'ingenierias','clase','M2-S1','cuestionario','{}',now()-interval '1 day') returning id",(aid,)).fetchone()['id']
    conn.execute("insert into trabajo(asignatura_id,agente,ambito_tipo,ambito_id,herramienta,parametros) "
                 "select %s,'ingenierias','clase','M2-S1','cuestionario','{}'::jsonb from generate_series(1,201)",(aid,))
    pedido = enviar(d,aid).json()
    privado = conn.execute('select trabajo_id from chat_pedido where id=%s',(pedido['id'],)).fetchone()['trabajo_id']
    lista = d.get(f'/asignaturas/{aid}/trabajos?ids={antiguo}&ids={privado}').json()
    assert [x['id'] for x in lista]==[str(antiguo)]


def test_el_chat_no_consulta_el_razonador(entorno, conn, monkeypatch):
    app, _, d, aid, producir = entorno
    r = producir()
    _interpretar(monkeypatch, {'accion':'ajustar_recurso','mensaje_al_docente':'Ajustaré la primera pregunta.',
                  'recurso_id':r['id'],'items':[r['contenido'][0]['item_id']],'rutas':[],'instrucciones':'Mayor precisión'})

    class Vetado:
        def __getattr__(self, nombre):
            pytest.fail('el chat consultó el razonador')

    recibidos = []

    def regenerar(*args, **kw):
        recibidos.append(kw)
        return r['contenido'], {}, {'alcance':[], 'veredictos':[]}

    monkeypatch.setattr('app.chat.ajustes.regenerar', regenerar)
    enviar(d,aid,r)
    assert procesar_uno(conn,cliente_revisor(),app.state.perfiles,'chat-test',360,razonador=Vetado())
    assert len(recibidos) == 1 and 'razonador' not in recibidos[0]
