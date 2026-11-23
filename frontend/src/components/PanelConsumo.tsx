import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { Gauge, Lock, X } from 'lucide-react';
import { ErrorApi } from '../api/cliente';
import { consumo as cargarConsumo, desbloquearConsumo, type Consumo } from '../api/consumo';
import { nombreAmbito, nombreHerramienta } from '../api/herramientas';
import { formatoCosto, formatoDuracion, formatoTokens, rangoPeriodo, type Periodo } from '../utils/consumo';

interface PanelConsumoProps {
  /** Proyecto formativo abierto; sin él, todos los de la cuenta. */
  aid?: string;
  onSesionVencida: () => void;
}

const PERIODOS: { id: Periodo; texto: string }[] = [{ id: 'hoy', texto: 'Hoy' }, { id: '7d', texto: '7 días' }, { id: 'mes', texto: 'Mes' }];
const ESTADOS: Record<string, string> = { listo: 'listo', requiere_revision: 'revisar', error: 'error' };

/** Botón fijo abajo a la derecha y panel superpuesto: no cambia el layout de la página. */
export function PanelConsumo({ aid, onSesionVencida }: PanelConsumoProps) {
  const [abierto, setAbierto] = useState(false);
  const [periodo, setPeriodo] = useState<Periodo>('mes');
  const [datos, setDatos] = useState<Consumo | null>(null);
  const [bloqueado, setBloqueado] = useState(false);
  const [error, setError] = useState('');
  const [clave, setClave] = useState('');
  const [enviando, setEnviando] = useState(false);
  const boton = useRef<HTMLButtonElement>(null);

  const cargar = useCallback(async () => {
    const { desde, hasta } = rangoPeriodo(periodo);
    try {
      setDatos(await cargarConsumo(desde, hasta, aid));
      setBloqueado(false);
      setError('');
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      if (e instanceof ErrorApi && e.estado === 403) { setBloqueado(true); setDatos(null); return; }
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor.');
    }
  }, [periodo, aid, onSesionVencida]);

  useEffect(() => { if (abierto) void cargar(); }, [abierto, cargar]);

  useEffect(() => {
    if (!abierto) return;
    const cerrar = (e: KeyboardEvent) => { if (e.key === 'Escape') { setAbierto(false); boton.current?.focus(); } };
    window.addEventListener('keydown', cerrar);
    return () => window.removeEventListener('keydown', cerrar);
  }, [abierto]);

  async function desbloquear(e: FormEvent) {
    e.preventDefault();
    if (!clave) { setError('Escribe la clave del panel.'); return; }
    setEnviando(true);
    try {
      await desbloquearConsumo(clave);
      setClave('');
      await cargar();
    } catch (err) {
      setClave('');
      if (err instanceof ErrorApi && err.estado === 401) return onSesionVencida();
      setError(err instanceof ErrorApi && err.estado === 403 ? 'Clave incorrecta.'
        : err instanceof ErrorApi ? err.message : 'No hay conexión con el servidor.');
    } finally {
      setEnviando(false);
    }
  }

  const total = datos ? datos.totales.tokens_entrada + datos.totales.tokens_salida : null;

  return <>
    <button ref={boton} type="button" onClick={() => setAbierto(a => !a)} aria-expanded={abierto} aria-controls="panel-consumo"
      className="fixed z-40 flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 text-sm text-fg shadow-sm hover:bg-app-soft"
      style={{ right: 'max(1rem, env(safe-area-inset-right))', bottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
      <Gauge aria-hidden="true" className="h-4 w-4" />
      <span>{total === null ? 'Consumo' : `${formatoTokens(total)} ${periodo === 'mes' ? 'este mes' : ''}`.trim()}</span>
    </button>

    {abierto && <section id="panel-consumo" role="dialog" aria-modal="false" aria-labelledby="titulo-consumo"
      className="fixed z-40 w-[min(26rem,calc(100vw-2rem))] max-h-[calc(100vh-7rem)] overflow-y-auto rounded-xl border border-line bg-surface p-4 text-sm text-fg shadow-lg"
      style={{ right: 'max(1rem, env(safe-area-inset-right))', bottom: 'calc(max(1rem, env(safe-area-inset-bottom)) + 3.25rem)' }}>
      <div className="mb-3 flex items-center justify-between">
        <h2 id="titulo-consumo" className="flex items-center gap-2 font-bold">
          {bloqueado && <Lock aria-hidden="true" className="h-4 w-4" />}Consumo de IA
        </h2>
        <button type="button" onClick={() => setAbierto(false)} aria-label="Cerrar" className="rounded p-1 text-muted hover:bg-app-soft">
          <X aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>

      {bloqueado && <form onSubmit={desbloquear} className="space-y-2">
        <p className="text-muted">Ingresa la clave del panel para ver el consumo.</p>
        <label htmlFor="clave-consumo" className="block text-xs font-semibold">Clave del panel</label>
        <input id="clave-consumo" type="password" autoComplete="off" value={clave}
          onChange={e => { setClave(e.target.value); setError(''); }}
          className="w-full rounded-lg border border-line bg-surface px-3 py-2" />
        {error && <p role="alert" className="text-xs text-danger">{error}</p>}
        <button type="submit" disabled={enviando} className="w-full rounded-lg bg-action px-4 py-2 font-semibold text-white hover:bg-action-hover disabled:opacity-50">
          Ver consumo
        </button>
      </form>}

      {!bloqueado && <>
        <div className="mb-3 flex gap-1" role="group" aria-label="Periodo">
          {PERIODOS.map(p => <button key={p.id} type="button" onClick={() => setPeriodo(p.id)} aria-pressed={periodo === p.id}
            className={`rounded-lg border px-3 py-1 text-xs ${periodo === p.id ? 'border-highlight bg-highlight-soft font-semibold' : 'border-line'}`}>
            {p.texto}
          </button>)}
        </div>
        {error && <p role="alert" className="mb-2 text-xs text-danger">{error}</p>}
        {!datos && !error && <p role="status" className="text-muted">Cargando…</p>}
        {datos && <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[['Entrada', formatoTokens(datos.totales.tokens_entrada)], ['Salida', formatoTokens(datos.totales.tokens_salida)],
              ['Llamadas', String(datos.totales.llamadas)], ['Costo aprox.', formatoCosto(datos.costo_usd)]].map(([k, v]) =>
              <div key={k} className="rounded-lg bg-app-soft px-2 py-1.5">
                <p className="text-xs text-muted">{k}</p><p className="font-bold">{v}</p>
              </div>)}
          </div>
          <p className="text-xs text-muted">
            {datos.totales.fallos} fallos · {formatoDuracion(datos.totales.segundos)} de IA
            {datos.costo_usd !== null && ' · el costo es un máximo: no cuenta la caché de DeepSeek'}
          </p>

          <Tabla titulo="Por herramienta" columnas={['Herramienta', 'Recursos', 'Tokens', 'Por recurso', 'Revisión']}
            vacio="Sin recursos generados en este periodo."
            filas={[...datos.por_herramienta.map(h => [nombreHerramienta(h.herramienta), String(h.recursos), formatoTokens(h.tokens),
              formatoTokens(h.por_recurso), `${Math.round(h.parte_revision * 100)} %`]),
              ...(datos.chat.pedidos ? [['Chat de ajustes', `${datos.chat.pedidos} pedidos`, formatoTokens(datos.chat.tokens),
                formatoTokens(datos.chat.tokens / datos.chat.pedidos), '—']] : [])]} />

          {!aid && datos.proyectos.length > 1 && <Tabla titulo="Por proyecto formativo" columnas={['Proyecto formativo', 'Recursos', 'Tokens']}
            vacio="" filas={datos.proyectos.map(p => [p.nombre ?? p.codigo_pf, String(p.recursos), formatoTokens(p.tokens)])} />}
          {datos.proyectos.length === 1 && <p className="text-xs text-muted">Proyecto formativo: {datos.proyectos[0].nombre ?? datos.proyectos[0].codigo_pf}</p>}

          <Tabla titulo="Últimos trabajos" columnas={['Herramienta', 'Ámbito', 'Estado', 'Tokens', 'Duración']}
            vacio="Sin trabajos en este periodo."
            filas={datos.recientes.map(r => [nombreHerramienta(r.herramienta), nombreAmbito(r.ambito_id),
              ESTADOS[r.estado] ?? r.estado, formatoTokens(r.tokens), formatoDuracion(r.segundos)])} />
        </div>}
      </>}
    </section>}
  </>;
}

function Tabla({ titulo, columnas, filas, vacio }: { titulo: string; columnas: string[]; filas: string[][]; vacio: string }) {
  return <div>
    <h3 className="mb-1 text-xs font-semibold text-muted">{titulo}</h3>
    {filas.length === 0 ? <p className="text-xs text-muted">{vacio}</p>
      : <div className="overflow-x-auto"><table className="w-full text-xs">
        <thead><tr>{columnas.map((c, i) => <th key={c} scope="col" className={`border-b border-line py-1 font-semibold text-muted ${i ? 'text-right' : 'text-left'}`}>{c}</th>)}</tr></thead>
        <tbody>{filas.map((f, k) => <tr key={k}>{f.map((v, i) =>
          <td key={i} className={`border-b border-line py-1 ${i ? 'text-right' : 'text-left'}`}>{v}</td>)}</tr>)}</tbody>
      </table></div>}
  </div>;
}
