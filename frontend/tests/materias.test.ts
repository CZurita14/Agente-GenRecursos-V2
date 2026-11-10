import assert from 'node:assert/strict';
import { test } from 'node:test';
import { etiquetaMateria, estadoMateria, mensajeIngreso } from '../src/utils/materias.ts';
import type { Materia } from '../src/api/tipos.ts';

const base: Materia = { id_sga: 'm1', codigo_pf: 'B26-SOFT-3', paralelo: '1', nombre: 'ANALISIS DE DATOS',
  carrera: 'SOFTWARE', estado_sga: 'ACTIVA', estado: 'importada', asignatura_id: 'a1' };

test('la etiqueta muestra el código y el paralelo como el SGA', () => {
  assert.equal(etiquetaMateria(base), 'B26-SOFT-3 PARALELO 1');
  assert.equal(etiquetaMateria({ ...base, paralelo: '2' }), 'B26-SOFT-3 PARALELO 2');
});

test('importada y sin_cambios se pueden abrir y llevan su asignatura', () => {
  for (const estado of ['importada', 'sin_cambios'] as const) {
    const e = estadoMateria({ ...base, estado });
    assert.equal(e.seleccionable, true);
    assert.equal(e.motivo, null);
  }
});

test('no_disponible e invalida sin asignatura quedan desactivadas con su motivo', () => {
  const nd = estadoMateria({ ...base, estado: 'no_disponible', asignatura_id: null });
  assert.equal(nd.seleccionable, false);
  assert.match(nd.motivo ?? '', /no está disponible/i);
  const inv = estadoMateria({ ...base, estado: 'invalida', asignatura_id: null });
  assert.equal(inv.seleccionable, false);
  assert.match(inv.motivo ?? '', /no se pudo importar/i);
});

test('no_disponible e invalida con asignatura se abren con la última versión importada', () => {
  for (const estado of ['no_disponible', 'invalida'] as const) {
    const e = estadoMateria({ ...base, estado, asignatura_id: 'a1' });
    assert.equal(e.seleccionable, true);
    assert.match(e.motivo ?? '', /se usa la última versión importada/i);
  }
  assert.match(estadoMateria({ ...base, estado: 'no_disponible' }).motivo ?? '', /no está disponible/i);
  assert.match(estadoMateria({ ...base, estado: 'invalida' }).motivo ?? '', /no se pudo importar/i);
});

test('un estado desconocido sin asignatura queda desactivado', () => {
  const raro = { ...base, estado: 'otro' as unknown as Materia['estado'] };
  assert.equal(estadoMateria({ ...raro, asignatura_id: null }).seleccionable, false);
  assert.equal(estadoMateria({ ...raro, asignatura_id: null, estado: 'toString' as unknown as Materia['estado'] }).seleccionable, false);
  assert.equal(estadoMateria(raro).seleccionable, true);
  assert.match(estadoMateria(raro).motivo ?? '', /se usa la última versión importada/i);
});

test('una materia abrible sin asignatura_id no se ofrece', () => {
  assert.equal(estadoMateria({ ...base, asignatura_id: null }).seleccionable, false);
});

test('mensajes de ingreso por estado', () => {
  assert.equal(mensajeIngreso(401), 'Usuario o clave incorrectos.');
  assert.match(mensajeIngreso(429, 30), /30 s/);
  assert.match(mensajeIngreso(429), /unos instantes/);
  assert.match(mensajeIngreso(503), /SGA no está disponible/);
  assert.match(mensajeIngreso(500), /No se pudo ingresar/);
  assert.match(mensajeIngreso(undefined), /No hay conexión/);
});
