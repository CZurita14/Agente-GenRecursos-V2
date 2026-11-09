import { useEffect, useState } from 'react';
import { CalendarDays } from 'lucide-react';
import { Alert, Badge, Button } from '../components';
import { ErrorApi, menu as cargarMenu, recursos as cargarRecursos } from '../api/cliente';
import type { Ambito, MenuAsignatura } from '../api/tipos';
import { dia, fechaCorta, nombreAmbito } from '../api/herramientas';

interface AsignaturaProps {
  aid: string;
  nombre: string;
  onElegir: (ambito: Ambito, titulo: string) => void;
  onVerRecursos: () => void;
  onSesionVencida: () => void;
}

/** Paso 1 del recorrido: el menú del Proyecto Formativo por semana; cada clase abre la actividad. */
export function Asignatura({ aid, nombre, onElegir, onVerRecursos, onSesionVencida }: AsignaturaProps) {
  const [datos, setDatos] = useState<MenuAsignatura | null>(null);
  const [cuenta, setCuenta] = useState<Record<string, number>>({});
  const [error, setError] = useState('');

  useEffect(() => {
    let vigente = true;
    Promise.all([cargarMenu(aid), cargarRecursos(aid)]).then(([m, rs]) => {
      if (!vigente) return;
      setDatos(m);
      setCuenta(rs.reduce<Record<string, number>>((c, r) => ({ ...c, [r.ambito_id]: (c[r.ambito_id] ?? 0) + 1 }), {}));
    }).catch(e => {
      if (!vigente) return;
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor.');
    });
    return () => { vigente = false; };
  }, [aid, onSesionVencida]);

  const insignia = (id: string) => cuenta[id]
    ? <Badge tone="success">{cuenta[id]} {cuenta[id] === 1 ? 'recurso' : 'recursos'}</Badge>
    : <Badge tone="neutral">sin generar</Badge>;
  const puedeGenerar = datos?.rol !== 'lector';

  return <>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold">{nombre}</h1>
        <p className="text-muted mt-1">Paso 1 · Elige la clase para preparar sus herramientas.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={onVerRecursos}>Ver recursos</Button>
        {puedeGenerar && <Button variant="secondary"
          onClick={() => onElegir({ tipo: 'asignatura', id: 'asignatura' }, 'Todo el Proyecto Formativo')}>
          Herramientas del Proyecto Formativo
        </Button>}
      </div>
    </div>
    {error && <Alert tone="danger" role="alert">{error}</Alert>}
    {!datos && !error && <p className="text-muted" role="status">Cargando el menú…</p>}
    {datos?.rol === 'lector' && <Alert tone="info">Tienes acceso de lectura: puedes ver los recursos, pero no generarlos.</Alert>}
    {datos?.menu.map(semana => <section key={semana.numero} aria-labelledby={`semana-${semana.numero}`} className="space-y-3">
      <h2 id={`semana-${semana.numero}`} className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-action-ink">
        <CalendarDays aria-hidden="true" className="w-4 h-4" />
        Semana {semana.numero} · {fechaCorta(semana.inicio)} – {fechaCorta(semana.fin)}
      </h2>
      <div className="grid gap-3 md:grid-cols-2">
        {semana.clases.map(clase => <button key={clase.clase_id} type="button" disabled={!puedeGenerar}
          onClick={() => onElegir({ tipo: 'clase', id: clase.clase_id }, `Clase ${clase.numero_clase} · ${nombreAmbito(clase.clase_id)}`)}
          className="text-left bg-surface rounded-xl border border-line p-4 hover:border-highlight focus-visible:border-highlight disabled:cursor-default">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-bold">{dia(clase.dia)} {fechaCorta(clase.fecha)} · Clase {clase.numero_clase}</span>
            {insignia(clase.clase_id)}
          </div>
          <p className="text-sm text-muted mt-1">Momento {clase.momento} · {clase.momento_titulo}</p>
          <p className="text-sm mt-1">{clase.contenidos.join(' · ')}</p>
          {clase.entregables.length > 0 && <p className="text-xs text-muted mt-1">Entregables: {clase.entregables.join(', ')}</p>}
        </button>)}
      </div>
    </section>)}
  </>;
}
