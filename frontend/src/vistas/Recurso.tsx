import { useEffect, useRef, useState, type ReactNode } from 'react';
import { CheckCircle2, Download, Pencil, ShieldCheck, Trash2 } from 'lucide-react';
import { Alert, Badge, Button, Card, Modal } from '../components';
import { ErrorApi, editar, recurso as cargarRecurso, urlExportar, validar } from '../api/cliente';
import { leer, poner } from '../api/edicion';
import type { Bloque, Recurso as TipoRecurso, Ruta } from '../api/tipos';
import { CON_RESPUESTAS, SIN_IA, legible, nombreAmbito, nombreHerramienta } from '../api/herramientas';
import { ChatAjustes } from '../components/ChatAjustes';

interface RecursoProps {
  aid: string;
  rid: string;
  puedeValidar: boolean;
  onVolver: () => void;
  onSesionVencida: () => void;
  onTrabajos?: (ids: string[]) => void;
}

interface Item { item_id: string; pregunta: string; contexto?: string; correcta: number; opciones: { texto: string; justificacion?: string }[] }

/** Lectura y escritura del borrador por ruta (modo edición). */
interface Editor { leer: (ruta: Ruta) => unknown; poner: (ruta: Ruta, valor: unknown) => void }

const esItems = (c: unknown): c is Item[] => Array.isArray(c) && c.every(i => i && typeof i === 'object' && 'opciones' in i);
const letra = (k: number) => String.fromCharCode(65 + k);

/** Alertas por ítem o sección: las del coordinador o, si el docente editó, las de su edición. */
function alertas(r: TipoRecurso): Record<string, string[]> {
  const salida: Record<string, string[]> = {};
  const sumar = (id: string, avisos: string[]) => { salida[id] = [...new Set([...(salida[id] ?? []), ...avisos])]; };
  for (const [id, avisos] of Object.entries(r.revision_claves ?? {})) if (avisos.length) sumar(id, avisos);
  if (!r.evidencia_vigente) {
    for (const [id, fallos] of Object.entries(r.verificacion_edicion ?? {})) if (fallos.length) sumar(id, fallos);
    return salida;
  }
  const verificaciones = (r.evidencia.verificaciones ?? {}) as Record<string, string[]>;
  const veredictos = (r.evidencia.veredictos ?? {}) as Record<string, string>;
  for (const [id, fallos] of Object.entries(verificaciones)) if (fallos.length) sumar(id, fallos);
  for (const [id, veredicto] of Object.entries(veredictos)) if (veredicto !== 'ok') sumar(id, [veredicto]);
  return salida;
}

/** Campo de texto de varias líneas con nombre accesible. */
function Campo({ etiqueta, valor, onCambio, filas = 2 }: { etiqueta: string; valor: unknown; onCambio: (v: string) => void; filas?: number }) {
  return <textarea aria-label={etiqueta} value={String(valor ?? '')} rows={filas} onChange={e => onCambio(e.target.value)}
    className="mt-1 w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-fg" />;
}

/** Bloque de la presentación ordenada; con `ed`, los textos que tienen ruta se editan (React escapa el texto). */
function VistaBloque({ b, nivel = 2, ed }: { b: Bloque; nivel?: number; ed?: Editor }): ReactNode {
  const Titulo = `h${Math.min(nivel + 1, 6)}` as 'h3';
  const titulo = <Titulo className={nivel === 2 ? 'font-bold' : 'text-sm font-bold'}>{b.titulo}</Titulo>;
  if (b.tipo === 'texto') {
    const ruta = b.ruta;
    return <section>{titulo}{ed && ruta
      ? <Campo etiqueta={b.titulo} valor={ed.leer(ruta)} onCambio={v => ed.poner(ruta, v)} filas={b.texto.length > 200 ? 6 : 3} />
      : <p className="text-sm mt-1 whitespace-pre-line">{b.texto}</p>}</section>;
  }
  if (b.tipo === 'lista') {
    const ruta = b.ruta;
    if (ed && ruta) {
      const items = (ed.leer(ruta) as string[] | undefined) ?? [];
      return <section>{titulo}<div className="space-y-1">{items.map((x, i) => <Campo key={i} etiqueta={`${b.titulo} ${i + 1}`}
        valor={x} onCambio={v => ed.poner([...ruta, i], v)} />)}</div></section>;
    }
    const Lista = b.numerada ? 'ol' : 'ul';
    return <section>{titulo}<Lista className={`${b.numerada ? 'list-decimal' : 'list-disc'} pl-6 text-sm space-y-1 mt-1`}>
      {b.items.map((x, i) => <li key={i}>{x}</li>)}</Lista></section>;
  }
  if (b.tipo === 'tabla') return <section>{titulo}<div className="overflow-x-auto mt-1">
    <table className="w-full text-sm border-collapse">
      <thead><tr>{b.columnas.map((c, i) => <th key={i} scope="col" className="border border-line bg-app-soft px-2 py-1 text-left align-top">{c}</th>)}</tr></thead>
      <tbody>{b.filas.map((f, i) => <tr key={i}>{f.map((c, k) => {
        const ruta = b.rutas[i]?.[k];
        return <td key={k} className="border border-line px-2 py-1 align-top">{ed && ruta
          ? <Campo etiqueta={`${b.columnas[k]} ${i + 1}`} valor={ed.leer(ruta)} onCambio={v => ed.poner(ruta, v)} />
          : c}</td>;
      })}</tr>)}</tbody>
    </table></div></section>;
  return <section className="rounded-lg border border-line p-3 space-y-3">{titulo}
    {b.bloques.map((x, i) => <VistaBloque key={i} b={x} nivel={nivel + 1} ed={ed} />)}</section>;
}

