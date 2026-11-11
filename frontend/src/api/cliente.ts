/**
 * Cliente mínimo de la API del P4. Todo pasa por /api (proxy de Vite en desarrollo, servidor
 * web en producción) con la cookie de sesión HttpOnly: el frontend nunca ve ni guarda el token.
 */
import type {
  Ambito, AsignaturaResumen, Catalogo, Materia, MenuAsignatura, Recurso, RecursoResumen, Trabajo, TrabajoCreado,
  TipoAmbito, Usuario,
} from './tipos';

const BASE = '/api';

export class ErrorApi extends Error {
  readonly estado: number;
  readonly reintentar?: number;

  constructor(estado: number, mensaje: string, reintentar?: number) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.estado = estado;
    this.reintentar = reintentar;
  }
}

const MENSAJES: Record<number, string> = {
  401: 'Tu sesión terminó. Vuelve a ingresar.',
  403: 'No tienes permiso para esta acción.',
  404: 'No se encontró lo que buscabas.',
  409: 'Los datos cambiaron mientras trabajabas. Recarga e inténtalo de nuevo.',
  503: 'Servicio no disponible por el momento. Inténtalo en unos minutos.',
};

async function error(respuesta: Response): Promise<ErrorApi> {
  const estado = respuesta.status;
  if (estado === 429) {
    const segundos = Number(respuesta.headers.get('Retry-After')) || undefined;
    return new ErrorApi(429, `Demasiados intentos; espera ${segundos ?? 'unos'} s y vuelve a intentarlo.`, segundos);
  }
  if (estado === 422) {
    // Solo los mensajes de texto de la API son para el docente; los de validación son internos.
    const detalle = await respuesta.json().then(d => d?.detail, () => undefined);
    return new ErrorApi(422, typeof detalle === 'string' ? detalle : 'Los datos enviados no son válidos.');
  }
  return new ErrorApi(estado, MENSAJES[estado] ?? 'No se pudo completar la solicitud.');
}

export async function pedir<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const cabeceras = new Headers(init.headers);
  if (init.body !== undefined && !(init.body instanceof Blob) && !cabeceras.has('Content-Type')) {
    cabeceras.set('Content-Type', 'application/json');
  }
  const respuesta = await fetch(`${BASE}${ruta}`, { ...init, headers: cabeceras, credentials: 'include' });
  if (!respuesta.ok) throw await error(respuesta);
  return (respuesta.status === 204 ? undefined : await respuesta.json()) as T;
}

const json = (datos: unknown) => JSON.stringify(datos);

/** Ingreso con el usuario y la clave del SGA. La clave solo viaja en este cuerpo: nunca se guarda ni se registra. */
export const ingresar = (usuario: string, clave: string) =>
  pedir<{ correo: string; materias: Materia[] }>('/auth/ingresar', { method: 'POST', body: json({ usuario, clave }) });

/** Materias del docente en el SGA y si ya se pueden abrir. */
export const materias = () => pedir<Materia[]>('/materias');

/** Si la API ofrece el acceso de prueba sin el SGA (solo en desarrollo). */
export const modoAcceso = () => pedir<{ acceso_prueba: boolean }>('/auth/modo');

/** Sesión sin código; sin correo entra como invitado. */
export const accesoPrueba = (correo?: string) =>
  pedir<{ mensaje: string }>('/auth/prueba', { method: 'POST', body: json(correo ? { correo } : {}) });

export const yo = () => pedir<Usuario>('/auth/yo');

export const salir = () => pedir<{ mensaje: string }>('/auth/salir', { method: 'POST' });

export const asignaturas = () => pedir<AsignaturaResumen[]>('/asignaturas');

const enc = encodeURIComponent;

export const menu = (aid: string) => pedir<MenuAsignatura>(`/asignaturas/${enc(aid)}/menu`);

export const catalogo = (aid: string, tipo: TipoAmbito, id: string) =>
  pedir<Catalogo>(`/asignaturas/${enc(aid)}/herramientas?ambito=${tipo}&id=${enc(id)}`);

export const generar = (aid: string, ambito: Ambito, herramientas: string[]) =>
  pedir<{ trabajos: TrabajoCreado[] }>(`/asignaturas/${enc(aid)}/generar`,
    { method: 'POST', body: json({ ambito, herramientas }) });

export const trabajos = (aid: string, ids?: string[]) => pedir<Trabajo[]>(`/asignaturas/${enc(aid)}/trabajos?limite=200${ids ? ids.map(id => `&ids=${enc(id)}`).join('') : ''}`);

export const recursos = (aid: string) => pedir<RecursoResumen[]>(`/asignaturas/${enc(aid)}/recursos?limite=200`);

export const recurso = (aid: string, rid: string) => pedir<Recurso>(`/asignaturas/${enc(aid)}/recursos/${enc(rid)}`);

export const validar = (aid: string, rid: string, revision: number) =>
  pedir<Recurso>(`/asignaturas/${enc(aid)}/recursos/${enc(rid)}/validar`, { method: 'POST', body: json({ revision }) });

/** Guarda la edición del docente: contenido completo y la revisión que se editó (409 si cambió). */
export const editar = (aid: string, rid: string, revision: number, contenido: unknown) =>
  pedir<Recurso>(`/asignaturas/${enc(aid)}/recursos/${enc(rid)}`, { method: 'PUT', body: json({ revision, contenido }) });

/** Descarga directa (enlace): la cookie viaja sola y la API exige la validación (409 si no). */
export const urlImagen = (aid: string, rid: string, hash: string) =>
  `${BASE}/asignaturas/${enc(aid)}/recursos/${enc(rid)}/imagenes/${enc(hash)}`;

export const urlExportar = (aid: string, rid: string, formato: 'html' | 'pdf' | 'docx' | 'pptx' = 'html', docente = false) =>
  `${BASE}/asignaturas/${enc(aid)}/recursos/${enc(rid)}/exportar?formato=${formato}${docente ? '&version=docente' : ''}`;
