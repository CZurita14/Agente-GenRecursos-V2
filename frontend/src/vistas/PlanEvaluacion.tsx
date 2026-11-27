import { useState } from 'react';
import { AlertTriangle, CheckCircle2, Lightbulb, Link2, Sparkles } from 'lucide-react';
import { Alert, Badge } from '../components';
import { ErrorApi, generar, guardarPesos, restaurarPesos } from '../api/cliente';
import type { ActividadPlan, PlanEvaluacion as Plan, TrabajoCreado } from '../api/tipos';
import { fechaCorta, legible, nombreAmbito, nombreHerramienta } from '../api/herramientas';

/** Calificaciones del RRA en el orden de la norma, con su color de la barra. */
export const CALIFICACIONES: { codigo: string; corto: string; color: string }[] = [
  { codigo: 'C1_contacto', corto: 'C1 contacto', color: 'bg-violet-300' },
  { codigo: 'C3_formativa', corto: 'C3 formativa', color: 'bg-violet-500' },
  { codigo: 'C5_sumativa', corto: 'C5 sumativa', color: 'bg-violet-700' },
  { codigo: 'C2_practicas', corto: 'C2 prácticas', color: 'bg-emerald-600' },
  { codigo: 'C1_autonoma', corto: 'C1 autónomas', color: 'bg-orange-300' },
  { codigo: 'C4_proyecto', corto: 'C4 proyecto', color: 'bg-orange-600' },
];
const CORTO = Object.fromEntries(CALIFICACIONES.map(c => [c.codigo, c.corto]));

const MODALIDAD: Record<string, string> = {
  presencial: 'Presencial', en_linea: 'En línea', distancia: 'Distancia', semipresencial: 'Semipresencial',
};
const INSTRUMENTO: Record<string, string> = {
  prueba_objetiva: 'Prueba objetiva', rubrica: 'Rúbrica', lista_cotejo: 'Lista de cotejo',
  guia_observacion: 'Guía de observación', cuestionario_autoevaluacion: 'Cuestionario de autoevaluación',
};
const AGENTE: Record<string, string> = {
  heteroevaluacion: 'heteroevaluación', coevaluacion: 'coevaluación', autoevaluacion: 'autoevaluación',
  coevaluacion_y_heteroevaluacion: 'coevaluación y heteroevaluación',
};
const FINALIDAD: Record<string, string> = { diagnostica: 'diagnóstica', formativa: 'formativa', sumativa: 'sumativa' };
const COLUMNA: Record<string, string> = {
  docente: 'con el docente', asincronica: 'otras actividades con el docente', practico: 'práctico-experimental',
  autonomo: 'trabajo autónomo',
};

const porcentaje = (n: number) => `${n.toLocaleString('es-EC', { maximumFractionDigits: 2 })} %`;
/** Totales por momento: un decimal, igual que en las pestañas de los momentos. */
export const porcentajeMomento = (n: number) => `${n.toLocaleString('es-EC', { maximumFractionDigits: 1 })} %`;

interface NormaProps {
  plan: Plan; aid?: string; lector?: boolean; onPlan?: (p: Plan) => void; onError?: (e: unknown) => void;
}

