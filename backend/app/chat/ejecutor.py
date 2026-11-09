"""Despacho de pedidos privados con fencing y publicación atómica de ajustes."""
from fastapi import HTTPException
from psycopg.types.json import Jsonb

from app.agentes.coordinador import LeasePerdido, _ClienteConLease
from app.agentes.orquestador import crear_trabajos, SolicitudGeneracion
from app.agentes.workers.definiciones import DEFINICIONES
from app.asignaturas.servicio import exigir_acceso
from app.cola.trabajos import Ambito, renovar_lease, terminar, registrar_avance
from app.herramientas.sin_ia import HERRAMIENTAS_SIN_IA
from app.recursos.servicio import _recurso, _contexto, _restriccion, ServicioRecursos
from app.silabo.modelo import SilaboUTI


def _seleccion(conn, p):
    a, _ = exigir_acceso(conn, p['asignatura_id'], p['usuario'], editar=True)
    r = None
    if p['recurso_id']:
        r = _recurso(conn, p['asignatura_id'], p['recurso_id'], editar=True)
        if r['revision'] != p['revision']:
            raise HTTPException(409, 'El recurso cambió durante el ajuste. No se sobrescribieron los cambios.')
        if r['herramienta'] in HERRAMIENTAS_SIN_IA:
            raise HTTPException(422, 'Esta herramienta reproduce el sílabo')
        tipo = 'asignatura' if r['ambito_id']=='asignatura' else ('clase' if '-S' in r['ambito_id'] else 'momento')
        for datos in (a['silabo'], r['snapshot']['silabo']):
            if _restriccion(SilaboUTI.model_validate(datos), tipo, r['ambito_id']):
                raise HTTPException(422, 'La política de IA no permite este ajuste')
    return a, r


