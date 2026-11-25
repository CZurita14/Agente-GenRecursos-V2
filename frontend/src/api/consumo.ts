/** Panel de consumo de tokens (GET /consumo, POST /consumo/desbloquear). */
import { pedir } from './cliente';

export interface ConsumoHerramienta {
  herramienta: string; recursos: number; tokens: number; por_recurso: number; parte_revision: number; costo_usd: number;
  /** Tiempo de IA por recurso, en segundos (suma de sus llamadas, sin la espera en cola). */
  segundos_por_recurso?: number;
}
export interface ConsumoProyecto { id: string; codigo_pf: string; nombre: string | null; tokens: number; recursos: number }
export interface ConsumoReciente {
  herramienta: string; ambito_id: string; estado: string; tokens: number; segundos: number; creado: string;
}
/** SearchAPI (solo la guía de estudio): una consulta es un crédito. */
export interface BusquedaWeb {
  proveedor: string; creditos: number; fallidas: number; segundos: number; momentos: number;
  saldo: number | null;
  por_momento: { codigo_pf: string; nombre: string | null; momento: number; creditos: number; segundos: number; fuentes: number }[];
}
export interface Consumo {
  desde: string; hasta: string;
  totales: { llamadas: number; tokens_entrada: number; tokens_salida: number; segundos: number; fallos: number; tokens_cache: number };
  por_herramienta: ConsumoHerramienta[];
  busqueda_web?: BusquedaWeb;
  chat: { pedidos: number; tokens: number };
  proyectos: ConsumoProyecto[];
  recientes: ConsumoReciente[];
  /** Costo con la tarifa de DeepSeek de cada llamada; las anteriores al registro se estiman al máximo. */
  costo_usd: number;
  costo_estimado_llamadas: number;
  tarifa: { vigencia: string; fuente: string };
}

export const consumo = (desde: string, hasta: string, asignatura?: string) =>
  pedir<Consumo>(`/consumo?desde=${desde}&hasta=${hasta}${asignatura ? `&asignatura=${encodeURIComponent(asignatura)}` : ''}`);

/** La clave solo viaja en este cuerpo; la API responde con una cookie HttpOnly de 30 minutos. */
export const desbloquearConsumo = (clave: string) =>
  pedir<void>('/consumo/desbloquear', { method: 'POST', body: JSON.stringify({ clave }) });
