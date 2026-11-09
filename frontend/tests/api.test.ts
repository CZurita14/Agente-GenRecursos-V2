import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { ErrorApi, asignaturas, pedirCodigo, salir, subirSilabo, verificarCodigo, yo, urlExportar } from '../src/api/cliente.ts';

test('descargas con formato explícito y HTML por defecto', () => {
  assert.equal(urlExportar('a/b', 'r?'), '/api/asignaturas/a%2Fb/recursos/r%3F/exportar?formato=html');
  for (const formato of ['pdf', 'docx'] as const) assert.ok(urlExportar('a', 'r', formato).endsWith(`formato=${formato}`));
});

interface Llamada { url: string; init: RequestInit }
const original = globalThis.fetch;
let llamadas: Llamada[] = [];

function responder(estado: number, cuerpo: unknown = {}, cabeceras: Record<string, string> = {}) {
  llamadas = [];
  globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
    llamadas.push({ url, init });
    return new Response(estado === 204 ? null : JSON.stringify(cuerpo),
      { status: estado, headers: { 'Content-Type': 'application/json', ...cabeceras } });
  }) as typeof fetch;
}
afterEach(() => { globalThis.fetch = original; });

test('usa la base /api, credenciales y JSON', async () => {
  responder(200, { mensaje: 'ok' });
  await pedirCodigo('docente@uti.edu.ec');
  const [{ url, init }] = llamadas;
  assert.equal(url, '/api/auth/codigo');
  assert.equal(init.method, 'POST');
  assert.equal(init.credentials, 'include');
  assert.equal(new Headers(init.headers).get('Content-Type'), 'application/json');
  assert.deepEqual(JSON.parse(String(init.body)), { correo: 'docente@uti.edu.ec' });
});

test('verificar, yo, salir y asignaturas', async () => {
  responder(200, { mensaje: 'Sesión iniciada' });
  await verificarCodigo('docente@uti.edu.ec', '123456');
  assert.deepEqual(JSON.parse(String(llamadas[0].init.body)), { correo: 'docente@uti.edu.ec', codigo: '123456' });
  responder(200, { correo: 'docente@uti.edu.ec', rol: 'docente' });
  assert.deepEqual(await yo(), { correo: 'docente@uti.edu.ec', rol: 'docente' });
  assert.equal(llamadas[0].init.method ?? 'GET', 'GET');
  responder(200, { mensaje: 'Sesión cerrada' });
  await salir();
  assert.equal(llamadas[0].url, '/api/auth/salir');
  responder(200, [{ id: 'a1', nombre: 'Datos', codigo_pf: 'B26', version_silabo: '1.0', agente: 'ingenierias', rol: 'dueno', dueno: 'x@uti.edu.ec' }]);
  assert.equal((await asignaturas())[0].nombre, 'Datos');
});

test('el sílabo viaja como PDF binario, no multipart', async () => {
  responder(201, { id: 'a1', agente: 'ingenierias', menu: [], clases_cambiadas: [] });
  const pdf = new File([new Uint8Array([37, 80, 68, 70])], 'silabo.pdf', { type: 'application/pdf' });
  const r = await subirSilabo(pdf);
  assert.equal(r.agente, 'ingenierias');
  const { url, init } = llamadas[0];
  assert.equal(url, '/api/silabos');
  assert.equal(new Headers(init.headers).get('Content-Type'), 'application/pdf');
  assert.equal(init.body, pdf);
});

const casos: [number, unknown, string][] = [
  [401, { detail: 'Sesión requerida' }, 'Tu sesión terminó'],
  [403, { detail: 'x' }, 'No tienes permiso'],
  [413, { detail: 'x' }, 'El archivo supera 10 MB'],
  [415, { detail: 'x' }, 'Solo se aceptan archivos PDF'],
  [422, { detail: 'Falta en el sílabo: carrera.' }, 'Falta en el sílabo: carrera.'],
  [422, { detail: [{ loc: ['body'], msg: 'interno' }] }, 'Los datos enviados no son válidos'],
  [503, { detail: 'x' }, 'Servicio no disponible'],
  [500, { detail: 'Traceback interno' }, 'No se pudo completar la solicitud'],
];
for (const [estado, cuerpo, mensaje] of casos) {
  test(`mensaje en español para ${estado}`, async () => {
    responder(estado, cuerpo);
    await assert.rejects(yo(), (e: unknown) => e instanceof ErrorApi && e.estado === estado
      && e.message.startsWith(mensaje) && !e.message.includes('Traceback'));
  });
}

test('429 informa el tiempo de espera', async () => {
  responder(429, { detail: 'Demasiadas solicitudes' }, { 'Retry-After': '42' });
  await assert.rejects(yo(), (e: unknown) => e instanceof ErrorApi && e.reintentar === 42 && e.message.includes('42'));
});
