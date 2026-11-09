import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { registerHooks } from 'node:module';

// El código de Vite usa imports sin extensión; Node ejecuta estas pruebas sin bundler.
registerHooks({ resolve(specifier, context, next) {
  return next(specifier === './cliente' && context.parentURL?.endsWith('/api/chat.ts') ? './cliente.ts' : specifier, context);
} });
const { agregarHistorial, chatPendiente, consultarChat, enviarChat, historialChat } = await import('../src/api/chat.ts');
const { ErrorApi } = await import('../src/api/cliente.ts');
import type { ChatPedido } from '../src/api/chat.ts';

const original = globalThis.fetch;
afterEach(() => { globalThis.fetch = original; });
const pedido: ChatPedido = { id: 'p1', orden: 1, mensaje: 'Ajusta la pregunta 3', estado: 'en_cola',
  respuesta: null, recurso_id: 'r1', revision_resultado: null, trabajos: [], creado: '2026-10-28T12:00:00Z' };

test('historial paginado y consulta codifican IDs y conservan el cursor numérico cero', async () => {
  const urls: string[] = [];
  const control = new AbortController();
  globalThis.fetch = (async (url, init) => {
    urls.push(String(url));
    assert.equal(init?.signal, control.signal);
    assert.equal(init?.credentials, 'include');
    return Response.json(urls.length === 3 ? pedido : { pedidos: [pedido], siguiente: 0 });
  }) as typeof fetch;
  assert.equal((await historialChat('a/b', undefined, control.signal)).siguiente, 0);
  await historialChat('a/b', 0, control.signal);
  assert.deepEqual(await consultarChat('a/b', 'p/?', control.signal), pedido);
  assert.deepEqual(urls, ['/api/asignaturas/a%2Fb/chat?limite=20', '/api/asignaturas/a%2Fb/chat?limite=20&antes=0',
    '/api/asignaturas/a%2Fb/chat/p%2F%3F']);
});

test('POST 202 y reintento conservan UUID, recurso, revisión y mensaje exactos', async () => {
  const envio = { peticion_id: '5f23aa12-7ec5-49db-a858-57cc77da66aa', mensaje: '<script>texto</script>', recurso_id: 'r1', revision: 0 };
  const cuerpos: string[] = [];
  globalThis.fetch = (async (url, init) => {
    assert.equal(url, '/api/asignaturas/a/chat');
    assert.equal(init?.method, 'POST');
    assert.equal(new Headers(init?.headers).get('Content-Type'), 'application/json');
    cuerpos.push(String(init?.body));
    if (cuerpos.length === 1) throw new TypeError('network');
    return Response.json(pedido, { status: 202 });
  }) as typeof fetch;
  await assert.rejects(enviarChat('a', envio));
  assert.deepEqual(await enviarChat('a', envio), pedido);
  assert.equal(cuerpos[0], cuerpos[1]);
  assert.deepEqual(JSON.parse(cuerpos[1]), envio);
});

test('chat de asignatura envía contexto nulo y propaga 401 sin detalles privados', async () => {
  globalThis.fetch = (async (_url, init) => {
    assert.deepEqual(JSON.parse(String(init?.body)), { peticion_id: 'uuid', mensaje: 'Genera', recurso_id: null, revision: null });
    return Response.json({ detail: 'información privada' }, { status: 401 });
  }) as typeof fetch;
  await assert.rejects(enviarChat('a', { peticion_id: 'uuid', mensaje: 'Genera', recurso_id: null, revision: null }),
    (e: unknown) => e instanceof ErrorApi && e.estado === 401 && !e.message.includes('privada'));
});

test('páginas solapadas no revierten estados observados; orden estable por orden del servidor', () => {
  const completado = { ...pedido, estado: 'completado' as const, respuesta: 'Listo', revision_resultado: 1 };
  const anterior = { ...pedido, id: 'anterior', orden: 0 };
  const combinado = agregarHistorial([completado], [pedido, anterior]);
  assert.deepEqual(combinado, [anterior, completado]);
  assert.deepEqual(combinado.filter(chatPendiente).map(p => p.id), ['anterior']);
  for (const estado of ['conflicto', 'error'] as const) assert.equal(chatPendiente({ ...pedido, estado }), false);
});
