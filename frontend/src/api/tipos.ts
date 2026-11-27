/** Formas de las respuestas de la API del P4 que usa el frontend. */

export interface Usuario {
  correo: string;
  rol: string;
  /** Etapa de pruebas: cuenta creada por un administrador (sin el SGA). */
  cuenta_local?: boolean;
  /** Debe cambiar la clave inicial antes de seguir. */
  cambiar_clave?: boolean;
  /** El servidor tiene encendidas las cuentas locales. */
  cuentas_locales?: boolean;
}

export interface CuentaLocal {
  correo: string;
  nombre: string;
  activa: boolean;
  cambiar_clave: boolean;
  creada: string;
  creada_por: string;
  ultimo_ingreso: string | null;
  materias: number;
}

export interface SilaboImportado {
  codigo_pf: string;
  nombre: string;
  estado: 'importada' | 'sin_cambios' | 'no_disponible' | 'invalida';
  fallos: string[];
  asignatura_id: string | null;
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

export interface RecursoMomento {
  id: string; herramienta: string; nombre: string; ambito_id: string; estado: string;
  validado: boolean; por_regenerar: boolean;
}

export interface MomentoDetalle {
  numero: number; id: string; titulo: string;
  fase: { nombre: string; proposito: string };
  fecha_inicio: string | null; fecha_fin: string | null;
  ra: { id: string; texto: string }[];
  evidencia: string; politica_ia: string;
  sesiones: { id: string; numero: number; fecha: string | null; contenidos: string[] }[];
  contexto_docente: { texto: string; revision: number; actualizado: string | null; verificaciones: string[] } | null;
  guia: { recurso_id: string; estado: string; validado: boolean; paginas: number; por_regenerar: boolean;
    fuentes?: { silabo: number; web: number } } | null;
  recursos: RecursoMomento[];
  resumen: { total: number; validados: number; por_regenerar: number };
}

export interface MomentosRespuesta { rol: Rol; momentos: MomentoDetalle[] }

export interface ResumenDescarga {
  carpeta: string; validados: number; asignatura: number;
  momentos: { numero: number; titulo: string; fase: string; total: number; validados: number;
    por_regenerar: number; guia_validada: boolean }[];
}

/** Plan de evaluación implícito en el sílabo (norma del RRA, bloques, actividades con peso sugerido). */
export interface ActividadPlan {
  /** «M2-S3/practico/practica_experimental»: identifica la actividad al ajustar los pesos (V4-4). */
  clave?: string;
  sesion: string;
  momento: number;
  columna: 'docente' | 'asincronica' | 'practico' | 'autonomo';
  texto: string;
  tipo: string;
  nombre_tipo: string;
  evaluable: boolean;
  calificacion: string | null;
  instrumento: string | null;
  finalidad: string | null;
  agente: string | null;
  origen: 'rotulo' | 'ia' | 'sin_rotulo';
  bloque: number | null;
  peso_bloque: number;
  peso_final: number;
  /** §6: si la tarea continúa un producto previo, de dónde viene (null si es independiente). */
  dependencia?: { insumo: string | null; origen: string | null; origen_legible: string | null; roto: boolean;
    revisar: boolean } | null;
  herramientas: { herramienta: string; ambito: Ambito; instrucciones?: string }[];
}

export interface PlanEvaluacion {
  rol: Rol;
  modalidad: string;
  norma: {
    modalidad: string; estado: 'definida' | 'pendiente'; bloques: 'parciales' | 'unico' | null;
    pesos: Record<string, number>; componentes: Record<'contacto' | 'practico' | 'autonomo', number>;
    c5: string | null; c4: string | null;
  } | null;
  bloques: { numero: number; nombre: string; inicio: string; fin: string; sesiones: string[] }[];
  clasificacion_ia: 'no_necesaria' | 'pendiente' | 'en_curso' | 'lista' | 'error';
  por_bloque: Record<string, number>;
  por_momento: Record<string, number>;
  alertas: string[];
  /** Cada alerta con cómo corregirla (V4-3); `alertas` queda por compatibilidad. */
  avisos?: { texto: string; sugerencia: string | null }[];
  /** §9.4: momentos ("3") cuya política de IA excluye la IA en una evaluación, con el motivo. */
  ia_restringida?: Record<string, string>;
  actividades: ActividadPlan[];
  /** V4-4: de dónde salen los pesos; `desactualizados` si el docente confirmó otra versión del sílabo. */
  pesos?: { origen: 'docente' | 'sugeridos'; confirmado_por: string | null; confirmado_en: string | null;
    desactualizados: boolean };
  /** Lo que el docente puede repartir: cada calificación de cada bloque, con su % de la norma. */
  grupos?: { bloque: number; calificacion: string; peso: number; claves: string[] }[];
}