/** Pregunta en modo lectura, con la clave marcada. */
function VistaItem({ item }: { item: Item }) {
  return <>
    {item.contexto && <p className="text-sm text-muted italic mt-1">{legible(item.contexto)}</p>}
    <p className="font-medium mt-1">{legible(item.pregunta)}</p>
    <ul className="mt-2 space-y-1 text-sm">{item.opciones.map((o, k) => <li key={k}
      className={k === item.correcta ? 'font-bold text-success' : ''}>
      {letra(k)}) {legible(o.texto)}{k === item.correcta && ' ✓ (clave)'}
    </li>)}</ul>
  </>;
}

/** Pregunta en modo edición: contexto, enunciado, opciones con justificación y clave. */
function EditorItem({ item, n, ed }: { item: Item; n: number; ed: Editor }) {
  const p = `Pregunta ${n + 1}`;
  return <div className="space-y-3 mt-2">
    <label className="block text-sm font-medium">Contexto
      <Campo etiqueta={`${p}: contexto`} valor={item.contexto} onCambio={v => ed.poner([n, 'contexto'], v)} /></label>
    <label className="block text-sm font-medium">Pregunta
      <Campo etiqueta={`${p}: enunciado`} valor={item.pregunta} onCambio={v => ed.poner([n, 'pregunta'], v)} /></label>
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium">Opciones (marca la clave)</legend>
      {item.opciones.map((o, k) => <div key={k} className={`rounded-md border p-2 ${k === item.correcta ? 'border-success' : 'border-line'}`}>
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="radio" name={`clave-${item.item_id}`} checked={k === item.correcta} onChange={() => ed.poner([n, 'correcta'], k)}
            aria-label={`${p}: la clave es la opción ${letra(k)}`} />
          Opción {letra(k)}{k === item.correcta && ' (clave)'}
        </label>
        <Campo etiqueta={`${p}: opción ${letra(k)}`} valor={o.texto} onCambio={v => ed.poner([n, 'opciones', k, 'texto'], v)} filas={1} />
        <Campo etiqueta={`${p}: justificación ${letra(k)}`} valor={o.justificacion} onCambio={v => ed.poner([n, 'opciones', k, 'justificacion'], v)} />
      </div>)}
    </fieldset>
  </div>;
}

