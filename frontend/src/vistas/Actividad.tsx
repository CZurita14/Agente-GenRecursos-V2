import { useEffect, useState } from 'react';
import { ShieldAlert, Sparkles } from 'lucide-react';
import { Alert, Badge, Button, Card } from '../components';
import { ErrorApi, catalogo as cargarCatalogo, generar } from '../api/cliente';
import type { Ambito, Catalogo, TrabajoCreado } from '../api/tipos';
import { SIN_IA, nombreHerramienta } from '../api/herramientas';

interface ActividadProps {
  aid: string;
  ambito: Ambito;
  titulo: string;
  onGenerado: (trabajos: TrabajoCreado[]) => void;
  onVolver: () => void;
  onSesionVencida: () => void;
}

/** Paso 2: elegir la actividad (herramientas del ámbito) y generar. Respeta §9.4.2. */
export function Actividad({ aid, ambito, titulo, onGenerado, onVolver, onSesionVencida }: ActividadProps) {
  const [datos, setDatos] = useState<Catalogo | null>(null);
  const [elegidas, setElegidas] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    let vigente = true;
    cargarCatalogo(aid, ambito.tipo, ambito.id).then(c => { if (vigente) setDatos(c); }).catch(e => {
      if (!vigente) return;
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor.');
    });
    return () => { vigente = false; };
  }, [aid, ambito.tipo, ambito.id, onSesionVencida]);

  function alternar(id: string) {
    // La API no mezcla herramientas con y sin IA en un pedido: se elige un solo tipo a la vez.
    setElegidas(actual => actual.includes(id) ? actual.filter(x => x !== id)
      : [...actual.filter(x => SIN_IA.has(x) === SIN_IA.has(id)), id]);
  }

  async function enviar() {
    setError('');
    setEnviando(true);
    try {
      onGenerado((await generar(aid, ambito, elegidas)).trabajos);
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor.');
    } finally {
      setEnviando(false);
    }
  }

  return <>
    <div>
      <Button variant="ghost" size="sm" onClick={onVolver}>← Volver al menú</Button>
      <h1 className="text-2xl font-bold mt-2">{titulo}</h1>
      <p className="text-muted mt-1">Paso 2 · Elige la actividad que quieres preparar.</p>
    </div>
    {error && <Alert tone="danger" role="alert">{error}</Alert>}
    {datos?.restringido && <Alert tone="warning" role="alert">{datos.motivo}</Alert>}
    {datos?.politica_ia && <Card title="Política de IA del momento" icon={<ShieldAlert aria-hidden="true" />}>
      <p className="text-sm text-muted">{datos.politica_ia}</p>
    </Card>}
    {!datos && !error && <p className="text-muted" role="status">Cargando las herramientas…</p>}
    {datos && <Card title="Herramientas" icon={<Sparkles aria-hidden="true" />}>
      {datos.herramientas.length === 0 ? <p className="text-sm text-muted">No hay herramientas disponibles para este ámbito.</p>
        : <fieldset className="space-y-2">
          <legend className="sr-only">Herramientas para generar</legend>
          {datos.herramientas.map(h => <label key={h.id}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-line p-3 cursor-pointer hover:bg-app-soft">
            <input type="checkbox" checked={elegidas.includes(h.id)} onChange={() => alternar(h.id)} />
            <span className="font-medium">{nombreHerramienta(h.id)}</span>
            {SIN_IA.has(h.id) ? <Badge tone="neutral">sin IA</Badge> : <Badge tone="info">con IA</Badge>}
            {h.recomendada && <Badge tone="highlight">recomendada</Badge>}
          </label>)}
          <p className="text-xs text-muted">Las herramientas sin IA salen al instante del sílabo; las que usan IA pueden tardar unos minutos.</p>
        </fieldset>}
      <div className="mt-4"><Button onClick={enviar} loading={enviando} disabled={elegidas.length === 0}>Generar</Button></div>
    </Card>}
  </>;
}
