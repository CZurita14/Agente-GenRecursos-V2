import { useCallback, useEffect, useState } from 'react';
import { BookOpenCheck, ChevronRight, Download, RefreshCw } from 'lucide-react';
import { Alert, Badge, Button } from '../components';
import {
  ErrorApi, generar, guardarContexto, momentos as cargarMomentos, planEvaluacion, resumenDescarga, urlDescarga,
} from '../api/cliente';
import type { Ambito, MomentoDetalle, PlanEvaluacion, ResumenDescarga, TrabajoCreado } from '../api/tipos';
import { NormaModalidad, PlanMomento, porcentajeMomento } from './PlanEvaluacion';
import { fechaCorta, nombreAmbito } from '../api/herramientas';

interface MomentosProps {
  aid: string;
  nombre: string;
  onVolver: () => void;
  onElegir: (ambito: Ambito, titulo: string) => void;
  onAbrir: (rid: string) => void;
  onGenerado: (creados: TrabajoCreado[]) => void;
  onSesionVencida: () => void;
}

const mensaje = (e: unknown) => e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor.';

/** Trazabilidad M1 → M4: cada momento con su contexto (editable), su guía de estudio y sus herramientas. */
export function Momentos({ aid, nombre, onVolver, onElegir, onAbrir, onGenerado, onSesionVencida }: MomentosProps) {
  const [lista, setLista] = useState<MomentoDetalle[] | null>(null);
  const [lector, setLector] = useState(false);
  const [resumen, setResumen] = useState<ResumenDescarga | null>(null);
  const [error, setError] = useState('');
  const [abierto, setAbierto] = useState<number | null>(null);
  const [plan, setPlan] = useState<PlanEvaluacion | null>(null);

  const fallo = useCallback((e: unknown) => {
    if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
    setError(mensaje(e));
  }, [onSesionVencida]);

  useEffect(() => {
    let vigente = true;
    Promise.all([cargarMomentos(aid), resumenDescarga(aid)]).then(([m, r]) => {
      if (!vigente) return;
      setLista(m.momentos);
      setLector(m.rol === 'lector');
      setResumen(r);
      setAbierto(a => a ?? m.momentos[0]?.numero ?? null);
    }).catch(e => vigente && fallo(e));
    return () => { vigente = false; };
  }, [aid, fallo]);

  // Plan de evaluación implícito en el sílabo; mientras la IA clasifica, se vuelve a pedir cada 5 s.
  useEffect(() => {
    let vigente = true;
    let espera: ReturnType<typeof setTimeout> | undefined;
    const cargar = () => planEvaluacion(aid).then(p => {
      if (!vigente) return;
      setPlan(p);
      if (p.clasificacion_ia === 'en_curso') espera = setTimeout(cargar, 5000);
    }).catch(e => vigente && fallo(e));
    cargar();
    return () => { vigente = false; clearTimeout(espera); };
  }, [aid, fallo]);

  const reemplazar = (m: MomentoDetalle) => {
    setLista(l => l?.map(x => x.numero === m.numero ? m : x) ?? null);
    resumenDescarga(aid).then(setResumen).catch(() => undefined);
  };

  return <>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <button type="button" onClick={onVolver} className="text-sm text-muted hover:text-fg">← Volver al Proyecto Formativo</button>
        <h1 className="text-2xl font-bold mt-1">{nombre}</h1>
        <p className="text-muted mt-1">Momentos del proyecto: contexto, guía de estudio y herramientas de cada uno.</p>
      </div>
    </div>
    {error && <Alert tone="danger" role="alert">{error}</Alert>}
    {!lista && !error && <p className="text-muted" role="status">Cargando los momentos…</p>}
    {plan && <NormaModalidad plan={plan} />}
    {lista && <ol aria-label="Trazabilidad de momentos" className="flex flex-wrap items-center gap-2">
      {lista.map((m, i) => <li key={m.numero} className="flex items-center gap-2">
        <button type="button" onClick={() => setAbierto(m.numero)} aria-current={abierto === m.numero}
          className={`rounded-lg border px-3 py-2 text-left text-sm ${abierto === m.numero ? 'border-highlight bg-highlight-soft' : 'border-line bg-surface'}`}>
          <span className="block font-bold">Momento {m.numero}</span>
          <span className="block text-xs text-muted">{m.fase.nombre}</span>
          {plan?.norma?.estado === 'definida' && <span className="block text-xs font-bold text-action-ink">
            {porcentajeMomento(plan.por_momento[m.numero] ?? 0)} de la nota</span>}
        </button>
        {i < lista.length - 1 && <ChevronRight aria-hidden="true" className="w-4 h-4 text-muted" />}
      </li>)}
    </ol>}
    {lista?.filter(m => m.numero === abierto).map(m => <TarjetaMomento key={m.numero} aid={aid} momento={m}
      lector={lector} plan={plan} onCambio={reemplazar} onError={fallo} onElegir={onElegir} onAbrir={onAbrir}
      onGenerado={onGenerado} />)}
    {resumen && <Descarga aid={aid} resumen={resumen} />}
  </>;
}