/** Pasos 4 y 5: revisar con las alertas, corregir, validar y descargar el HTML para Canvas. */
export function Recurso({ aid, rid, puedeValidar, onVolver, onSesionVencida, onTrabajos }: RecursoProps) {
  const [r, setR] = useState<TipoRecurso | null>(null);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [confirmar, setConfirmar] = useState(false);
  const [validando, setValidando] = useState(false);
  const [borrador, setBorrador] = useState<unknown>(null);  // null: no se está editando.
  const [guardando, setGuardando] = useState(false);
  const [revisionEdicion, setRevisionEdicion] = useState<number | null>(null);
  const edicionActiva = useRef(false);
  const carga = useRef(0);
  const vigente = useRef(true);

  const manejar = (e: unknown) => {
    if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
    setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor.');
  };
  const recargar = () => {
    const turno = ++carga.current;
    return cargarRecurso(aid, rid).then(nuevo => {
      if (vigente.current && turno === carga.current && !edicionActiva.current) setR(nuevo);
    }).catch(e => { if (vigente.current && turno === carga.current) manejar(e); });
  };
  useEffect(() => { vigente.current = true; void recargar(); return () => { vigente.current = false; carga.current++; }; }, [aid, rid]);

  if (!r) return error ? <Alert tone="danger" role="alert">{error}</Alert> : <p className="text-muted" role="status">Cargando el recurso…</p>;

  const avisos = alertas(r);
  const cantidad = Object.keys(avisos).length;
  const editable = puedeValidar && !SIN_IA.has(r.herramienta);
  const editando = borrador !== null;
  const ed: Editor = { leer: ruta => leer(borrador, ruta), poner: (ruta, valor) => setBorrador((b: unknown) => poner(b, ruta, valor)) };

  async function validarRecurso() {
    if (!r) return;
    setConfirmar(false);
    setValidando(true);
    setError('');
    try {
      setR(await validar(aid, r.id, r.revision));
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 409) { setError(e.message); await recargar(); } else manejar(e);
    } finally {
      setValidando(false);
    }
  }

  async function guardar() {
    if (!r) return;
    setGuardando(true);
    setError('');
    try {
      const nuevo = await editar(aid, r.id, revisionEdicion ?? r.revision, borrador);
      const cambio = nuevo.revision !== r.revision;
      setR(nuevo);
      setBorrador(null);
      edicionActiva.current = false;
      setRevisionEdicion(null);
      setAviso(cambio ? 'Cambios guardados. El recurso volvió a «Por validar»: revísalo y valídalo de nuevo.' : 'No había cambios que guardar.');
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 409) setError(`${e.message}. Tu borrador se conserva; cópialo antes de cancelar y cargar la versión actual.`);
      else if (e instanceof ErrorApi && e.estado === 422) setError(`${e.message}. Revisa que ningún campo quede vacío o demasiado corto.`);
      else manejar(e);
    } finally {
      setGuardando(false);
    }
  }

  const items = editando && esItems(borrador) ? borrador : esItems(r.contenido) ? r.contenido : null;

  return <>
    <div>
      <Button variant="ghost" size="sm" onClick={onVolver}>← Volver</Button>
      <h1 className="text-2xl font-bold mt-2">{nombreHerramienta(r.herramienta)}</h1>
      <div className="flex flex-wrap items-center gap-2 mt-2">
        <Badge tone="brand">{nombreAmbito(r.ambito_id)}</Badge>
        {r.revision > 0 && <Badge tone="neutral">Editado por el docente</Badge>}
        {r.validado ? <Badge tone="success" icon={<CheckCircle2 aria-hidden="true" className="w-3 h-3" />}>Validado</Badge>
          : <Badge tone="neutral">Por validar</Badge>}
        {cantidad > 0 && <Badge tone="warning">{cantidad} {cantidad === 1 ? 'alerta' : 'alertas'}</Badge>}
      </div>
    </div>
    {error && <Alert tone="danger" role="alert">{error}</Alert>}
    {aviso && !error && <Alert tone="success" role="status">{aviso}</Alert>}
    {r.silabo_actualizado && <Alert tone="info">El sílabo cambió desde que se generó este recurso.</Alert>}
    {!r.evidencia_vigente && <Alert tone="info">{r.revision_ia
      ? 'El ajuste con IA volvió a verificar el contenido y revisó el alcance indicado en el pedido. Revisa las alertas antes de validar.'
      : 'Las alertas son las comprobaciones de tu última edición; el revisor de IA no vuelve a revisar los cambios.'}</Alert>}

    <Card title="Paso 4 · Revisa el contenido">
      {editable && <div className="flex flex-wrap gap-2 mb-4">{editando ? <>
        <Button onClick={guardar} loading={guardando}>Guardar cambios</Button>
        <Button variant="secondary" onClick={() => { edicionActiva.current = false; setRevisionEdicion(null); setBorrador(null); setError(''); void recargar(); }} disabled={guardando}>Cancelar</Button>
      </> : <Button variant="secondary" icon={<Pencil aria-hidden="true" className="w-4 h-4" />}
        onClick={() => { edicionActiva.current = true; setRevisionEdicion(r.revision); setBorrador(structuredClone(r.contenido)); setAviso(''); setError(''); }}>Editar</Button>}</div>}
      {items ? <ol className="space-y-4">{items.map((item, n) => <li key={item.item_id}
        className={`rounded-lg border p-4 ${avisos[item.item_id] ? 'border-warning bg-warning-soft' : 'border-line'}`}>
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-muted">Pregunta {n + 1}</p>
          {editando && <Button variant="ghost" size="sm" disabled={items.length === 1} icon={<Trash2 aria-hidden="true" className="w-4 h-4" />}
            onClick={() => setBorrador(items.filter((_, k) => k !== n))} aria-label={`Quitar la pregunta ${n + 1}`}>Quitar</Button>}
        </div>
        {editando ? <EditorItem item={item} n={n} ed={ed} /> : <VistaItem item={item} />}
        {avisos[item.item_id]?.map((a, i) => <Alert key={i} tone="warning" className="mt-2">{legible(a)}</Alert>)}
      </li>)}</ol> : <>
        {Object.entries(avisos).map(([id, lista]) => lista.map((a, i) => <Alert key={`${id}${i}`} tone="warning" className="mb-2">{legible(a)}</Alert>))}
        <div className="space-y-4">{r.presentacion.map((b, i) => <VistaBloque key={i} b={b} ed={editando ? ed : undefined} />)}</div>
      </>}
    </Card>

    {editable && <ChatAjustes aid={aid} rid={r.id} revision={r.revision} deshabilitado={editando || guardando}
      onActualizado={() => { void recargar(); }} onSesionVencida={onSesionVencida} onTrabajos={onTrabajos} />}

    <Card title="Paso 5 · Valida y descarga para Canvas" icon={<ShieldCheck aria-hidden="true" />}>
      {editando ? <p className="text-sm text-muted">Guarda o cancela la edición antes de validar.</p> : r.validado ? <div className="space-y-3">
        <Alert tone="success">Validado por {r.validado_por}. Ya puedes descargarlo y subirlo a Canvas.</Alert>
        <a href={urlExportar(aid, r.id)} download
          className="inline-flex items-center gap-2 rounded-lg bg-action hover:bg-action-hover text-white px-4 py-2 font-medium">
          <Download aria-hidden="true" className="w-4 h-4" />Descargar HTML para Canvas
        </a>
        <div className="flex flex-wrap gap-3">
          <a href={urlExportar(aid, r.id, 'pdf')} download className="text-action underline">Descargar PDF</a>
          <a href={urlExportar(aid, r.id, 'docx')} download className="text-action underline">Descargar Word</a>
        </div>
        {CON_RESPUESTAS.has(r.herramienta) && puedeValidar && <div className="rounded-lg border border-line p-3 space-y-2">
          <p className="text-sm"><strong>Solo para el docente.</strong> Las descargas de arriba son para el estudiante y no llevan respuestas. Estas sí: no las compartas.</p>
          <div className="flex flex-wrap gap-3">
            <a href={urlExportar(aid, r.id, 'pdf', true)} download className="text-action underline">Descargar respuestas en PDF</a>
            <a href={urlExportar(aid, r.id, 'docx', true)} download className="text-action underline">Descargar respuestas en Word</a>
          </div>
        </div>}
      </div> : !puedeValidar ? <p className="text-sm text-muted">Un editor o el dueño del Proyecto Formativo debe validarlo antes de descargarlo.</p>
        : <div className="space-y-3">
          <p className="text-sm text-muted">La descarga se habilita cuando validas el recurso: confirma que lo revisaste.</p>
          <Button onClick={() => cantidad > 0 ? setConfirmar(true) : validarRecurso()} loading={validando}>Validar recurso</Button>
        </div>}
    </Card>

    <Modal isOpen={confirmar} onClose={() => setConfirmar(false)} title="¿Validar con alertas pendientes?"
      footer={<div className="flex gap-2 justify-end">
        <Button variant="secondary" onClick={() => setConfirmar(false)}>Seguir revisando</Button>
        <Button onClick={validarRecurso}>Validar de todos modos</Button>
      </div>}>
      <p className="text-sm">Este recurso tiene {cantidad} {cantidad === 1 ? 'alerta' : 'alertas'} del revisor o del verificador.
        Al validarlo confirmas que lo revisaste y que puede usarse con tus estudiantes.</p>
    </Modal>
  </>;
}
