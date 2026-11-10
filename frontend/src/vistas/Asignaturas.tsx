import { useEffect, useState } from 'react';
import { Alert, Badge, Button, DataTable, type Column } from '../components';
import { ErrorApi, asignaturas as listarAsignaturas } from '../api/cliente';
import type { AsignaturaResumen } from '../api/tipos';

interface AsignaturasProps {
  onSesionVencida: () => void;
  onSubir: () => void;
  onAbrir: (asignatura: AsignaturaResumen) => void;
}

const ROLES: Record<AsignaturaResumen['rol'], string> = { dueno: 'Dueño', editor: 'Editor', lector: 'Lector' };

const COLUMNAS: Column<AsignaturaResumen>[] = [
  { key: 'nombre', header: 'Proyecto Formativo' },
  { key: 'codigo_pf', header: 'Código' },
  { key: 'version_silabo', header: 'Versión' },
  { key: 'rol', header: 'Tu rol', render: a => <Badge tone={a.rol === 'dueno' ? 'brand' : 'neutral'}>{ROLES[a.rol]}</Badge> },
];

/** Asignaturas propias y compartidas (GET /asignaturas). */
export function Asignaturas({ onSesionVencida, onSubir, onAbrir }: AsignaturasProps) {
  const [filas, setFilas] = useState<AsignaturaResumen[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let vigente = true;
    listarAsignaturas().then(a => { if (vigente) setFilas(a); }).catch(e => {
      if (!vigente) return;
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor.');
      setFilas([]);
    });
    return () => { vigente = false; };
  }, [onSesionVencida]);

  return <>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-bold">Proyecto Formativo</h1>
      <Button onClick={onSubir}>Elegir materia del SGA</Button>
    </div>
    {error && <Alert tone="danger" role="alert">{error}</Alert>}
    <DataTable caption="Proyecto Formativo" columns={COLUMNAS} rows={filas ?? []} rowKey={a => a.id}
      loading={filas === null} emptyMessage="Todavía no tienes Proyectos Formativos. Elige una materia del SGA para empezar."
      onRowClick={onAbrir} rowActionLabel={a => `Abrir ${a.nombre}`} />
  </>;
}
