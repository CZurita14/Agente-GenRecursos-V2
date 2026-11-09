import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ErrorApi } from '../api/cliente';
import { agregarHistorial, chatPendiente, consultarChat, enviarChat, historialChat,
  type ChatEnvio, type ChatPedido } from '../api/chat';
import { Alert } from './Alert';
import { Button } from './Button';
import { Card } from './Card';

export interface ChatAjustesProps {
  aid: string;
  rid?: string;
  revision?: number;
  deshabilitado?: boolean;
  onActualizado: () => void;
  onSesionVencida: () => void;
  onTrabajos?: (ids: string[]) => void;
}

const estados: Record<ChatPedido['estado'], string> = {
  en_cola: 'En cola', procesando: 'Procesando', completado: 'Completado',
  conflicto: 'Conflicto: el recurso cambió. Revisa la versión actual antes de solicitar otro ajuste.',
  error: 'No se pudo completar el pedido.',
};

/** La clave reinicia incluso el borrador y los reintentos antes de mostrar otro contexto. */
export function ChatAjustes(props: ChatAjustesProps) {
  return <PanelChat key={JSON.stringify([props.aid, props.rid ?? null])} {...props} />;
}

function PanelChat({ aid, rid, revision, deshabilitado = false, onActualizado, onSesionVencida, onTrabajos }: ChatAjustesProps) {
  const [pedidos, setPedidos] = useState<ChatPedido[]>([]);
  const [mensaje, setMensaje] = useState('');
  const [envio, setEnvio] = useState<ChatEnvio | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [siguiente, setSiguiente] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [errorHistorial, setErrorHistorial] = useState(false);
  const [pausado, setPausado] = useState(false);
  const [seguimiento, setSeguimiento] = useState(0);
  const [actualizar, setActualizar] = useState(false);
  const activo = useRef(false);
  const bloqueoEnvio = useRef(false);
  const bloqueoHistorial = useRef(false);
  const control = useRef<AbortController>();
  const callbacks = useRef({ onActualizado, onSesionVencida });
  callbacks.current = { onActualizado, onSesionVencida };

  function manejar(e: unknown) {
    if (!activo.current) return;
    if (e instanceof ErrorApi && e.estado === 401) callbacks.current.onSesionVencida();
    else setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor. Inténtalo de nuevo.');
  }

  async function cargar(antes?: number) {
    if (bloqueoHistorial.current) return;
    bloqueoHistorial.current = true;
    setCargando(true);
    setErrorHistorial(false);
    const signal = control.current?.signal;
    try {
      const pagina = await historialChat(aid, antes, signal);
      if (!activo.current || signal?.aborted) return;
      setPedidos(prev => agregarHistorial(prev, pagina.pedidos));
      setSiguiente(pagina.siguiente);
    } catch (e) {
      if (!activo.current || signal?.aborted) return;
      setErrorHistorial(true);
      manejar(e);
    } finally {
      if (!signal?.aborted) {
        bloqueoHistorial.current = false;
        if (activo.current) setCargando(false);
      }
    }
  }

  useEffect(() => {
    activo.current = true;
    control.current = new AbortController();
    void cargar();
    return () => { activo.current = false; control.current?.abort(); bloqueoHistorial.current = false; };
  }, []);

  // Si termina durante una edición manual, el padre recibe el aviso al salir de ella.
  useEffect(() => {
    if (actualizar && !deshabilitado) {
      setActualizar(false);
      callbacks.current.onActualizado();
    }
  }, [actualizar, deshabilitado]);

  const pendientes = pedidos.filter(chatPendiente).map(p => p.id).sort().join(',');
  useEffect(() => {
    if (!pendientes) return;
    const abort = new AbortController();
    let vigente = true;
    let demora = 1000;
    const fin = Date.now() + 120_000;
    let temporizador: ReturnType<typeof setTimeout>;
    const limite = setTimeout(() => {
      vigente = false;
      abort.abort();
      clearTimeout(temporizador);
      setPausado(true);
    }, 120_000);
    async function consultar() {
      const resultados = await Promise.allSettled(pendientes.split(',').map(id => consultarChat(aid, id, abort.signal)));
      if (!vigente) return;
      let esperaServidor = 0;
      for (const resultado of resultados) {
        if (resultado.status === 'fulfilled') {
          const pedido = resultado.value;
          setPedidos(prev => prev.map(p => p.id === pedido.id ? pedido : p));
          if (pedido.estado === 'conflicto') setActualizar(true);
          if (pedido.estado === 'completado' && (pedido.revision_resultado !== null || pedido.trabajos.length > 0)) setActualizar(true);
        } else {
          manejar(resultado.reason);
          if (resultado.reason instanceof ErrorApi) {
            if ([401, 403, 404].includes(resultado.reason.estado)) {
              vigente = false;
              clearTimeout(limite);
              setPausado(true);
              return;
            }
            esperaServidor = Math.max(esperaServidor, (resultado.reason.reintentar ?? 0) * 1000);
          }
        }
      }
      demora = Math.min(demora * 2, 10_000);
      temporizador = setTimeout(() => void consultar(), Math.min(Math.max(demora, esperaServidor), Math.max(0, fin - Date.now())));
    }
    setPausado(false);
    temporizador = setTimeout(() => void consultar(), demora);
    return () => { vigente = false; abort.abort(); clearTimeout(temporizador); clearTimeout(limite); };
  }, [aid, pendientes, seguimiento]);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const texto = mensaje.trim();
    if (bloqueoEnvio.current || deshabilitado || cargando || errorHistorial || pendientes || (!envio && (!texto || texto.length > 2000))) return;
    // Un fallo de red puede ocultar un 202: repetir exactamente el cuerpo y UUID.
    const intento = envio ?? { peticion_id: crypto.randomUUID(), mensaje: texto, recurso_id: rid ?? null, revision: rid ? revision ?? null : null };
    bloqueoEnvio.current = true;
    setEnvio(intento);
    setEnviando(true);
    setError('');
    try {
      const pedido = await enviarChat(aid, intento, control.current?.signal);
      if (!activo.current) return;
      setPedidos(prev => agregarHistorial([pedido], prev));
      setEnvio(null);
      setMensaje('');
      if (pedido.estado === 'conflicto') setActualizar(true);
      if (pedido.estado === 'completado' && (pedido.revision_resultado !== null || pedido.trabajos.length > 0)) setActualizar(true);
    } catch (err) {
      if (!activo.current) return;
      // Un rechazo definitivo permite corregir texto/revisión con una nueva petición.
      // Red, 5xx y 429 conservan el intento exacto para evitar duplicados.
      if (err instanceof ErrorApi && err.estado >= 400 && err.estado < 500 && err.estado !== 429) {
        setEnvio(null);
        if (err.estado === 409) setActualizar(true);
      }
      manejar(err);
    }
    finally {
      bloqueoEnvio.current = false;
      if (activo.current) setEnviando(false);
    }
  }

  return <Card title="Ajustar con IA" description="Describe el ajuste. Los cambios deben revisarse y validarse de nuevo.">
    {error && <Alert tone="danger" role="alert">{error}</Alert>}
    {cargando && <p role="status">Cargando historial…</p>}
    {(siguiente !== null || errorHistorial) && <Button variant="secondary" disabled={cargando}
      onClick={() => void cargar(siguiente ?? undefined)}>{errorHistorial ? 'Reintentar historial' : 'Cargar mensajes anteriores'}</Button>}
    <ol aria-label="Historial de ajustes" className="space-y-3 my-4">
      {pedidos.map(p => <li key={p.id} className="rounded-lg border border-line p-3 space-y-2 break-words">
        <p className="text-sm whitespace-pre-wrap"><strong>Tú: </strong>{p.mensaje}</p>
        <p className="text-sm" role="status">{estados[p.estado]}</p>
        {p.respuesta && <p className="text-sm whitespace-pre-wrap"><strong>Asistente: </strong>{p.respuesta}</p>}
        {p.estado === 'completado' && p.revision_resultado !== null && <p className="text-sm">Revisión {p.revision_resultado}. Revisa el resultado y vuelve a validarlo.</p>}
        {p.trabajos.length > 0 && <Button variant="secondary" disabled={deshabilitado || !onTrabajos}
          onClick={() => onTrabajos?.([...p.trabajos])}>Ver avance de generación</Button>}
      </li>)}
    </ol>
    {pausado && <Alert tone="info" role="status">Se pausó la consulta automática; el pedido puede seguir en curso.
      <Button variant="secondary" onClick={() => setSeguimiento(n => n + 1)}>Consultar estado de nuevo</Button>
    </Alert>}
    {deshabilitado && <p role="status">Guarda o cancela la edición manual antes de enviar ajustes.</p>}
    <form onSubmit={enviar} className="space-y-2">
      <label className="block text-sm font-medium">Mensaje de ajuste
        <textarea value={mensaje} onChange={e => setMensaje(e.target.value)} maxLength={2000} rows={3}
          disabled={deshabilitado || enviando || envio !== null}
          className="mt-1 w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-fg" />
      </label>
      <p className="text-xs text-muted">{mensaje.length}/2000 caracteres</p>
      <Button type="submit" loading={enviando} disabled={deshabilitado || cargando || errorHistorial || !!pendientes || (!envio && (!mensaje.trim() || mensaje.trim().length > 2000))}>
        {envio && !enviando ? 'Reintentar envío' : 'Enviar ajuste'}
      </Button>
    </form>
  </Card>;
}