interface TarjetaProps {
  aid: string; momento: MomentoDetalle; lector: boolean; plan: PlanEvaluacion | null;
  onCambio: (m: MomentoDetalle) => void; onError: (e: unknown) => void;
  onElegir: (ambito: Ambito, titulo: string) => void; onAbrir: (rid: string) => void;
  onGenerado: (creados: TrabajoCreado[]) => void;
}

function TarjetaMomento({ aid, momento: m, lector, plan, onCambio, onError, onElegir, onAbrir, onGenerado }: TarjetaProps) {
  const [texto, setTexto] = useState(m.contexto_docente?.texto ?? '');
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState<{ tono: 'success' | 'danger'; texto: string } | null>(null);
  const [generando, setGenerando] = useState(false);
  const cambiado = texto.trim() !== (m.contexto_docente?.texto ?? '');

  const guardar = async () => {
    setGuardando(true); setAviso(null);
    try {
      const nuevo = await guardarContexto(aid, m.numero, m.contexto_docente?.revision ?? 0, texto);
      setTexto(nuevo.contexto_docente?.texto ?? texto);
      onCambio(nuevo);
      setAviso({ tono: 'success', texto: 'Contexto validado y guardado. La guía y las herramientas generadas antes quedan por regenerar.' });
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 401) return onError(e);
      setAviso({ tono: 'danger', texto: mensaje(e) });
    } finally { setGuardando(false); }
  };

  const generarGuia = async () => {
    setGenerando(true);
    try {
      const r = await generar(aid, { tipo: 'momento', id: m.id }, ['guia_estudio']);
      onGenerado(r.trabajos);
    } catch (e) { onError(e); } finally { setGenerando(false); }
  };

  const guia = m.guia;
  const estadoGuia = !guia ? <Badge tone="neutral">sin generar</Badge>
    : guia.por_regenerar ? <Badge tone="warning">por regenerar</Badge>
    : guia.validado ? <Badge tone="success">validada · {guia.paginas} págs.</Badge>
    : <Badge tone="info">por validar · {guia.paginas} págs.</Badge>;

  return <section aria-labelledby={`momento-${m.numero}`} className="bg-surface rounded-xl border border-line p-5 space-y-5">
    <header>
      <p className="text-xs font-bold uppercase tracking-wide text-action-ink">Momento {m.numero} · {m.fase.nombre}</p>
      <h2 id={`momento-${m.numero}`} className="text-xl font-bold mt-1">{m.titulo}</h2>
      <p className="text-sm text-muted mt-1">
        {m.fecha_inicio && m.fecha_fin ? `${fechaCorta(m.fecha_inicio)} – ${fechaCorta(m.fecha_fin)} · ` : ''}
        En este momento se {m.fase.proposito}.
      </p>
    </header>

    <div className="grid gap-4 md:grid-cols-2">
      <div className="space-y-3">
        <h3 className="font-bold">Lo que trae el sílabo</h3>
        <div>
          <p className="text-sm font-semibold">Resultados de aprendizaje</p>
          <ul className="text-sm list-disc pl-5">{m.ra.map(r => <li key={r.id}><b>{r.id}</b>: {r.texto}</li>)}</ul>
        </div>
        <div>
          <p className="text-sm font-semibold">Sesiones</p>
          <ul className="text-sm space-y-1">{m.sesiones.map(s => <li key={s.id}>
            <b>Sesión {s.numero}</b>{s.fecha ? ` (${fechaCorta(s.fecha)})` : ''}: {s.contenidos.join(' · ')}
          </li>)}</ul>
        </div>
        {m.evidencia && <div><p className="text-sm font-semibold">Evidencia</p><p className="text-sm">{m.evidencia}</p></div>}
      </div>
      <div className="space-y-2">
        <h3 className="font-bold">Contexto del docente</h3>
        <p className="text-xs text-muted">Complementa el sílabo para generar la guía y las herramientas de este momento.
          Se valida al guardar: sin datos personales, sin órdenes al sistema y sin pedir que se resuelva la evidencia.</p>
        <textarea aria-label={`Contexto del momento ${m.numero}`} value={texto} onChange={e => setTexto(e.target.value)}
          readOnly={lector} maxLength={6000} rows={9}
          className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-fg" />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-muted">{texto.length} / 6000
            {m.contexto_docente ? ` · revisión ${m.contexto_docente.revision}` : ' · sin contexto propio'}</span>
          {!lector && <Button size="sm" onClick={guardar} loading={guardando} disabled={!cambiado}>Validar y guardar</Button>}
        </div>
        {m.contexto_docente && <div className="flex flex-wrap gap-1">
          {m.contexto_docente.verificaciones.map(v => <Badge key={v} tone="success">✓ {v}</Badge>)}
        </div>}
        {aviso && <Alert tone={aviso.tono} role="status">{aviso.texto}</Alert>}
      </div>
    </div>

    <div className="rounded-lg border border-line p-4 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BookOpenCheck aria-hidden="true" className="w-5 h-5 text-action-ink" />
          <h3 className="font-bold">Guía de estudio del momento</h3>
          {estadoGuia}
        </div>
        <div className="flex flex-wrap gap-2">
          {guia && <Button size="sm" variant="secondary" onClick={() => onAbrir(guia.recurso_id)}>Abrir y validar</Button>}
          {!lector && <Button size="sm" onClick={generarGuia} loading={generando}
            icon={guia ? <RefreshCw aria-hidden="true" className="w-4 h-4" /> : undefined}>
            {guia ? 'Regenerar guía' : 'Generar guía'}</Button>}
        </div>
      </div>
      <p className="text-sm text-muted">La parte teórica del momento (de 10 a 15 páginas), apoyada en la bibliografía del
        sílabo y en fuentes web verificadas con su enlace. Una vez validada, es la base con la que se generan las
        herramientas del momento y de sus clases.</p>
      {guia?.fuentes && <p className="text-xs text-muted">Bibliografía: {guia.fuentes.silabo} del sílabo ·
        {' '}{guia.fuentes.web} fuentes web con enlace</p>}
    </div>

    {plan && <PlanMomento aid={aid} plan={plan} numero={m.numero} lector={lector} onGenerado={onGenerado}
      onError={onError} />}

    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-bold">Herramientas generadas</h3>
        {!lector && <Button size="sm" variant="secondary"
          onClick={() => onElegir({ tipo: 'momento', id: m.id }, `Momento ${m.numero} · ${m.titulo}`)}>
          Más herramientas</Button>}
      </div>
      {m.recursos.length === 0 ? <p className="text-sm text-muted">Todavía no hay herramientas generadas en este momento.</p>
        : <ul className="divide-y divide-line">{m.recursos.map(r => <li key={r.id}
          className="flex flex-wrap items-center justify-between gap-2 py-2">
          <button type="button" className="text-left text-sm hover:underline" onClick={() => onAbrir(r.id)}>
            {r.nombre} <span className="text-muted">· {r.ambito_id === m.id ? 'momento' : nombreAmbito(r.ambito_id)}</span>
          </button>
          <span className="flex gap-1">
            {r.por_regenerar && <Badge tone="warning">por regenerar</Badge>}
            {r.validado ? <Badge tone="success">validada</Badge> : <Badge tone="neutral">por validar</Badge>}
          </span>
        </li>)}</ul>}
    </div>
  </section>;
}

