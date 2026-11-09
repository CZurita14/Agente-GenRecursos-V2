import { pedir } from './cliente';

export interface ChatPedido {
  id: string;
  orden: number;
  mensaje: string;
  estado: 'en_cola' | 'procesando' | 'completado' | 'conflicto' | 'error';
  respuesta: string | null;
  recurso_id: string | null;
  revision_resultado: number | null;
  trabajos: string[];
  creado: string;
}

export interface ChatPagina { pedidos: ChatPedido[]; siguiente: number | null }
export interface ChatEnvio {
  peticion_id: string;
  mensaje: string;
  recurso_id: string | null;
  revision: number | null;
}

const ruta = (aid: string) => `/asignaturas/${encodeURIComponent(aid)}/chat`;

export const historialChat = (aid: string, antes?: number, signal?: AbortSignal) =>
  pedir<ChatPagina>(`${ruta(aid)}?limite=20${antes === undefined ? '' : `&antes=${antes}`}`, { signal });

export const consultarChat = (aid: string, id: string, signal?: AbortSignal) =>
  pedir<ChatPedido>(`${ruta(aid)}/${encodeURIComponent(id)}`, { signal });

export const enviarChat = (aid: string, envio: ChatEnvio, signal?: AbortSignal) =>
  pedir<ChatPedido>(ruta(aid), { method: 'POST', body: JSON.stringify(envio), signal });

export const chatPendiente = (pedido: ChatPedido) => pedido.estado === 'en_cola' || pedido.estado === 'procesando';

/** Una página antigua no debe hacer retroceder el estado de un pedido que ya seguimos. */
export function agregarHistorial(actuales: ChatPedido[], pagina: ChatPedido[]): ChatPedido[] {
  const porId = new Map(pagina.map(p => [p.id, p]));
  for (const pedido of actuales) porId.set(pedido.id, pedido);
  return [...porId.values()].sort((a, b) => a.orden - b.orden);
}
