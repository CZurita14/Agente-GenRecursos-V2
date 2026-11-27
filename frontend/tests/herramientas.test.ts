import assert from 'node:assert/strict';
import { test } from 'node:test';
import { CON_RESPUESTAS, legible, nombreAmbito, nombreHerramienta } from '../src/api/herramientas.ts';

test('el rango de momentos del simulacro acumulativo se lee completo', () => {
  assert.equal(nombreAmbito('M1-M2'), 'Momentos 1 a 2');
  assert.equal(nombreAmbito('M2-S4'), 'Momento 2, sesión 4');
  assert.equal(nombreAmbito('M3'), 'Momento 3');
  assert.equal(legible('Simulacro de M3-M4 con RA2'), 'Simulacro de Momentos 3 a 4 con Resultado de aprendizaje 2');
});

test('las herramientas del plan de evaluación tienen nombre', () => {
  for (const id of ['guia_practica', 'ficha_foro', 'guia_tarea', 'prueba_diagnostica', 'guia_entrega', 'insumo_respaldo']) {
    assert.notEqual(nombreHerramienta(id), id);
  }
  assert.ok(CON_RESPUESTAS.has('prueba_diagnostica'));
});