/** Norma del RRA de la modalidad, bloques de calificación y alertas del plan implícito en el sílabo. */
export function NormaModalidad({ plan, aid, lector = true, onPlan, onError }: NormaProps) {
  const { norma } = plan;
  const cumple = !!norma && norma.estado === 'definida' && plan.alertas.length === 0;
  return <section aria-labelledby="norma" className="bg-surface rounded-xl border border-line p-5 space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 id="norma" className="font-bold">Norma de evaluación de la modalidad</h2>
      <span className="flex flex-wrap gap-1">
        <Badge tone="info">{norma ? MODALIDAD[norma.modalidad] ?? norma.modalidad : plan.modalidad || 'Sin modalidad'} · RRA</Badge>
        {plan.bloques.length > 0 && <Badge tone="neutral">{plan.bloques.length === 1 ? 'Un bloque'
          : `${plan.bloques.length} parciales`}</Badge>}
      </span>
    </div>
    {norma && norma.estado === 'definida' && <>
      <div className="flex h-2.5 overflow-hidden rounded-full" aria-hidden="true">
        {CALIFICACIONES.map(c => <div key={c.codigo} className={c.color} style={{ width: `${norma.pesos[c.codigo] ?? 0}%` }} />)}
      </div>
      <p className="text-sm text-muted">
        {CALIFICACIONES.map(c => `${c.corto} ${norma.pesos[c.codigo]}`).join(' · ')}
        {norma.c5 === 'prueba_y_proyecto_final' && ' · C5 = prueba + proyecto final'}
      </p>
      {plan.bloques.length > 1 && <ul className="flex flex-wrap gap-2 text-sm">{plan.bloques.map(b =>
        <li key={b.numero} className="rounded-lg border border-line px-3 py-1.5">
          <b>{b.nombre}</b> · {fechaCorta(b.inicio)} – {fechaCorta(b.fin)} · {porcentaje(plan.por_bloque[b.numero] ?? 0)} de 100
        </li>)}</ul>}
    </>}
    {plan.clasificacion_ia === 'en_curso' && <p className="text-sm text-info flex items-center gap-1.5" role="status">
      <Sparkles aria-hidden="true" className="w-4 h-4" />Clasificando con IA las actividades que no traen rótulo…</p>}
    {plan.clasificacion_ia === 'error' && <p className="text-sm text-danger">No se pudieron clasificar algunas actividades;
      se muestran como actividades de avance.</p>}
    {cumple && <p className="text-sm text-success flex items-center gap-1.5">
      <CheckCircle2 aria-hidden="true" className="w-4 h-4" />El plan implícito en el sílabo cumple la norma.</p>}
    {plan.alertas.length > 0 && <ul className="space-y-2">{(plan.avisos ?? plan.alertas.map(texto => ({ texto, sugerencia: null })))
      .map(a => <li key={a.texto} className="text-sm">
        <p className="text-warning flex items-start gap-1.5">
          <AlertTriangle aria-hidden="true" className="w-4 h-4 mt-0.5 shrink-0" />{a.texto}</p>
        {a.sugerencia && <p className="text-muted ml-6 flex items-start gap-1.5">
          <Lightbulb aria-hidden="true" className="w-3.5 h-3.5 mt-0.5 shrink-0" />{legible(a.sugerencia)}</p>}
      </li>)}</ul>}
    {plan.pesos?.origen === 'docente'
      ? <p className="text-xs text-success flex items-center gap-1.5">
          <CheckCircle2 aria-hidden="true" className="w-3.5 h-3.5" />Pesos confirmados por {plan.pesos.confirmado_por}
          {plan.pesos.confirmado_en ? ` el ${fechaCorta(plan.pesos.confirmado_en)}` : ''}.</p>
      : <p className="text-xs text-muted">Pesos sugeridos por el sistema a partir del sílabo y la norma; el docente los
          confirma o reparte dentro de cada calificación.</p>}
    {plan.pesos?.desactualizados && <p className="text-xs text-warning">El sílabo cambió desde la última confirmación:
      revisa y confirma de nuevo los pesos.</p>}
    {!lector && aid && onPlan && (plan.grupos?.length ?? 0) > 0 &&
      <AjustePesos plan={plan} aid={aid} onPlan={onPlan} onError={onError} />}
  </section>;
}

const redondear = (n: number) => Math.round(n * 100) / 100;

