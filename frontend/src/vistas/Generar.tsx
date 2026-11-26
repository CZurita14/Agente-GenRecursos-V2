import { useEffect, useRef, useState } from 'react';
import { BookOpen, FileUp } from 'lucide-react';
import { Alert, Badge, Button, Card } from '../components';
import { ErrorApi, materias as listarMaterias, subirSilaboPdf } from '../api/cliente';
import type { Materia, SilaboImportado } from '../api/tipos';
import { avisoLegible, estadoMateria, etiquetaMateria } from '../utils/materias';

interface GenerarProps {
  /** Cuenta local (etapa de pruebas): sus materias vienen del PDF del sílabo, no del SGA. */
  cuentaLocal?: boolean;
  onSesionVencida: () => void;
  onAbrir: (materia: Materia & { asignatura_id: string }) => void;
}

/** Paso 1 de «Generar herramientas»: elegir una materia del SGA; ya viene con su sílabo importado. */
export function Generar({ cuentaLocal = false, onSesionVencida, onAbrir }: GenerarProps) {
  const [filas, setFilas] = useState<Materia[] | null>(null);
  const [error, setError] = useState('');
  const [recarga, setRecarga] = useState(0);
  const [subiendo, setSubiendo] = useState(false);
  const [resultado, setResultado] = useState<SilaboImportado | null>(null);
  const [errorPdf, setErrorPdf] = useState('');
  const archivo = useRef<HTMLInputElement>(null);

  async function subir(pdf: File | undefined) {
    if (!pdf) return;
    setErrorPdf(''); setResultado(null);
    if (pdf.type && pdf.type !== 'application/pdf') return setErrorPdf('Elige el archivo PDF del sílabo.');
    if (pdf.size > 15 * 1024 * 1024) return setErrorPdf('El PDF pesa más de 15 MB.');
    setSubiendo(true);
    try {
      setResultado(await subirSilaboPdf(pdf));
      setRecarga(n => n + 1);
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setErrorPdf(e instanceof ErrorApi && e.estado === 413 ? 'El PDF es demasiado grande.'
        : e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor. Inténtalo de nuevo.');
    } finally {
      setSubiendo(false);
      if (archivo.current) archivo.current.value = '';
    }
  }

  useEffect(() => {
    let vigente = true;
    listarMaterias().then(m => { if (vigente) setFilas(m); }).catch(e => {
      if (!vigente) return;
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor. Inténtalo de nuevo.');
      setFilas([]);
    });
    return () => { vigente = false; };
  }, [onSesionVencida, recarga]);

  return <>
    <div>
      <h1 className="text-2xl font-bold">Generar herramientas</h1>
      <p className="text-muted mt-1">Paso 1 · Elige la materia de tu Proyecto Formativo
        {cuentaLocal ? ' (las que cargaste con el PDF de su sílabo).' : ' (las que tienes asignadas en el SGA).'}</p>
    </div>
    {cuentaLocal && <Card title="Sube el sílabo" icon={<FileUp aria-hidden="true" />}
      description="Tu cuenta es de la etapa de pruebas: tus materias vienen del PDF del sílabo institucional.">
      <div className="space-y-3">
        <input ref={archivo} type="file" accept="application/pdf,.pdf" className="sr-only" id="silabo-pdf"
          aria-label="PDF del sílabo" onChange={e => subir(e.target.files?.[0])} />
        <Button icon={<FileUp aria-hidden="true" className="w-4 h-4" />} loading={subiendo}
          onClick={() => archivo.current?.click()}>{subiendo ? 'Leyendo el sílabo…' : 'Elegir PDF del sílabo'}</Button>
        <p className="text-xs text-muted">Puede tardar unos segundos. Si vuelves a subir el mismo sílabo, se actualiza la materia.</p>
        {resultado && (resultado.estado === 'invalida'
          ? <Alert tone="warning" role="alert">Se leyó <strong>{resultado.nombre}</strong>, pero el sílabo tiene datos incompletos:
            {' '}{resultado.fallos.slice(0, 4).join('; ')}{resultado.fallos.length > 4 ? '…' : ''}</Alert>
          : <Alert tone="success" role="status"><strong>{resultado.nombre}</strong>
            {resultado.estado === 'sin_cambios' ? ' ya estaba cargada y no cambió.' : ' quedó lista en tus materias.'}</Alert>)}
        {resultado && resultado.estado !== 'invalida' && resultado.fallos.length > 0 &&
          <Alert tone="warning" role="status">Revisa en el PDF del sílabo:
            <ul className="list-disc ml-5 mt-1">{resultado.fallos.slice(0, 6).map(f => <li key={f}>{avisoLegible(f)}</li>)}</ul>
            {resultado.fallos.length > 6 && <span>y {resultado.fallos.length - 6} más.</span>}</Alert>}
        {errorPdf && <Alert tone="danger" role="alert">{errorPdf}</Alert>}
      </div>
    </Card>}
    <Card title="Tus materias" icon={<BookOpen aria-hidden="true" />}>
      <div className="space-y-4">
        {error && <Alert tone="danger" role="alert">{error}</Alert>}
        {filas === null && <p className="text-muted" role="status">Cargando tus materias…</p>}
        {filas?.length === 0 && !error && <p className="text-muted">{cuentaLocal
          ? 'Todavía no tienes materias: sube el PDF de tu sílabo.' : 'El SGA no te muestra materias asignadas por ahora.'}</p>}
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
                  {motivo
                    ? <Badge tone="warning">Versión anterior</Badge>
                    : <Badge tone="success">{m.estado === 'importada' ? 'Recién importada' : 'Lista'}</Badge>}
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
