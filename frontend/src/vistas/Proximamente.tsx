import { Construction } from 'lucide-react';
import { Card } from '../components';

interface ProximamenteProps {
  titulo: string;
  descripcion: string;
}

/** Vista de una sección que llega en la siguiente entrega del P6. */
export function Proximamente({ titulo, descripcion }: ProximamenteProps) {
  return <>
    <h1 className="text-2xl font-bold">{titulo}</h1>
    <Card title="Próximamente" icon={<Construction aria-hidden="true" />}>
      <p className="text-sm text-muted">{descripcion}</p>
    </Card>
  </>;
}
