import type { Ruta } from './tipos';

/** Valor del contenido en la ruta (claves e índices); undefined si no existe. */
export function leer(contenido: unknown, ruta: Ruta): unknown {
  let actual = contenido;
  for (const paso of ruta) {
    if (actual === null || typeof actual !== 'object') return undefined;
    actual = (actual as Record<string | number, unknown>)[paso];
  }
  return actual;
}

/** Copia del contenido con `valor` en la ruta; el original no cambia. */
export function poner<T>(contenido: T, ruta: Ruta, valor: unknown): T {
  if (!ruta.length) return valor as T;
  const copia = structuredClone(contenido);
  let actual = copia as Record<string | number, unknown>;
  for (const paso of ruta.slice(0, -1)) {
    if (actual[paso] === null || typeof actual[paso] !== 'object') throw new Error('Ruta inexistente en el contenido');
    actual = actual[paso] as Record<string | number, unknown>;
  }
  actual[ruta[ruta.length - 1]] = valor;
  return copia;
}
