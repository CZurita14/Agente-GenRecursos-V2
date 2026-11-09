"""Encolado e historial privados. Ninguna llamada al modelo se realiza en HTTP."""
from fastapi import HTTPException
from psycopg.types.json import Jsonb

from app.cola.trabajos import Ambito, encolar
from app.herramientas.sin_ia import HERRAMIENTAS_SIN_IA
from app.recursos.servicio import _recurso, _contexto, _restriccion
from app.silabo.modelo import SilaboUTI


def publico(f):
    return {k: f[k] for k in ('id','orden','mensaje','estado','respuesta','recurso_id','revision_resultado','trabajos','creado')}


class ServicioChat:
    def __init__(self, recursos):
        self.recursos = recursos

    def enviar(self, aid, usuario, peticion_id, mensaje, recurso_id=None, revision=None, accion=None):
        if not mensaje.strip() or len(mensaje) > 2000 or ((recurso_id is None) != (revision is None)):
            raise HTTPException(422, 'Pedido de ajustes no válido')
        with self.recursos._acceso(aid, usuario, editar=True) as (conn, a):
            # Serializa cuotas y deduplicación de este usuario incluso entre asignaturas.
            conn.execute('select pg_advisory_xact_lock(hashtextextended(%s, 4242))', (usuario,))
            previo = conn.execute('select * from chat_pedido where asignatura_id=%s and usuario=%s and peticion_id=%s',
                                  (aid, usuario, peticion_id)).fetchone()
            if previo:
                if (previo['mensaje'], previo['recurso_id'], previo['revision'], previo['entrada_accion']) != (mensaje, recurso_id, revision, accion):
                    raise HTTPException(409, 'Este identificador ya corresponde a otro pedido')
                return publico(previo)
            if conn.execute("select count(*) n from chat_pedido p join trabajo t on t.id=p.trabajo_id "
                            "where p.usuario=%s and t.estado in ('en_cola','en_espera','generando','verificando','revisando')", (usuario,)).fetchone()['n'] >= 3:
                raise HTTPException(429, 'Espera a que terminen tus ajustes pendientes', headers={'Retry-After': '30'})
            if conn.execute("select count(*) n from chat_pedido where usuario=%s and creado > now()-interval '1 hour'", (usuario,)).fetchone()['n'] >= 30:
                raise HTTPException(429, 'Límite de ajustes alcanzado', headers={'Retry-After': '60'})
            if recurso_id:
                r = _recurso(conn, aid, recurso_id)
                if r['revision'] != revision:
                    raise HTTPException(409, 'El recurso cambió; recárgalo antes de ajustar')
                if r['herramienta'] in HERRAMIENTAS_SIN_IA:
                    raise HTTPException(422, 'Esta herramienta reproduce el sílabo y no se ajusta con IA')
                _contexto(r, a)
                tipo = 'asignatura' if r['ambito_id'] == 'asignatura' else ('clase' if '-S' in r['ambito_id'] else 'momento')
                if motivo := _restriccion(SilaboUTI.model_validate(r['snapshot']['silabo']), tipo, r['ambito_id']):
                    raise HTTPException(422, motivo)
                if motivo := _restriccion(SilaboUTI.model_validate(a['silabo']), tipo, r['ambito_id']):
                    raise HTTPException(422, motivo)
            fila = conn.execute('insert into chat_pedido (asignatura_id,usuario,peticion_id,mensaje,recurso_id,revision,accion,entrada_accion,silabo) '
                                'values (%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *',
                                (aid, usuario, peticion_id, mensaje, recurso_id, revision, Jsonb(accion) if accion else None, Jsonb(accion) if accion else None,Jsonb(a['silabo']))).fetchone()
            tid = encolar(conn, asignatura_id=aid, agente=a['agente'], ambito=Ambito('asignatura','asignatura'),
                          herramienta='chat', tipo='chat', parametros={'pedido_id': str(fila['id'])})
            conn.execute('update chat_pedido set trabajo_id=%s where id=%s', (tid, fila['id']))
            return publico(fila)

    def listar(self, aid, usuario, limite=20, antes=None):
        with self.recursos._acceso(aid, usuario, editar=True) as (conn, _):
            filas = conn.execute('select p.*,t.estado estado_trabajo from chat_pedido p join trabajo t on t.id=p.trabajo_id '
                                 'where p.asignatura_id=%s and p.usuario=%s and (%s::bigint is null or orden<%s) '
                                 'order by orden desc limit %s', (aid, usuario, antes, antes, limite+1)).fetchall()
            return {'pedidos': [self._estado(f) for f in filas[:limite]],
                    'siguiente': filas[limite-1]['orden'] if len(filas)>limite else None}

    @staticmethod
    def _estado(f):
        resultado = publico(f)
        if f['estado'] in ('en_cola','procesando') and f['estado_trabajo'] == 'error':
            resultado.update(estado='error', respuesta='No se pudo completar el pedido. Puedes volver a intentarlo.')
        return resultado

    def obtener(self, aid, usuario, pedido):
        with self.recursos._acceso(aid, usuario, editar=True) as (conn, _):
            fila = conn.execute('select p.*,t.estado estado_trabajo from chat_pedido p join trabajo t on t.id=p.trabajo_id '
                                'where p.id=%s and p.asignatura_id=%s and p.usuario=%s', (pedido,aid,usuario)).fetchone()
            if not fila:
                raise HTTPException(404, 'Pedido inexistente')
            return self._estado(fila)
