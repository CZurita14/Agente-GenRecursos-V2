import { useEffect, useRef, useState, type FormEvent } from 'react';
import { KeyRound, Mail } from 'lucide-react';
import { Alert, Button, Card, Input } from '../components';
import { ErrorApi, modoAcceso, pedirCodigo } from '../api/cliente';

interface IngresoProps {
  onIngresar: (correo: string, codigo: string) => Promise<void>;
  onIngresarPrueba: (correo?: string) => Promise<void>;
}

const DOMINIOS = 'Usa tu correo @uti.edu.ec o @indoamerica.edu.ec.';

function mensaje(e: unknown, paso: 'correo' | 'codigo'): string {
  if (e instanceof ErrorApi) {
    if (e.estado === 403) return `Ese correo no está permitido. ${DOMINIOS}`;
    if (e.estado === 401 && paso === 'codigo') return 'El código no es válido o venció. Revísalo o pide uno nuevo.';
    return e.message;
  }
  return 'No hay conexión con el servidor. Inténtalo de nuevo.';
}

/** Ingreso en dos pasos: correo institucional y código de 6 dígitos enviado al correo (spec §2.1). */
export function Ingreso({ onIngresar, onIngresarPrueba }: IngresoProps) {
  const [paso, setPaso] = useState<'correo' | 'codigo'>('correo');
  const [correo, setCorreo] = useState('');
  const [codigo, setCodigo] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [modoPrueba, setModoPrueba] = useState(false);
  const codigoRef = useRef<HTMLInputElement>(null);

  // Si la consulta falla se muestra el ingreso normal con código.
  useEffect(() => {
    let vigente = true;
    modoAcceso().then(m => { if (vigente) setModoPrueba(m.acceso_prueba); }).catch(() => {});
    return () => { vigente = false; };
  }, []);

  async function entrarPrueba(evento?: FormEvent, conCorreo = true) {
    evento?.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await onIngresarPrueba(conCorreo ? correo.trim() : undefined);
    } catch (e) {
      setError(mensaje(e, 'correo'));
    } finally {
      setEnviando(false);
    }
  }

  async function solicitar(evento?: FormEvent) {
    evento?.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await pedirCodigo(correo.trim());
      setPaso('codigo');
      setCodigo('');
      setTimeout(() => codigoRef.current?.focus(), 0);
    } catch (e) {
      setError(mensaje(e, 'correo'));
    } finally {
      setEnviando(false);
    }
  }

  async function verificar(evento: FormEvent) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await onIngresar(correo.trim(), codigo.trim());
    } catch (e) {
      setError(mensaje(e, 'codigo'));
    } finally {
      setEnviando(false);
    }
  }

  if (modoPrueba) return <div className="max-w-md mx-auto">
    <Card title="Ingresa a Recursos de estudio" description="Modo de prueba: entras sin validar el correo." icon={<Mail aria-hidden="true" />}>
      <form onSubmit={entrarPrueba} className="space-y-4" noValidate>
        <Alert tone="warning">Modo de prueba: cualquiera puede entrar con cualquier correo institucional. Usa solo datos de prueba.</Alert>
        <Input label="Correo institucional" name="correo" type="email" autoComplete="email" required
          value={correo} onChange={e => setCorreo(e.target.value)} hint={DOMINIOS} />
        {error && <Alert tone="danger" role="alert">{error}</Alert>}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" loading={enviando} disabled={!correo.trim()}>Entrar</Button>
          <Button variant="secondary" onClick={() => entrarPrueba(undefined, false)} disabled={enviando}>Entrar como invitado</Button>
        </div>
      </form>
    </Card>
  </div>;

  return <div className="max-w-md mx-auto">
    <Card title="Ingresa a Recursos de estudio" description="Te enviaremos un código de acceso a tu correo institucional."
      icon={paso === 'correo' ? <Mail aria-hidden="true" /> : <KeyRound aria-hidden="true" />}>
      {paso === 'correo' ? <form onSubmit={solicitar} className="space-y-4" noValidate>
        <Input label="Correo institucional" name="correo" type="email" autoComplete="email" required
          value={correo} onChange={e => setCorreo(e.target.value)} hint={DOMINIOS} />
        {error && <Alert tone="danger" role="alert">{error}</Alert>}
        <Button type="submit" loading={enviando} disabled={!correo.trim()}>Enviar código</Button>
      </form> : <form onSubmit={verificar} className="space-y-4" noValidate>
        <Alert tone="info">Si el correo es institucional, te enviamos un código de 6 dígitos a <strong>{correo}</strong>. Vence en 10 minutos.</Alert>
        <Input ref={codigoRef} label="Código de acceso" name="codigo" inputMode="numeric" autoComplete="one-time-code"
          maxLength={6} pattern="\d{6}" required value={codigo}
          onChange={e => setCodigo(e.target.value.replace(/\D/g, ''))} />
        {error && <Alert tone="danger" role="alert">{error}</Alert>}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" loading={enviando} disabled={codigo.length !== 6}>Ingresar</Button>
          <Button variant="ghost" onClick={() => solicitar()} disabled={enviando}>Volver a pedir el código</Button>
          <Button variant="ghost" onClick={() => { setPaso('correo'); setError(''); }} disabled={enviando}>Cambiar correo</Button>
        </div>
      </form>}
    </Card>
  </div>;
}