/** V4-4: el docente reparte el peso entre las actividades de una misma calificación; cada una conserva su % de la norma. */
function AjustePesos({ plan, aid, onPlan, onError }: { plan: Plan; aid: string; onPlan: (p: Plan) => void;
  onError?: (e: unknown) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [pesos, setPesos] = useState<Record<string, number>>({});
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState('');
  const actividad = Object.fromEntries(plan.actividades.filter(a => a.clave).map(a => [a.clave!, a]));
  const abrir = () => {
    setPesos(Object.fromEntries(plan.actividades.filter(a => a.clave && a.evaluable && a.calificacion)
      .map(a => [a.clave!, a.peso_bloque])));
    setAviso(''); setAbierto(true);
  };
  const grupos = (plan.grupos ?? []).filter(g => g.claves.length > 1);
  const suma = (claves: string[]) => redondear(claves.reduce((t, c) => t + (pesos[c] ?? 0), 0));
  const cuadra = (plan.grupos ?? []).every(g => Math.abs(suma(g.claves) - g.peso) < 0.005);
  const bloque = (n: number) => plan.bloques.find(b => b.numero === n)?.nombre ?? 'Bloque único';

  const ejecutar = async (accion: () => Promise<Plan>) => {
    setGuardando(true); setAviso('');
    try { onPlan(await accion()); setAbierto(false); } catch (e) {
      if (e instanceof ErrorApi && e.estado === 401) return onError?.(e);
      setAviso(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor.');
    } finally { setGuardando(false); }
  };

  if (!abierto) return <div className="flex flex-wrap gap-2">
    <button type="button" onClick={abrir}
      className="rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-app-soft">
      {plan.pesos?.origen === 'docente' ? 'Ajustar pesos' : 'Confirmar o ajustar pesos'}</button>
    {plan.pesos?.origen === 'docente' && <button type="button" disabled={guardando}
      onClick={() => ejecutar(() => restaurarPesos(aid))}
      className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-app-soft disabled:opacity-60">
      Volver a los sugeridos</button>}
  </div>;

  return <div className="space-y-3 rounded-lg border border-line p-3" role="group" aria-label="Ajuste de pesos">
    <p className="text-sm">Reparte el peso entre las actividades de cada calificación. Cada calificación conserva el % de
      la norma; las que tienen una sola actividad no se ajustan.</p>
    {grupos.length === 0 && <p className="text-sm text-muted">Ninguna calificación tiene más de una actividad:
      puedes confirmar los pesos sugeridos tal cual.</p>}
    {grupos.map(g => {
      const total = suma(g.claves);
      const ok = Math.abs(total - g.peso) < 0.005;
      return <fieldset key={`${g.bloque}-${g.calificacion}`} className="space-y-1.5">
        <legend className="text-sm font-bold flex flex-wrap items-center gap-2">
          {plan.bloques.length > 1 ? `${bloque(g.bloque)} · ` : ''}{CORTO[g.calificacion] ?? g.calificacion}
          <Badge tone={ok ? 'success' : 'warning'}>{porcentaje(total)} de {porcentaje(g.peso)}</Badge>
        </legend>
        {g.claves.map(c => {
          const a = actividad[c];
          return <label key={c} className="flex items-center justify-between gap-3 text-sm">
            <span>{a ? `${legible(a.sesion)} · ${a.nombre_tipo}` : c}</span>
            <span className="flex items-center gap-1">
              <input type="number" min={0} max={g.peso} step={0.01} value={pesos[c] ?? 0}
                aria-label={`Peso de ${a ? `${legible(a.sesion)}, ${a.nombre_tipo}` : c} (% del bloque)`}
                onChange={e => setPesos(p => ({ ...p, [c]: Number(e.target.value) }))}
                className="w-24 rounded-lg border border-line px-2 py-1 text-right" /> %
            </span>
          </label>;
        })}
      </fieldset>;
    })}
    {aviso && <Alert tone="danger" role="alert">{aviso}</Alert>}
    <div className="flex flex-wrap gap-2">
      <button type="button" disabled={!cuadra || guardando}
        onClick={() => ejecutar(() => guardarPesos(aid, Object.fromEntries(
          Object.entries(pesos).map(([k, v]) => [k, redondear(v)]))))}
        className="rounded-lg bg-action px-3 py-1.5 text-sm text-white disabled:opacity-60">
        {guardando ? 'Guardando…' : 'Confirmar pesos'}</button>
      <button type="button" onClick={() => setAbierto(false)}
        className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-app-soft">Cancelar</button>
    </div>
    {!cuadra && <p className="text-xs text-warning">Cada calificación debe sumar exactamente su % de la norma.</p>}
  </div>;
}

/** §6: de qué producto previo depende la tarea; si es evaluable, se califica solo el avance nuevo (§6.4). */
function Dependencia({ d }: { d: NonNullable<ActividadPlan['dependencia']> }) {
  const insumo = d.insumo ? `«${legible(d.insumo)}»` : 'un producto previo';
  if (d.roto) return <p className="text-xs text-danger flex items-start gap-1.5">
    <AlertTriangle aria-hidden="true" className="w-3.5 h-3.5 mt-0.5 shrink-0" />
    Continúa {insumo}, pero ese insumo no existe en el sílabo o no tiene horas. Revisa la tarea (§6.3).</p>;
  if (d.origen_legible) return <p className="text-xs text-muted flex items-start gap-1.5">
    <Link2 aria-hidden="true" className="w-3.5 h-3.5 mt-0.5 shrink-0" />
    Continúa {insumo} de {d.origen_legible}. Se califica solo el avance nuevo.</p>;
  return <p className="text-xs text-warning flex items-start gap-1.5">
    <Link2 aria-hidden="true" className="w-3.5 h-3.5 mt-0.5 shrink-0" />
    Continúa {insumo} sin un origen claro en las sesiones anteriores; revisa su insumo previo (§6.1).</p>;
}

/** Nombre del botón; si la herramienta cubre varios momentos (simulacro del parcial), lo dice. */
export function etiquetaBoton(h: ActividadPlan['herramientas'][number]): string {
  const rango = /^M\d+-M\d+$/.test(h.ambito.id);
  return rango ? `${nombreHerramienta(h.herramienta)} · ${nombreAmbito(h.ambito.id)}` : nombreHerramienta(h.herramienta);
}

interface PlanMomentoProps {
  aid: string; plan: Plan; numero: number; lector: boolean;
  onGenerado: (creados: TrabajoCreado[]) => void; onError: (e: unknown) => void;
}

/** Actividades evaluables del momento con su calificación, peso, instrumento y las herramientas que las preparan. */
export function PlanMomento({ aid, plan, numero, lector, onGenerado, onError }: PlanMomentoProps) {
  const [generando, setGenerando] = useState('');
  const [aviso, setAviso] = useState<{ clave: string; texto: string } | null>(null);
  const propias = plan.actividades.filter(a => a.momento === numero);
  const evaluables = propias.filter(a => a.evaluable);
  const avance = [...new Set(propias.filter(a => !a.evaluable).map(a => a.sesion))]
    .filter(s => !evaluables.some(e => e.sesion === s));
  const parciales = plan.bloques.length > 1;

  const crear = async (clave: string, h: ActividadPlan['herramientas'][number]) => {
    setGenerando(clave + h.herramienta); setAviso(null);
    try {
      onGenerado((await generar(aid, h.ambito, [h.herramienta], h.instrucciones)).trabajos);
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 401) return onError(e);
      setAviso({ clave, texto: e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor.' });
    } finally { setGenerando(''); }
  };

  const grupos = parciales
    ? plan.bloques.map(b => ({ titulo: b.nombre, filas: evaluables.filter(a => a.bloque === b.numero) })).filter(g => g.filas.length)
    : [{ titulo: '', filas: evaluables }];

  return <div className="space-y-2">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-bold">Plan de evaluación del momento</h3>
      <Badge tone="highlight">{porcentajeMomento(plan.por_momento[numero] ?? 0)} de la nota</Badge>
    </div>
    {plan.ia_restringida?.[String(numero)] && <p className="text-sm text-warning">{plan.ia_restringida[String(numero)]}
      {' '}Se ofrecen solo las herramientas sin IA.</p>}
    {evaluables.length === 0 && <p className="text-sm text-muted">El sílabo no trae actividades evaluables en este momento.</p>}
    {grupos.map(g => <div key={g.titulo || 'todo'}>
      {g.titulo && <p className="text-xs font-bold uppercase tracking-wide text-muted mt-2">{g.titulo}</p>}
      <ul className="divide-y divide-line">{g.filas.map(a => {
        const clave = `${a.sesion}/${a.columna}/${a.tipo}`;
        return <li key={clave} className="py-3 space-y-1.5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="text-sm"><b>{a.sesion.replace(/^M\d+-/, '')} · {a.nombre_tipo}</b>
              <span className="text-muted"> · {COLUMNA[a.columna]}</span></p>
            <span className="flex flex-wrap gap-1">
              {a.calificacion ? <Badge tone="info">{CORTO[a.calificacion]}</Badge> : <Badge tone="neutral">diagnóstica</Badge>}
              <Badge tone="neutral">{porcentaje(a.peso_final)}</Badge>
              {a.origen === 'ia' && <Badge tone="brand" icon={<Sparkles aria-hidden="true" className="w-3 h-3" />}>sugerida por IA</Badge>}
            </span>
          </div>
          <p className="text-sm text-muted line-clamp-2">{a.texto}</p>
          {a.dependencia && <Dependencia d={a.dependencia} />}
          <p className="text-xs text-muted">{a.instrumento ? INSTRUMENTO[a.instrumento] ?? a.instrumento : ''}
            {a.finalidad ? ` · ${FINALIDAD[a.finalidad] ?? a.finalidad}` : ''}{a.agente ? ` · ${AGENTE[a.agente] ?? a.agente}` : ''}</p>
          {!lector && a.herramientas.length > 0 && <div className="flex flex-wrap gap-2">{a.herramientas.map(h =>
            <button key={h.herramienta} type="button" disabled={!!generando}
              onClick={() => crear(clave, h)}
              className="inline-flex items-center gap-1 rounded-lg border border-line px-3 py-1.5 text-sm hover:bg-app-soft disabled:opacity-60">
              <Sparkles aria-hidden="true" className="w-3.5 h-3.5 text-action-ink" />
              {generando === clave + h.herramienta ? 'Encolando…' : etiquetaBoton(h)}
            </button>)}</div>}
          {aviso?.clave === clave && <Alert tone="danger" role="alert">{aviso.texto}</Alert>}
        </li>;
      })}</ul>
    </div>)}
    {avance.length > 0 && <p className="text-sm text-muted border-t border-line pt-2">
      {avance.map(s => s.replace(/^M\d+-/, '')).join(', ')} · actividades de avance (no se califican): práctica guiada,
      tarjetas y guion de clase desde «Más herramientas».</p>}
  </div>;
}
