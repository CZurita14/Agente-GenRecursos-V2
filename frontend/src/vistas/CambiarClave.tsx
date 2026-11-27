import { useState, type FormEvent } from 'react';
import { KeyRound } from 'lucide-react';
import { Alert, Button, Card, Input } from '../components';
import { cambiarClave, ErrorApi } from '../api/cliente';

interface CambiarClaveProps {
  /** Primer ingreso con la clave inicial: no se puede seguir sin cambiarla. */
  obligatorio?: boolean;
  onListo: () => void;
  onSalir?: () => void;
  onSesionVencida: () => void;
}

const MIN = 10;

/** Cuenta local (etapa de pruebas): el docente reemplaza la clave que le dio el administrador. */
export function CambiarClave({ obligatorio = false, onListo, onSalir, onSesionVencida }: CambiarClaveProps) {
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [repetida, setRepetida] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  const problema = nueva && nueva.length < MIN ? `Usa al menos ${MIN} caracteres.`
    : repetida && repetida !== nueva ? 'Las claves nuevas no coinciden.' : '';

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (problema) return;
    setError('');
    setEnviando(true);
    try {
      await cambiarClave(actual, nueva);
      onListo();
    } catch (e) {
      if (e instanceof ErrorApi && e.estado === 401) return onSesionVencida();
      setError(e instanceof ErrorApi ? e.message : 'No hay conexión con el servidor. Inténtalo de nuevo.');
    } finally {
      setActual(''); setNueva(''); setRepetida('');
      setEnviando(false);
    }
  }

  return <div className="max-w-md mx-auto">
    <Card title="Cambia tu clave" icon={<KeyRound aria-hidden="true" />}
      description={obligatorio ? 'Es tu primer ingreso: reemplaza la clave que te dio el administrador.' : 'Elige una clave nueva para tu cuenta.'}>
      <form onSubmit={enviar} className="space-y-4" noValidate>
        <Input label={obligatorio ? 'Clave inicial' : 'Clave actual'} type="password" autoComplete="current-password" required
          value={actual} onChange={e => setActual(e.target.value)} />
        <Input label="Clave nueva" type="password" autoComplete="new-password" required minLength={MIN}
          value={nueva} onChange={e => setNueva(e.target.value)} hint={`Al menos ${MIN} caracteres.`} />
        <Input label="Repite la clave nueva" type="password" autoComplete="new-password" required
          value={repetida} onChange={e => setRepetida(e.target.value)} error={problema || undefined} />
        {error && <Alert tone="danger" role="alert">{error}</Alert>}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" loading={enviando} disabled={!actual || !nueva || !repetida || !!problema}>Guardar clave</Button>
          {onSalir && <Button variant="secondary" onClick={onSalir} disabled={enviando}>{obligatorio ? 'Salir' : 'Cancelar'}</Button>}
        </div>
      </form>
    </Card>
  </div>;
}
