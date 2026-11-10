import type { Materia } from '../api/tipos';

/** «CODIGO PARALELO n», como se ve en la pantalla del SGA. */
export const etiquetaMateria = (m: Pick<Materia, 'codigo_pf' | 'paralelo'>) => `${m.codigo_pf} PARALELO ${m.paralelo}`;

const MOTIVOS: Partial<Record<Materia['estado'], string>> = {
  no_disponible: 'Esta materia no está disponible por ahora en el SGA.',
  invalida: 'No se pudo importar el sílabo de esta materia. Avisa al coordinador de tu carrera.',
};

/** Una materia se abre solo si ya tiene asignatura; si no, se explica por qué no. */
export function estadoMateria(m: Materia): { seleccionable: boolean; motivo: string | null } {
  const motivo = MOTIVOS[m.estado] ?? null;
  if (motivo) return { seleccionable: false, motivo };
  if (!m.asignatura_id) return { seleccionable: false, motivo: 'Esta materia todavía no está lista.' };
  return { seleccionable: true, motivo: null };
}

/** Mensaje del formulario de ingreso según el estado HTTP (undefined = sin respuesta del servidor). */
export function mensajeIngreso(estado: number | undefined, reintentar?: number): string {
  if (estado === undefined) return 'No hay conexión con el servidor. Inténtalo de nuevo.';
  if (estado === 401) return 'Usuario o clave incorrectos.';
  if (estado === 429) {
    return `Demasiados intentos; espera ${reintentar ? `${reintentar} s` : 'unos instantes'} y vuelve a intentarlo.`;
  }
  if (estado === 503) return 'El SGA no está disponible por el momento. Inténtalo en unos minutos.';
  return 'No se pudo ingresar. Inténtalo de nuevo.';
}
