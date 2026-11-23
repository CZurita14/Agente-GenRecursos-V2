import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatoCosto, formatoDuracion, formatoTokens, rangoPeriodo } from '../src/utils/consumo.ts';

test('tokens abreviados en español', () => {
  assert.equal(formatoTokens(0), '0');
  assert.equal(formatoTokens(950), '950');
  assert.equal(formatoTokens(8_300), '8,3 k');
  assert.equal(formatoTokens(142_300), '142 k');
  assert.equal(formatoTokens(1_230_000), '1,23 M');
});

test('costo con y sin precio configurado', () => {
  assert.equal(formatoCosto(null), 'sin precio configurado');
  assert.equal(formatoCosto(1.4237), 'US$ 1,42');
  assert.equal(formatoCosto(0.0012), 'US$ 0,0012');
});

test('duraciones legibles', () => {
  assert.equal(formatoDuracion(42), '42 s');
  assert.equal(formatoDuracion(840), '14 min');
  assert.equal(formatoDuracion(7920), '2 h 12 min');
});

test('periodos con fechas UTC y rango de 31 días como máximo', () => {
  const hoy = new Date('2026-11-23T15:00:00Z');
  assert.deepEqual(rangoPeriodo('hoy', hoy), { desde: '2026-11-23', hasta: '2026-11-23' });
  assert.deepEqual(rangoPeriodo('7d', hoy), { desde: '2026-11-17', hasta: '2026-11-23' });
  assert.deepEqual(rangoPeriodo('mes', hoy), { desde: '2026-11-01', hasta: '2026-11-23' });
});
