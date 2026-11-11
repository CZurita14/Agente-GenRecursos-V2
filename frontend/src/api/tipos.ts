/** Formas de las respuestas de la API del P4 que usa el frontend. */

export interface Usuario {
  correo: string;
  rol: string;
}

export type Rol = 'dueno' | 'editor' | 'lector';

export interface AsignaturaResumen {
  id: string;
  nombre: string;
  codigo_pf: string;
  version_silabo: string;
  agente: string;
  rol: Rol;
  dueno: string;
}

export interface ClaseMenu {
  clase_id: string;
  numero_clase: number;
  dia: string;
  fecha: string;
  momento: number;
  momento_titulo: string;
  contenidos: string[];
  ra: string[];
  entregables: string[];
}

export interface SemanaMenu {
  numero: number;
  inicio: string;
  fin: string;
  clases: ClaseMenu[];
  cierra_momentos: number[];
}

export type EstadoMateria = 'importada' | 'sin_cambios' | 'no_disponible' | 'invalida';

/** Materia del docente en el SGA (GET /materias). */
export interface Materia {
  id_sga: string;
  codigo_pf: string;
  paralelo: string;
  nombre: string;
  carrera: string;
  estado_sga: string;
  estado: EstadoMateria;
  asignatura_id: string | null;
}

export type TipoAmbito = 'clase' | 'momento' | 'asignatura';

export interface Ambito {
  tipo: TipoAmbito;
  id: string;
}

export interface MenuAsignatura {
  id: string;
  rol: Rol;
  version_silabo: string;
  menu: SemanaMenu[];
}

export interface Catalogo {
  ambito: TipoAmbito;
  restringido: boolean;
  motivo: string | null;
  politica_ia: string | null;
  perfil_sugerido: string;
  herramientas: { id: string; recomendada: boolean }[];
}

export type EstadoTrabajo = 'en_cola' | 'en_espera' | 'generando' | 'verificando' | 'revisando'
  | 'listo' | 'requiere_revision' | 'error';

export interface TrabajoCreado {
  id: string;
  herramienta: string;
  estado: EstadoTrabajo;
  recurso_id?: string;
}

export interface Trabajo {
  id: string;
  herramienta: string;
  ambito_tipo: TipoAmbito;
  ambito_id: string;
  estado: EstadoTrabajo;
  lotes_total: number;
  lotes_hechos: number;
  recurso_id: string | null;
  error: string | null;
}

export interface RecursoResumen {
  id: string;
  trabajo_id: string;
  ambito_id: string;
  herramienta: string;
  version_silabo: string;
  estado: 'listo' | 'requiere_revision';
  revision: number;
  creado: string;
  validado: boolean;
}

/** Presentación ordenada de una herramienta (backend: app/exportar/presentacion.py). */
/** Camino dentro del contenido (claves e índices) de un texto editable (P6c). */
export type Ruta = (string | number)[];

export type Bloque =
  | { tipo: 'texto'; titulo: string; texto: string; ruta: Ruta | null }
  | { tipo: 'lista'; titulo: string; items: string[]; numerada: boolean; ruta: Ruta | null }
  | { tipo: 'tabla'; titulo: string; columnas: string[]; filas: string[][]; rutas: (Ruta | null)[][] }
  | { tipo: 'grupo'; titulo: string; bloques: Bloque[] }
  | { tipo: 'imagen'; titulo: string; hash: string; credito: string; vista?: string };

export interface Recurso extends RecursoResumen {
  contenido: unknown;
  presentacion: Bloque[];
  evidencia: Record<string, unknown>;
  validado: boolean;
  validado_por: string | null;
  validado_en: string | null;
  silabo_actualizado: boolean;
  evidencia_vigente: boolean;
  revision_ia?: Record<string, unknown> | null;
  /** Comprobaciones deterministas de la última edición (null si no se ha editado). */
  verificacion_edicion: Record<string, string[]> | null;
  /** Claves que contradicen sus explicaciones; se calcula sobre el contenido actual. */
  revision_claves?: Record<string, string[]>;
}
