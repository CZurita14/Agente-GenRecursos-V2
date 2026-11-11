/** Nombres legibles de las herramientas y cuáles se generan sin IA (P3a). */
export const NOMBRES: Record<string, string> = {
  cuestionario: 'Cuestionario',
  ficha_clase: 'Ficha de clase',
  simulacro: 'Simulacro',
  repaso_momento: 'Repaso integrador',
  guia_evidencia: 'Guía de la evidencia',
  estudio_caso: 'Estudio de caso',
  guia_producto_final: 'Guía del producto final',
  hoja_ruta: 'Hoja de ruta del Proyecto Formativo',
  autoevaluacion_rubrica: 'Autoevaluación con la rúbrica',
  autoevaluacion_final: 'Autoevaluación final',
  lista_evidencia: 'Lista de verificación de la evidencia',
  rubrica_momento: 'Rúbrica del momento',
  rubrica_final: 'Rúbrica del producto final',
  practica_guiada: 'Práctica guiada',
  tarjetas: 'Tarjetas de estudio',
  guia_autonoma: 'Guía de trabajo autónomo',
  guion_clase: 'Guion de clase (docente)',
  presentacion: 'Presentación (PowerPoint)',
};

export const SIN_IA = new Set(['hoja_ruta', 'autoevaluacion_rubrica', 'autoevaluacion_final', 'lista_evidencia', 'rubrica_momento', 'rubrica_final']);

/** Tienen una descarga aparte con las respuestas, solo para el docente; la del estudiante no las lleva. */
export const CON_RESPUESTAS = new Set(['cuestionario', 'simulacro', 'estudio_caso']);

export const nombreHerramienta = (id: string) => NOMBRES[id] ?? id;

/** Códigos a nombres completos, también dentro de lo que redacta la IA; solo al mostrar. */
export function legible(texto: string): string {
  return texto
    .replace(/\bM([1-9]\d?)-S([1-9]\d?)\b/g, 'Momento $1, sesión $2')
    .replace(/\bRA([1-9]\d?)\b/g, 'Resultado de aprendizaje $1')
    .replace(/\bM([1-9]\d?)\b/g, 'Momento $1')
    .replace(/\b(los|Los|sus|Sus) RA\b/g, '$1 resultados de aprendizaje')
    .replace(/\bRA\b/g, 'resultado de aprendizaje');
}

/** «M2-S1» → «Momento 2, sesión 1»; «M2» → «Momento 2»; «asignatura» → «Proyecto Formativo». */
export function nombreAmbito(id: string): string {
  return id === 'asignatura' ? 'Proyecto Formativo' : legible(id);
}

const DIAS: Record<string, string> = { lun: 'lun', mar: 'mar', mie: 'mié', jue: 'jue', vie: 'vie', sab: 'sáb', dom: 'dom' };
export const dia = (d: string) => DIAS[d] ?? d;

/** «2026-10-14» → «14/10» (sin depender de la zona horaria del navegador). */
export const fechaCorta = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
