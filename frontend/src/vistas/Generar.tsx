import { useEffect, useState } from 'react';
import { BookOpen } from 'lucide-react';
import { Alert, Badge, Card } from '../components';
import { ErrorApi, materias as listarMaterias } from '../api/cliente';
import type { Materia } from '../api/tipos';
import { estadoMateria, etiquetaMateria } from '../utils/materias';

interface GenerarProps {
  onSesionVencida: () => void;
  onAbrir: (materia: Materia & { asignatura_id: string }) => void;
}

/** Paso 1 de «Generar herramientas»: elegir una materia del SGA; ya viene con su sílabo importado. */
export function Generar({ onSesionVencida, onAbrir }: GenerarProps) {
  const [filas, setFilas] = useState<Materia[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let vigente = true;
    listarMaterias().then(m => { if (vigente) setFilas(m); }).catch(e => {
      if (!vigente) return;
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor. Inténtalo de nuevo.');
      setFilas([]);
    });
    return () => { vigente = false; };
  }, [onSesionVencida]);

  return <>
    <div>
      <h1 className="text-2xl font-bold">Generar herramientas</h1>
      <p className="text-muted mt-1">Paso 1 · Elige la materia de tu Proyecto Formativo (las que tienes asignadas en el SGA).</p>
    </div>
    <Card title="Tus materias" icon={<BookOpen aria-hidden="true" />}>
      <div className="space-y-4">
        {error && <Alert tone="danger" role="alert">{error}</Alert>}
        {filas === null && <p className="text-muted" role="status">Cargando tus materias…</p>}
        {filas?.length === 0 && !error && <p className="text-muted">El SGA no te muestra materias asignadas por ahora.</p>}
        {filas && filas.length > 0 && <ul className="space-y-2" aria-label="Materias del SGA">
          {filas.map(m => {
            const { seleccionable, motivo } = estadoMateria(m);
            const detalle = <>
              <span className="block text-xs font-semibold text-muted">{etiquetaMateria(m)}</span>
              <span className="block font-medium">{m.nombre}</span>
              <span className="block text-xs text-muted">{m.carrera}</span>
              {motivo && <span className="block text-sm text-warning mt-1">{motivo}</span>}
            </>;
            return <li key={m.id_sga}>
              {seleccionable && m.asignatura_id
                ? <button type="button" onClick={() => onAbrir({ ...m, asignatura_id: m.asignatura_id as string })}
                  className="w-full text-left rounded-lg border border-line bg-surface p-3 hover:border-highlight flex items-start justify-between gap-3">
                  <span>{detalle}</span>
                  <Badge tone="success">{m.estado === 'importada' ? 'Recién importada' : 'Lista'}</Badge>
                </button>
                : <div aria-disabled="true" className="w-full rounded-lg border border-dashed border-line bg-app-soft p-3 opacity-70 flex items-start justify-between gap-3">
                  <span>{detalle}</span>
                  <Badge tone="warning">No disponible</Badge>
                </div>}
            </li>;
          })}
        </ul>}
      </div>
    </Card>
  </>;
}
