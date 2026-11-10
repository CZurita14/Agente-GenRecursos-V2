import type { Materia } from '../api/tipos';

/** «CODIGO PARALELO n», como se ve en la pantalla del SGA. */
export const etiquetaMateria = (m: Pick<Materia, 'codigo_pf' | 'paralelo'>) => `${m.codigo_pf} PARALELO ${m.paralelo}`;

const MOTIVOS: Record<Materia['estado'], string | null> = {
  importada: null,
  sin_cambios: null,
  no_disponible: 'Esta materia no está disponible por ahora en el SGA.',
  invalida: 'No se pudo importar el sílabo de esta materia. Avisa al coordinador de tu carrera.',
};

const VERSION_ANTERIOR = 'Se usa la última versión importada.';

/**
 * Una materia se abre si ya tiene asignatura. Si el SGA no entregó su sílabo o no se pudo importar,
 * se abre la última versión importada con el motivo como aviso; sin asignatura queda desactivada.
 * Solo se reconocen los estados conocidos (lista blanca): un estado desconocido sin asignatura no se abre.
 */
export function estadoMateria(m: Materia): { seleccionable: boolean; motivo: string | null } {
  const conocido = Object.prototype.hasOwnProperty.call(MOTIVOS, m.estado);
  const motivo = conocido ? MOTIVOS[m.estado] : null;
  if (!m.asignatura_id) {
    return { seleccionable: false, motivo: motivo ?? 'Esta materia todavía no está lista.' };
  }
  if (conocido && motivo === null) return { seleccionable: true, motivo: null };
  return { seleccionable: true, motivo: motivo ? `${motivo} ${VERSION_ANTERIOR}` : VERSION_ANTERIOR };
}

/** Mensaje del formulario de ingreso según el estado HTTP (undefined = sin respuesta del servidor). */
export function mensajeIngreso(estado: number | undefined, reintentar?: number): string {
  if (estado === undefined) return 'No hay conexión con el servidor. Inténtalo de nuevo.';
  if (estado === 401) return 'Correo o clave incorrectos.';
  if (estado === 403) return 'Ese correo no está habilitado para Recursos de estudio.';
  if (estado === 429) {
    return `Demasiados intentos; espera ${reintentar ? `${reintentar} s` : 'unos instantes'} y vuelve a intentarlo.`;
  }
  if (estado === 503) return 'El SGA no está disponible por el momento. Inténtalo en unos minutos.';
  return 'No se pudo ingresar. Inténtalo de nuevo.';
}
