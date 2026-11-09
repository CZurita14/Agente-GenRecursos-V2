import { useEffect, useState } from 'react';
import { Alert, Badge, Button, Card } from '../components';
import { ErrorApi, trabajos as cargarTrabajos } from '../api/cliente';
import type { EstadoTrabajo, Trabajo, TrabajoCreado } from '../api/tipos';
import { nombreHerramienta } from '../api/herramientas';

interface ProgresoProps {
  aid: string;
  creados: TrabajoCreado[];
  onAbrir: (rid: string) => void;
  onVolver: () => void;
  onSesionVencida: () => void;
}

export const ETAPAS: Record<EstadoTrabajo, { texto: string; avance: number; tono: 'neutral' | 'info' | 'success' | 'warning' | 'danger' }> = {
  en_cola: { texto: 'En espera', avance: 10, tono: 'neutral' },
  en_espera: { texto: 'En espera', avance: 10, tono: 'warning' },
  generando: { texto: 'Generando', avance: 40, tono: 'info' },
  verificando: { texto: 'Generando', avance: 65, tono: 'info' },
  revisando: { texto: 'Generando', avance: 85, tono: 'info' },
  listo: { texto: 'Lista para revisar', avance: 100, tono: 'success' },
  requiere_revision: { texto: 'Lista para revisar', avance: 100, tono: 'success' },
  error: { texto: 'No se pudo generar', avance: 100, tono: 'danger' },
};
export const FINALES = new Set<EstadoTrabajo>(['listo', 'requiere_revision', 'error']);
export const INTERVALO_MS = 4000;

/** Paso 3: avance de los trabajos del pedido; consulta cada 4 s mientras alguno siga activo. */
export function Progreso({ aid, creados, onAbrir, onVolver, onSesionVencida }: ProgresoProps) {
  const [estado, setEstado] = useState<Record<string, Trabajo>>({});
  const [error, setError] = useState('');
  const [ausentes, setAusentes] = useState<string[]>([]);
  const ids = creados.map(t => t.id);
  const terminado = ids.every(id => ausentes.includes(id) || FINALES.has(estado[id]?.estado ?? creados.find(t => t.id === id)!.estado));

  useEffect(() => {
    if (terminado) return;
    let vigente = true;
    const consultar = () => cargarTrabajos(aid, ids).then(lista => {
      if (vigente) {
        setEstado(Object.fromEntries(lista.filter(t => ids.includes(t.id)).map(t => [t.id, t])));
        const faltantes = ids.filter(id => !lista.some(t => t.id === id));
        setAusentes(faltantes);
        if (faltantes.length) setError('Algún trabajo ya no está disponible en este Proyecto Formativo.');
      }
    }).catch(e => {
      if (!vigente) return;
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor; reintentando…');
    });
    consultar();
    const temporizador = setInterval(consultar, INTERVALO_MS);
    return () => { vigente = false; clearInterval(temporizador); };  // Sin intervalos vivos al salir.
  }, [aid, terminado, onSesionVencida, ids.join()]);

  return <>
    <div>
      <Button variant="ghost" size="sm" onClick={onVolver}>← Volver al menú</Button>
      <h1 className="text-2xl font-bold mt-2">Generando herramientas</h1>
      <p className="text-muted mt-1">Paso 3 · La colmena está trabajando. Puedes salir: el avance queda en «Mis recursos».</p>
    </div>
    {error && <Alert tone="warning">{error}</Alert>}
    <div className="grid gap-3">
      {creados.map(c => {
        const t = estado[c.id];
        const etapa = ausentes.includes(c.id) ? { ...ETAPAS.error, texto: 'Trabajo no disponible' } : ETAPAS[t?.estado ?? c.estado];
        const rid = t?.recurso_id ?? c.recurso_id;
        return <Card key={c.id} title={nombreHerramienta(t?.herramienta ?? c.herramienta)}>
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone={etapa.tono}>{etapa.texto}</Badge>
          </div>
          <div className="mt-3 h-2 rounded-full bg-app-soft overflow-hidden" role="progressbar" aria-valuemin={0}
            aria-valuemax={100} aria-valuenow={etapa.avance} aria-label={`Avance de ${nombreHerramienta(c.herramienta)}`}>
            <div className="h-full bg-highlight transition-all" style={{ width: `${etapa.avance}%` }} />
          </div>
          {(t?.estado ?? c.estado) === 'en_cola' && <p className="text-xs text-muted mt-2">Esperando su turno: se genera una herramienta a la vez por Proyecto Formativo. Un cuestionario o un simulacro puede tardar más de 30 minutos.</p>}
          {rid && FINALES.has(t?.estado ?? c.estado) && <div className="mt-3"><Button size="sm" onClick={() => onAbrir(rid)}>Revisar</Button></div>}
        </Card>;
      })}
    </div>
  </>;
}
