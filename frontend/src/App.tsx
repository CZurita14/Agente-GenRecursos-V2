import { useState } from 'react';
import { BookOpen, FolderOpen, Home, LogOut } from 'lucide-react';
import { AppLayout } from './components';
import type { Ambito, Rol, TrabajoCreado } from './api/tipos';
import { useSesion } from './sesion/useSesion';
import { Actividad } from './vistas/Actividad';
import { Asignatura } from './vistas/Asignatura';
import { Asignaturas } from './vistas/Asignaturas';
import { Generar } from './vistas/Generar';
import { Ingreso } from './vistas/Ingreso';
import { Inicio } from './vistas/Inicio';
import { Progreso } from './vistas/Progreso';
import { Recurso } from './vistas/Recurso';
import { Recursos } from './vistas/Recursos';

interface Curso { aid: string; nombre: string; rol: Rol }

/** Ruta de la aplicación (sin router: la plantilla no trae uno). */
type Ruta =
  | { vista: 'inicio' } | { vista: 'generar' } | { vista: 'asignaturas' }
  | { vista: 'recursos'; aid?: string }
  | { vista: 'asignatura'; curso: Curso }
  | { vista: 'actividad'; curso: Curso; ambito: Ambito; titulo: string }
  | { vista: 'progreso'; curso: Curso; creados: TrabajoCreado[] }
  | { vista: 'recurso'; curso: Pick<Curso, 'aid' | 'rol'> & { nombre?: string }; rid: string; volver: Ruta };

const MENU = [
  { id: 'inicio', label: 'Inicio', icon: <Home aria-hidden="true" className="w-4 h-4" /> },
  { id: 'asignaturas', label: 'Proyecto Formativo', icon: <BookOpen aria-hidden="true" className="w-4 h-4" /> },
  { id: 'recursos', label: 'Mis recursos', icon: <FolderOpen aria-hidden="true" className="w-4 h-4" /> },
];

const pestana = (r: Ruta) => r.vista === 'inicio' || r.vista === 'generar' ? 'inicio'
  : r.vista === 'recursos' || r.vista === 'recurso' ? 'recursos' : 'asignaturas';

/** Sin sesión: ingreso. Con sesión: menú principal (opción B) y el recorrido de recursos (P6b). */
export default function App() {
  const { usuario, cargando, ingresar, ingresarPrueba, salir, expirar } = useSesion();
  const [ruta, setRuta] = useState<Ruta>({ vista: 'inicio' });

  if (cargando) {
    return <AppLayout><p className="text-muted" role="status">Cargando…</p></AppLayout>;
  }
  if (!usuario) {
    return <AppLayout><Ingreso onIngresar={async (usuario, clave) => { await ingresar(usuario, clave); setRuta({ vista: 'inicio' }); }}
      onIngresarPrueba={async correo => { await ingresarPrueba(correo); setRuta({ vista: 'inicio' }); }} /></AppLayout>;
  }

  const acciones = <div className="flex items-center gap-3 text-sm">
    <span className="text-header-muted hidden sm:inline" title="Sesión iniciada">{usuario.correo}</span>
    <button type="button" onClick={salir}
      className="flex items-center gap-1 px-3 py-2 rounded-lg text-header-muted hover:bg-header-border hover:text-white">
      <LogOut aria-hidden="true" className="w-4 h-4" /><span>Salir</span>
    </button>
  </div>;

  const aMenu = (curso: Curso) => setRuta({ vista: 'asignatura', curso });

  return <AppLayout items={MENU} activeId={pestana(ruta)} onChange={id => setRuta({ vista: id } as Ruta)} actions={acciones}>
    {ruta.vista === 'inicio' && <Inicio onGenerar={() => setRuta({ vista: 'generar' })} />}
    {ruta.vista === 'generar' && <Generar onSesionVencida={expirar}
      onAbrir={m => aMenu({ aid: m.asignatura_id, nombre: m.nombre, rol: 'dueno' })} />}
    {ruta.vista === 'asignaturas' && <Asignaturas onSesionVencida={expirar} onSubir={() => setRuta({ vista: 'generar' })}
      onAbrir={a => aMenu({ aid: a.id, nombre: a.nombre, rol: a.rol })} />}
    {ruta.vista === 'asignatura' && <Asignatura aid={ruta.curso.aid} nombre={ruta.curso.nombre} onSesionVencida={expirar}
      onElegir={(ambito, titulo) => setRuta({ vista: 'actividad', curso: ruta.curso, ambito, titulo })}
      onVerRecursos={() => setRuta({ vista: 'recursos', aid: ruta.curso.aid })} />}
    {ruta.vista === 'actividad' && <Actividad aid={ruta.curso.aid} ambito={ruta.ambito} titulo={ruta.titulo}
      onSesionVencida={expirar} onVolver={() => aMenu(ruta.curso)}
      onGenerado={creados => setRuta({ vista: 'progreso', curso: ruta.curso, creados })} />}
    {ruta.vista === 'progreso' && <Progreso aid={ruta.curso.aid} creados={ruta.creados} onSesionVencida={expirar}
      onVolver={() => aMenu(ruta.curso)}
      onAbrir={rid => setRuta({ vista: 'recurso', curso: ruta.curso, rid, volver: ruta })} />}
    {ruta.vista === 'recursos' && <Recursos aidInicial={ruta.aid} onSesionVencida={expirar}
      onTrabajos={(aid, ids, rol) => setRuta({ vista: 'progreso', curso: { aid, rol, nombre: 'Asignatura' },
        creados: ids.map(id => ({ id, herramienta: 'recurso', estado: 'en_cola' })) })}
      onAbrir={(aid, rid, rol) => setRuta({ vista: 'recurso', curso: { aid, rol }, rid, volver: { vista: 'recursos', aid } })} />}
    {ruta.vista === 'recurso' && <Recurso key={`${ruta.curso.aid}:${ruta.rid}`} aid={ruta.curso.aid} rid={ruta.rid} puedeValidar={ruta.curso.rol !== 'lector'}
      onTrabajos={ids => setRuta({ vista: 'progreso', curso: { ...ruta.curso, nombre: ruta.curso.nombre ?? 'Proyecto Formativo' },
        creados: ids.map(id => ({ id, herramienta: 'recurso', estado: 'en_cola' })) })}
      onSesionVencida={expirar} onVolver={() => setRuta(ruta.volver)} />}
  </AppLayout>;
}
