import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { UserPlus, Users } from 'lucide-react';
import { Alert, Badge, Button, Card, Input } from '../components';
import { activarCuenta, crearCuenta, cuentasLocales, ErrorApi, restablecerClave } from '../api/cliente';
import type { CuentaLocal } from '../api/tipos';

interface CuentasProps {
  onSesionVencida: () => void;
}

const DOMINIOS = /^[^@\s]+@(indoamerica\.edu\.ec|uti\.edu\.ec)$/i;
const ALFABETO = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';

/** Clave inicial aleatoria de 12 caracteres (sin letras que se confunden: l, I, O, 0, 1). */
function claveAleatoria() {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  return Array.from(bytes, b => ALFABETO[b % ALFABETO.length]).join('');
}

const fecha = (iso: string | null) => iso ? new Date(iso).toLocaleString('es-EC', { dateStyle: 'short', timeStyle: 'short' }) : '—';

/** Administración (etapa de pruebas): cuentas con correo institucional, sin verificar el correo. */
export function Cuentas({ onSesionVencida }: CuentasProps) {
  const [filas, setFilas] = useState<CuentaLocal[] | null>(null);
  const [correo, setCorreo] = useState('');
  const [nombre, setNombre] = useState('');
  const [clave, setClave] = useState(claveAleatoria);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState<{ correo: string; clave: string; nueva: boolean } | null>(null);
  const [ocupado, setOcupado] = useState('');

  const fallo = useCallback((e: unknown) => {
    if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
    setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor. Inténtalo de nuevo.');
  }, [onSesionVencida]);

  const cargar = useCallback(() => cuentasLocales().then(setFilas).catch(e => { fallo(e); setFilas([]); }), [fallo]);
  useEffect(() => { void cargar(); }, [cargar]);

  const correoMal = correo.trim() && !DOMINIOS.test(correo.trim())
    ? 'Solo correos @indoamerica.edu.ec o @uti.edu.ec.' : '';

  async function crear(evento: FormEvent) {
    evento.preventDefault();
    if (correoMal) return;
    setError(''); setAviso(null); setOcupado('crear');
    try {
      const { correo: creado } = await crearCuenta(correo.trim(), nombre.trim(), clave);
      setAviso({ correo: creado, clave, nueva: true });
      setCorreo(''); setNombre(''); setClave(claveAleatoria());
      await cargar();
    } catch (e) { fallo(e); } finally { setOcupado(''); }
  }

  async function restablecer(c: CuentaLocal) {
    const nueva = claveAleatoria();
    setError(''); setAviso(null); setOcupado(c.correo);
    try {
      await restablecerClave(c.correo, nueva);
      setAviso({ correo: c.correo, clave: nueva, nueva: false });
      await cargar();
    } catch (e) { fallo(e); } finally { setOcupado(''); }
  }

  async function alternar(c: CuentaLocal) {
    setError(''); setAviso(null); setOcupado(c.correo);
    try {
      await activarCuenta(c.correo, !c.activa);
      await cargar();
    } catch (e) { fallo(e); } finally { setOcupado(''); }
  }

  return <>
    <div>
      <h1 className="text-2xl font-bold">Cuentas de prueba</h1>
      <p className="text-muted mt-1">Crea cuentas con correo institucional sin verificar el correo. El docente cambia la clave en su
        primer ingreso y sube el PDF de su sílabo. Solo están disponibles durante la etapa de pruebas.</p>
    </div>

    <Card title="Nueva cuenta" icon={<UserPlus aria-hidden="true" />}>
      <form onSubmit={crear} className="grid gap-4 md:grid-cols-2" noValidate>
        <Input label="Correo institucional" type="email" autoComplete="off" required spellCheck={false} autoCapitalize="none"
          placeholder="nombre@indoamerica.edu.ec" value={correo} onChange={e => setCorreo(e.target.value)}
          error={correoMal || undefined} hint={correoMal ? undefined : 'Solo @indoamerica.edu.ec o @uti.edu.ec.'} />
        <Input label="Nombre (opcional)" autoComplete="off" maxLength={200} value={nombre} onChange={e => setNombre(e.target.value)} />
        <Input label="Clave inicial" autoComplete="off" spellCheck={false} required minLength={10} value={clave}
          onChange={e => setClave(e.target.value)} hint="El docente la cambiará al entrar. Mínimo 10 caracteres." />
        <div className="flex items-end gap-3">
          <Button variant="secondary" onClick={() => setClave(claveAleatoria())}>Otra clave</Button>
          <Button type="submit" loading={ocupado === 'crear'} disabled={!correo.trim() || !!correoMal || clave.length < 10}>Crear cuenta</Button>
        </div>
      </form>
    </Card>

    {aviso && <Alert tone="success" role="status">
      {aviso.nueva ? 'Cuenta creada' : 'Clave restablecida'} para <strong>{aviso.correo}</strong>. Clave inicial:{' '}
      <code className="font-mono font-semibold select-all">{aviso.clave}</code>. Entrégala al docente: no se volverá a mostrar.
    </Alert>}
    {error && <Alert tone="danger" role="alert">{error}</Alert>}

    <Card title="Cuentas creadas" icon={<Users aria-hidden="true" />}>
      {filas === null && <p className="text-muted" role="status">Cargando cuentas…</p>}
      {filas?.length === 0 && <p className="text-muted">Todavía no hay cuentas de prueba.</p>}
      {filas && filas.length > 0 && <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-muted border-b border-line">
            <th className="py-2 pr-3">Correo</th><th className="py-2 pr-3">Estado</th><th className="py-2 pr-3">Materias</th>
            <th className="py-2 pr-3">Último ingreso</th><th className="py-2">Acciones</th>
          </tr></thead>
          <tbody>
            {filas.map(c => <tr key={c.correo} className="border-b border-line align-top">
              <td className="py-2 pr-3"><span className="block font-medium">{c.correo}</span>
                {c.nombre && <span className="block text-xs text-muted">{c.nombre}</span>}</td>
              <td className="py-2 pr-3 space-x-1">
                {c.activa ? <Badge tone="success">Activa</Badge> : <Badge tone="warning">Desactivada</Badge>}
                {c.activa && c.cambiar_clave && <Badge tone="info">Clave inicial</Badge>}
              </td>
              <td className="py-2 pr-3">{c.materias}</td>
              <td className="py-2 pr-3">{fecha(c.ultimo_ingreso)}</td>
              <td className="py-2"><div className="flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" loading={ocupado === c.correo} disabled={!!ocupado}
                  onClick={() => restablecer(c)}>Restablecer clave</Button>
                <Button size="sm" variant={c.activa ? 'ghost' : 'secondary'} disabled={!!ocupado}
                  onClick={() => alternar(c)}>{c.activa ? 'Desactivar' : 'Activar'}</Button>
              </div></td>
            </tr>)}
          </tbody>
        </table>
      </div>}
    </Card>
  </>;
}
