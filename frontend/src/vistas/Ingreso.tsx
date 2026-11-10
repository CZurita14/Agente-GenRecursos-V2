import { useEffect, useState, type FormEvent } from 'react';
import { KeyRound, Mail } from 'lucide-react';
import { Alert, Button, Card, Input } from '../components';
import { ErrorApi, modoAcceso } from '../api/cliente';
import { mensajeIngreso } from '../utils/materias';

interface IngresoProps {
  onIngresar: (usuario: string, clave: string) => Promise<void>;
  onIngresarPrueba: (correo?: string) => Promise<void>;
}

const DOMINIOS = 'Usa tu correo @uti.edu.ec o @indoamerica.edu.ec.';

const mensaje = (e: unknown) => e instanceof ErrorApi ? mensajeIngreso(e.estado, e.reintentar) : mensajeIngreso(undefined);

/** Ingreso con el usuario y la clave del SGA. La clave vive solo en este estado y se borra al responder el servidor. */
export function Ingreso({ onIngresar, onIngresarPrueba }: IngresoProps) {
  const [usuario, setUsuario] = useState('');
  const [clave, setClave] = useState('');
  const [correo, setCorreo] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [modoPrueba, setModoPrueba] = useState(false);

  // Si la consulta falla se muestra el ingreso normal con el SGA.
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
      setError(e instanceof ErrorApi && e.estado === 403 ? `Ese correo no está permitido. ${DOMINIOS}` : mensaje(e));
    } finally {
      setEnviando(false);
    }
  }

  async function entrar(evento: FormEvent) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await onIngresar(usuario.trim(), clave);
    } catch (e) {
      setError(mensaje(e));
    } finally {
      setClave(''); // La clave no se conserva después de la respuesta, sea cual sea.
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
    <Card title="Ingresa a Recursos de estudio" description="Usa el mismo usuario y clave que en el SGA."
      icon={<KeyRound aria-hidden="true" />}>
      <form onSubmit={entrar} className="space-y-4" noValidate>
        <Input label="Usuario del SGA" name="usuario" type="text" autoComplete="username" required
          autoCapitalize="none" spellCheck={false} value={usuario} onChange={e => setUsuario(e.target.value)} />
        <Input label="Clave del SGA" name="clave" type="password" autoComplete="current-password" required
          value={clave} onChange={e => setClave(e.target.value)}
          hint="Tu clave solo se usa para entrar; no se guarda." />
        {error && <Alert tone="danger" role="alert">{error}</Alert>}
        <Button type="submit" loading={enviando} disabled={!usuario.trim() || !clave}>Ingresar</Button>
      </form>
    </Card>
  </div>;
}
