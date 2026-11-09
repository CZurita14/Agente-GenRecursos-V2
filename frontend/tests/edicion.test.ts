import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { editar } from '../src/api/cliente.ts';
import { leer, poner } from '../src/api/edicion.ts';

const FICHA = { conceptual: { ideas_clave: ['A', 'B'] }, aplicacion: { ejemplo: { pasos: ['P1'] } } };

test('leer sigue claves e índices', () => {
  assert.equal(leer(FICHA, ['conceptual', 'ideas_clave', 1]), 'B');
  assert.equal(leer(FICHA, ['no', 'existe']), undefined);
  assert.equal(leer([{ pregunta: 'x' }], [0, 'pregunta']), 'x');
});

test('poner devuelve una copia y no toca el original', () => {
  const nuevo = poner(FICHA, ['aplicacion', 'ejemplo', 'pasos', 0], 'Paso corregido');
  assert.equal(leer(nuevo, ['aplicacion', 'ejemplo', 'pasos', 0]), 'Paso corregido');
  assert.equal(FICHA.aplicacion.ejemplo.pasos[0], 'P1');
  assert.deepEqual(nuevo.conceptual, FICHA.conceptual);
  assert.throws(() => poner(FICHA, ['no', 'existe'], 'x'));
});

const original = globalThis.fetch;
afterEach(() => { globalThis.fetch = original; });

test('editar envía PUT con la revisión y el contenido completo', async () => {
  let llamada: { url: string; init: RequestInit } | undefined;
  globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
    llamada = { url, init };
    return new Response(JSON.stringify({ id: 'r1', revision: 1 }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
  const r = await editar('a1', 'r1', 0, FICHA);
  assert.equal(r.revision, 1);
  assert.equal(llamada?.url, '/api/asignaturas/a1/recursos/r1');
  assert.equal(llamada?.init.method, 'PUT');
  assert.deepEqual(JSON.parse(String(llamada?.init.body)), { revision: 0, contenido: FICHA });
});