function Descarga({ aid, resumen }: { aid: string; resumen: ResumenDescarga }) {
  const pendientes = resumen.momentos.reduce((n, m) => n + (m.total - m.validados), 0);
  const regenerar = resumen.momentos.reduce((n, m) => n + m.por_regenerar, 0);
  return <section aria-labelledby="descarga" className="bg-surface rounded-xl border border-line p-5 space-y-3">
    <h2 id="descarga" className="text-lg font-bold">Descargar el perfil docente</h2>
    <p className="text-sm text-muted">Se descarga una carpeta <b>{resumen.carpeta}</b> con lo validado, ordenado por momento.</p>
    <table className="w-full text-sm">
      <thead><tr className="text-left text-muted"><th className="py-1">Momento</th><th>Guía</th><th>Validadas</th><th>Por regenerar</th></tr></thead>
      <tbody>{resumen.momentos.map(m => <tr key={m.numero} className="border-t border-line">
        <td className="py-1">M{m.numero} · {m.fase}</td>
        <td>{m.guia_validada ? '✓' : '—'}</td>
        <td>{m.validados} de {m.total}</td>
        <td>{m.por_regenerar || '—'}</td>
      </tr>)}</tbody>
    </table>
    {(pendientes > 0 || regenerar > 0) && <Alert tone="warning">
      {pendientes > 0 && `${pendientes} herramienta(s) sin validar no se incluirán. `}
      {regenerar > 0 && `${regenerar} quedaron por regenerar tras cambiar el contexto o la guía.`}
    </Alert>}
    {resumen.validados > 0
      ? <a href={urlDescarga(aid)} download
        className="inline-flex items-center gap-1.5 rounded-lg bg-action px-4 py-2 text-sm font-semibold text-white hover:bg-action-hover">
        <Download aria-hidden="true" className="w-4 h-4" />Descargar {resumen.validados} validadas (ZIP)</a>
      : <p className="text-sm text-muted">Valida al menos una herramienta para poder descargar.</p>}
  </section>;
}
