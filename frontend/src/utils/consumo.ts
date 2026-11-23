/** Formatos del panel de consumo (es-EC: coma decimal). */

export type Periodo = 'hoy' | '7d' | 'mes';

const decimal = (n: number, d: number) => n.toFixed(d).replace('.', ',');

/** 8 300 → «8,3 k»; 142 300 → «142 k»; 1 230 000 → «1,23 M». */
export function formatoTokens(n: number): string {
  if (n < 1000) return String(Math.round(n));
  if (n < 1_000_000) return `${decimal(n / 1000, n < 10_000 ? 1 : 0)} k`;
  return `${decimal(n / 1_000_000, 2)} M`;
}

/** null cuando no hay precio de DeepSeek en la configuración. */
export function formatoCosto(usd: number | null): string {
  if (usd === null) return 'sin precio configurado';
  return `US$ ${decimal(usd, usd > 0 && usd < 0.01 ? 4 : 2)}`;
}

export function formatoDuracion(segundos: number): string {
  if (segundos < 60) return `${Math.round(segundos)} s`;
  const min = Math.round(segundos / 60);
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${min % 60} min`;
}

const iso = (d: Date) => d.toISOString().slice(0, 10);

/** Fechas UTC, como las guarda la API. */
export function rangoPeriodo(periodo: Periodo, hoy = new Date()): { desde: string; hasta: string } {
  const hasta = iso(hoy);
  if (periodo === 'hoy') return { desde: hasta, hasta };
  if (periodo === 'mes') return { desde: `${hasta.slice(0, 8)}01`, hasta };
  return { desde: iso(new Date(hoy.getTime() - 6 * 86_400_000)), hasta };
}
