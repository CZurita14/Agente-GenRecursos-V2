import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateFiles } from '../src/utils/files.ts';

const pdf = new File(['pdf'], 'informe.PDF', { type: 'application/pdf' });
const image = new File(['image'], 'foto.png', { type: 'image/png' });
test('rechaza todos los archivos si se excede el modo de archivo único', () => {
  const result = validateFiles([pdf, image]);
  assert.equal(result.accepted.length, 0);
  assert.deepEqual(result.rejected.map(item => item.code), ['too-many-files', 'too-many-files']);
});
test('admite extensiones sin depender de mayúsculas ni de MIME informado', () => {
  const result = validateFiles([new File([''], 'INFORME.PDF')], { accept: ' .png, .pdf ' });
  assert.equal(result.accepted.length, 1);
});
test('admite MIME exacto y comodines; separa los rechazados', () => {
  const result = validateFiles([pdf, image, new File([''], 'datos.csv', { type: 'text/csv' })],
    { accept: 'application/pdf,image/*', multiple: true });
  assert.deepEqual(result.accepted, [pdf, image]);
  assert.equal(result.rejected[0].code, 'invalid-type');
});
test('respeta el límite de tamaño incluyendo su valor exacto', () => {
  const result = validateFiles([new File(['123'], 'ok'), new File(['1234'], 'grande')], { maxSize: 3, multiple: true });
  assert.equal(result.accepted.length, 1);
  assert.equal(result.rejected[0].code, 'too-large');
});
test('no impone restricciones de formato cuando accept está vacío', () => {
  assert.equal(validateFiles([pdf], { accept: '' }).accepted.length, 1);
  assert.deepEqual(validateFiles([]), { accepted: [], rejected: [] });
});
