import { ClipboardList, Hourglass, Sparkles } from 'lucide-react';
import { Badge, Button } from '../components';

interface InicioProps {
  onGenerar: () => void;
}

const PASOS = ['Elige tu materia', 'Elige la clase', 'Genera y revisa'];

/** Opción B aprobada: dos caminos lado a lado; el perfil docente se ve, pero está en espera. */
export function Inicio({ onGenerar }: InicioProps) {
  return <>
    <div>
      <h1 className="text-2xl font-bold">¿Qué quieres hacer hoy?</h1>
      <p className="text-muted mt-1">La colmena trabaja con tu sílabo: no inventa contenido.</p>
    </div>
    <div className="grid gap-6 md:grid-cols-2">
      <section aria-labelledby="camino-generar"
        className="bg-surface rounded-xl border-2 border-highlight p-6 shadow-sm flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <span className="p-2 rounded-lg bg-highlight-soft text-action-ink"><Sparkles aria-hidden="true" /></span>
          <h2 id="camino-generar" className="text-lg font-bold">Generar herramientas</h2>
        </div>
        <p className="text-muted text-sm">
          Elige una materia de tu SGA. La colmena lee su sílabo y prepara fichas, cuestionarios, guías, rúbricas y
          autoevaluaciones por clase y para todo el Proyecto Formativo.
        </p>
        <ol className="flex flex-wrap gap-2 text-xs" aria-label="Pasos">
          {PASOS.map((paso, i) => <li key={paso} className="bg-brand-soft text-brand rounded-full px-3 py-1 font-medium">
            {i + 1} · {paso}
          </li>)}
        </ol>
        <div><Button onClick={onGenerar}>Empezar</Button></div>
      </section>

      <section aria-labelledby="camino-perfil" aria-disabled="true"
        className="bg-surface rounded-xl border-2 border-dashed border-line p-6 flex flex-col gap-4 opacity-70">
        <div className="flex flex-wrap items-center gap-3">
          <span className="p-2 rounded-lg bg-app-soft text-muted"><ClipboardList aria-hidden="true" /></span>
          <h2 id="camino-perfil" className="text-lg font-bold">Perfil docente</h2>
          <Badge tone="warning" icon={<Hourglass aria-hidden="true" className="w-3 h-3" />}>En espera</Badge>
        </div>
        <p className="text-muted text-sm">
          Planificación del docente y su parametrización. Se activará cuando llegue la documentación
          institucional.
        </p>
      </section>
    </div>
  </>;
}
