import { useState } from 'react';
import { FileUp } from 'lucide-react';
import { Alert, Button, Card, DropZone } from '../components';
import { ErrorApi, subirSilabo } from '../api/cliente';
import type { SilaboSubido } from '../api/tipos';

interface GenerarProps {
  onSesionVencida: () => void;
  onVerAsignaturas: () => void;
}

const MAX_PDF = 10 * 1024 * 1024; // Límite de la API (spec v1.3, C11).

/** Paso 1 de «Generar herramientas»: subir el sílabo; la colmena lo lee y arma el menú de clases. */
export function Generar({ onSesionVencida, onVerAsignaturas }: GenerarProps) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState('');
  const [resultado, setResultado] = useState<SilaboSubido | null>(null);

  async function subir() {
    if (!archivo) return;
    setError('');
    setSubiendo(true);
    try {
      setResultado(await subirSilabo(archivo));
      setArchivo(null);
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor. Inténtalo de nuevo.');
    } finally {
      setSubiendo(false);
    }
  }

  const clases = resultado?.menu.reduce((total, semana) => total + semana.clases.length, 0) ?? 0;

  return <>
    <div>
      <h1 className="text-2xl font-bold">Generar herramientas</h1>
      <p className="text-muted mt-1">Paso 1 · Sube el sílabo de tu Proyecto Formativo en PDF (el que genera el sistema institucional).</p>
    </div>
    <Card title="Sube tu sílabo" icon={<FileUp aria-hidden="true" />}>
      <div className="space-y-4">
        <DropZone accept=".pdf,application/pdf" maxSize={MAX_PDF} disabled={subiendo}
          title="Arrastra aquí el sílabo en PDF" hint="o selecciónalo desde tu equipo (máx. 10 MB)"
          onFiles={archivos => { setArchivo(archivos[0] ?? null); setResultado(null); setError(''); }} />
        {archivo && <p className="text-sm">Archivo seleccionado: <strong>{archivo.name}</strong></p>}
        {error && <Alert tone="danger" role="alert">{error}</Alert>}
        {resultado && <Alert tone="success">
          Sílabo leído. Agente asignado: <strong>{resultado.agente}</strong>. Menú de {resultado.menu.length} semanas
          y {clases} clases.{resultado.clases_cambiadas.length > 0 && ` Clases actualizadas por la nueva versión: ${resultado.clases_cambiadas.join(', ')}.`}
        </Alert>}
        <div className="flex flex-wrap gap-3">
          <Button onClick={subir} loading={subiendo} disabled={!archivo}>Subir sílabo</Button>
          {resultado && <Button variant="secondary" onClick={onVerAsignaturas}>Ver mis Proyectos Formativos</Button>}
        </div>
      </div>
    </Card>
  </>;
}