def procesar_chat(conn, trabajo, cliente, perfiles, worker_id, lease_s):
    from app.chat.interprete import interpretar, limpiar_texto
    from app.chat.acciones import validar_accion
    from app.chat.ajustes import regenerar, rutas_editables
    cerco = dict(worker_id=worker_id, lease_version=trabajo.lease_version)

    def comprobar():
        if not renovar_lease(conn, trabajo.id, worker_id, lease_s, lease_version=trabajo.lease_version):
            raise LeasePerdido()

    def cercar():
        # Se llama dentro de una transacción corta. El lock dura hasta publicar.
        conn.execute('select id from trabajo where id=%s for update', (trabajo.id,))
        comprobar()

    def uso(tokens):
        if not registrar_avance(conn, trabajo.id, tokens=tokens, **cerco):
            raise LeasePerdido()

    cliente = _ClienteConLease(cliente, comprobar, uso)
    p = conn.execute('select * from chat_pedido where trabajo_id=%s and asignatura_id=%s',
                     (trabajo.id, trabajo.asignatura_id)).fetchone()
    if not p:
        raise ValueError('pedido de chat inexistente')

    def cerrar(estado, respuesta, *, revision=None, trabajos=None):
        conn.execute('update chat_pedido set estado=%s,respuesta=%s,revision_resultado=%s,trabajos=%s where id=%s',
                     (estado, respuesta, revision, Jsonb(trabajos or []), p['id']))
        if not terminar(conn, trabajo.id, 'listo', **cerco):
            raise LeasePerdido()

    try:
        with conn.transaction():
            cercar()
            if p['estado'] in ('completado','conflicto','error'):
                terminar(conn, trabajo.id, 'listo', **cerco)
                return
            a, r = _seleccion(conn, p)
            conn.execute("update chat_pedido set estado='procesando' where id=%s", (p['id'],))
            historial = conn.execute('select mensaje,respuesta from chat_pedido where asignatura_id=%s and usuario=%s '
                                     'and orden<%s and estado=\'completado\' order by orden desc limit 6',
                                     (p['asignatura_id'],p['usuario'],p['orden'])).fetchall()
            contexto = {'facultad': trabajo.agente, 'catalogo': [*[{'id':h,'tipo':d.ambito} for h,d in DEFINICIONES.items()],
                        *[{'id':h,'tipo':tipo,'usa_ia':False} for h,tipo in HERRAMIENTAS_SIN_IA.items()]],
                        'ambitos': ['asignatura', *[f'M{m.numero}' for m in SilaboUTI.model_validate(a['silabo']).momentos],
                                    *[s.id for m in SilaboUTI.model_validate(a['silabo']).momentos for s in m.sesiones]]}
            if r:
                contexto['recurso'] = {'id':str(r['id']),'revision':r['revision'],'herramienta':r['herramienta']}
                if isinstance(r['contenido'], list):
                    contexto['recurso']['items'] = [{'numero':i+1,'item_id':x['item_id'],'nivel':x['nivel'],'pregunta':x['pregunta'][:300]} for i,x in enumerate(r['contenido'])]
                else:
                    contexto['recurso']['rutas'] = [list(x) for x in rutas_editables(r)]
            version = p['silabo']
        # No mantener transacciones mientras el modelo procesa.
        accion = (validar_accion(p['accion']) if p['accion'] else interpretar(cliente, mensaje=p['mensaje'],
                  contexto=contexto, historial=[mensaje for fila in reversed(historial) for mensaje in
                      ({'role':'user','content':fila['mensaje']}, {'role':'assistant','content':fila['respuesta'] or ''})],
                  trabajo_id=trabajo.id, asignatura_id=trabajo.asignatura_id))
        datos = accion.model_dump(mode='json')
        if 'instrucciones' in datos:
            datos['instrucciones'] = limpiar_texto(datos['instrucciones'])
        with conn.transaction():
            cercar()
            _seleccion(conn, p)
            conn.execute('update chat_pedido set accion=%s where id=%s', (Jsonb(datos),p['id']))
        if datos['accion'] in ('aclarar','fuera_de_alcance'):
            with conn.transaction():
                cercar()
                _seleccion(conn, p)
                cerrar('completado', datos['mensaje_al_docente'])
            return
        if datos['accion'] == 'generar':
            with conn.transaction():
                cercar()
                actual, _ = _seleccion(conn, p)
                if actual['silabo'] != version:
                    raise HTTPException(409, 'El sílabo cambió; vuelve a enviar tu pedido')
                ambito = Ambito(**datos['ambito'])
                hs = datos['herramientas']
                if any(h in HERRAMIENTAS_SIN_IA for h in hs):
                    salida = ServicioRecursos._generar_sin_ia(conn, trabajo.asignatura_id, actual, ambito, hs)
                    ids = [x['id'] for x in salida['trabajos']]
                else:
                    if _restriccion(SilaboUTI.model_validate(actual['silabo']), ambito.tipo, ambito.id):
                        raise HTTPException(422, 'La política de IA no permite la generación solicitada')
                    ids = [str(x) for x in crear_trabajos(conn, SolicitudGeneracion(trabajo.asignatura_id, ambito, hs,
                           cantidad=datos['cantidad'], instrucciones=datos['instrucciones']))]
                cerrar('completado', 'Se crearon los trabajos solicitados; revisa su avance.', trabajos=ids)
            return
        if not r or str(datos['recurso_id']) != str(p['recurso_id']):
            raise HTTPException(422, 'Selecciona el recurso que deseas ajustar')
        if len(datos['items']) != len(set(datos['items'])):
            raise HTTPException(422, 'Selección de preguntas duplicada')
        permitidas = set(rutas_editables(r)) if not isinstance(r['contenido'], list) else set()
        if (not datos['items'] and not datos['rutas']) or any(tuple(x) not in permitidas for x in datos['rutas']):
            raise HTTPException(422, 'Selecciona preguntas o textos editables del recurso')
        contenido, verificaciones, revision_ia = regenerar(cliente, recurso=r, contexto=_contexto(r,a),
                       perfil=perfiles[trabajo.agente], accion=datos, trabajo_id=trabajo.id, asignatura_id=trabajo.asignatura_id)
        with conn.transaction():
            cercar()
            _, actual = _seleccion(conn, p)
            if contenido == actual['contenido']:
                cerrar('completado', 'No se detectaron cambios en el recurso.', revision=actual['revision'])
                return
            revision = actual['revision'] + 1
            # Alertas de la revisión exacta realizada, sin atribuir revisión IA al resto.
            alertas = {k:list(v) for k,v in verificaciones.items()}
            for veredicto in revision_ia.get('veredictos', []):
                if veredicto['revisor'] != 'ok':
                    alertas.setdefault(veredicto['item_id'], []).append(veredicto.get('motivo') or 'El revisor requiere revisión docente.')
            conn.execute('insert into recurso_edicion (recurso_id,asignatura_id,usuario,revision,contenido_anterior,'
                         'contenido_nuevo,estado_anterior,verificaciones,revision_ia) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                         (actual['id'],trabajo.asignatura_id,p['usuario'],revision,Jsonb(actual['contenido']),Jsonb(contenido),actual['estado'],Jsonb(alertas),Jsonb(revision_ia)))
            conn.execute("update recurso set contenido=%s,revision=%s,estado='requiere_revision',validado_por=null,validado_en=null,"
                         'verificacion_edicion=%s,actualizado=clock_timestamp() where id=%s and asignatura_id=%s',
                         (Jsonb(contenido),revision,Jsonb(alertas),actual['id'],trabajo.asignatura_id))
            cerrar('completado', 'Ajuste guardado. Revisa las alertas y vuelve a validar el recurso.', revision=revision)
    except HTTPException as error:
        with conn.transaction():
            cercar()
            cerrar('conflicto' if error.status_code==409 else 'error',
                   str(error.detail) if error.status_code in (409,422) else 'El permiso de edición ya no está disponible.')
