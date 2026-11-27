import { useRef, useState } from 'react';
import { BookOpen, FolderOpen, Home, KeyRound, LogOut, Users } from 'lucide-react';
import { AppLayout } from './components';
import { PanelConsumo } from './components/PanelConsumo';
import type { Ambito, Rol, TrabajoCreado } from './api/tipos';
import { useSesion } from './sesion/useSesion';
import { Actividad } from './vistas/Actividad';
import { Asignaturas } from './vistas/Asignaturas';
import { CambiarClave } from './vistas/CambiarClave';
import { Cuentas } from './vistas/Cuentas';
import { Generar } from './vistas/Generar';
import { Ingreso } from './vistas/Ingreso';
import { Inicio } from './vistas/Inicio';
import { Momentos } from './vistas/Momentos';
import { Progreso } from './vistas/Progreso';
import { Recurso } from './vistas/Recurso';
import { Recursos } from './vistas/Recursos';

interface Curso { aid: string; nombre: string; rol: Rol }

/** Ruta de la aplicación (sin router: la plantilla no trae uno). */
type Ruta =
  | { vista: 'inicio' } | { vista: 'generar' } | { vista: 'asignaturas' } | { vista: 'cuentas' } | { vista: 'clave' }
  | { vista: 'recursos'; aid?: string }
  | { vista: 'momentos'; curso: Curso }
  | { vista: 'actividad'; curso: Curso; ambito: Ambito; titulo: string }
  | { vista: 'progreso'; curso: Curso; creados: TrabajoCreado[] }
  | { vista: 'recurso'; curso: Pick<Curso, 'aid' | 'rol'> & { nombre?: string }; rid: string; volver: Ruta };

const MENU = [
  { id: 'inicio', label: 'Inicio', icon: <Home aria-hidden="true" className="w-4 h-4" /> },
  { id: 'asignaturas', label: 'Proyecto Formativo', icon: <BookOpen aria-hidden="true" className="w-4 h-4" /> },
  { id: 'recursos', label: 'Mis recursos', icon: <FolderOpen aria-hidden="true" className="w-4 h-4" /> },
];

const MENU_CUENTAS = { id: 'cuentas', label: 'Cuentas de prueba', icon: <Users aria-hidden="true" className="w-4 h-4" /> };

const pestana = (r: Ruta) => r.vista === 'cuentas' ? 'cuentas' : r.vista === 'clave' ? 'inicio'
  : r.vista === 'inicio' || r.vista === 'generar' ? 'inicio'
  : r.vista === 'recursos' || r.vista === 'recurso' ? 'recursos' : 'asignaturas';

/** Sin sesión: ingreso. Con sesión: menú principal (opción B) y el recorrido de recursos (P6b). */
export default function App() {
  const { usuario, cargando, ingresar, ingresarPrueba, salir, expirar, refrescar } = useSesion();
  const [ruta, setRuta] = useState<Ruta>({ vista: 'inicio' });
  // Último momento abierto en cada Proyecto Formativo: al volver de una clase o de un recurso se abre el mismo.
  const momentoAbierto = useRef<Record<string, number>>({});

  if (cargando) {
    return <AppLayout><p className="text-muted" role="status">Cargando…</p></AppLayout>;
  }
  if (!usuario) {
    return <AppLayout><Ingreso onIngresar={async (usuario, clave) => { await ingresar(usuario, clave); setRuta({ vista: 'inicio' }); }}
      onIngresarPrueba={async correo => { await ingresarPrueba(correo); setRuta({ vista: 'inicio' }); }} /></AppLayout>;
  }

  if (usuario.cambiar_clave) {
    // Cuenta local con la clave inicial del administrador: no se sigue sin cambiarla.
    return <AppLayout><CambiarClave obligatorio onListo={() => { void refrescar(); setRuta({ vista: 'inicio' }); }}
      onSalir={salir} onSesionVencida={expirar} /></AppLayout>;
  }

  const adminCuentas = usuario.rol === 'administrador' && !!usuario.cuentas_locales;
  const menu = adminCuentas ? [...MENU, MENU_CUENTAS] : MENU;

  const acciones = <div className="flex items-center gap-3 text-sm">
    <span className="text-header-muted hidden sm:inline" title="Sesión iniciada">{usuario.correo}</span>
    {usuario.cuenta_local && <button type="button" onClick={() => setRuta({ vista: 'clave' })}
      className="flex items-center gap-1 px-3 py-2 rounded-lg text-header-muted hover:bg-header-border hover:text-white">
      <KeyRound aria-hidden="true" className="w-4 h-4" /><span className="hidden sm:inline">Clave</span>
    </button>}
    <button type="button" onClick={salir}
      className="flex items-center gap-1 px-3 py-2 rounded-lg text-header-muted hover:bg-header-border hover:text-white">
      <LogOut aria-hidden="true" className="w-4 h-4" /><span>Salir</span>
    </button>
  </div>;

  // La pantalla principal de cada Proyecto Formativo son sus momentos (con sus clases dentro).
  const aMenu = (curso: Curso) => setRuta({ vista: 'momentos', curso });
  // El panel de consumo muestra el proyecto formativo abierto; fuera de uno, todos los de la cuenta.
  const aidAbierto = 'curso' in ruta ? ruta.curso.aid : ruta.vista === 'recursos' ? ruta.aid : undefined;

  return <AppLayout items={menu} activeId={pestana(ruta)} onChange={id => setRuta({ vista: id } as Ruta)} actions={acciones}
    amplio={ruta.vista === 'momentos'}>
    {ruta.vista === 'inicio' && <Inicio onGenerar={() => setRuta({ vista: 'generar' })} />}
    {ruta.vista === 'cuentas' && adminCuentas && <Cuentas onSesionVencida={expirar} />}
    {ruta.vista === 'clave' && <CambiarClave onListo={() => setRuta({ vista: 'inicio' })}
      onSalir={() => setRuta({ vista: 'inicio' })} onSesionVencida={expirar} />}
    {ruta.vista === 'generar' && <Generar cuentaLocal={!!usuario.cuenta_local} onSesionVencida={expirar}
      onAbrir={m => aMenu({ aid: m.asignatura_id, nombre: m.nombre, rol: 'dueno' })} />}
    {ruta.vista === 'asignaturas' && <Asignaturas onSesionVencida={expirar} onGenerar={() => setRuta({ vista: 'generar' })}
      onAbrir={a => aMenu({ aid: a.id, nombre: a.nombre, rol: a.rol })} />}
    {ruta.vista === 'momentos' && <Momentos key={ruta.curso.aid} aid={ruta.curso.aid} nombre={ruta.curso.nombre}
      onSesionVencida={expirar} onVolver={() => setRuta({ vista: 'asignaturas' })}
      momentoInicial={momentoAbierto.current[ruta.curso.aid]}
      onMomento={n => { momentoAbierto.current[ruta.curso.aid] = n; }}
      onVerRecursos={() => setRuta({ vista: 'recursos', aid: ruta.curso.aid })}
      onElegir={(ambito, titulo) => setRuta({ vista: 'actividad', curso: ruta.curso, ambito, titulo })}
      onAbrir={rid => setRuta({ vista: 'recurso', curso: ruta.curso, rid, volver: ruta })}
      onGenerado={creados => setRuta({ vista: 'progreso', curso: ruta.curso, creados })} />}
    {ruta.vista === 'actividad' && <Actividad aid={ruta.curso.aid} ambito={ruta.ambito} titulo={ruta.titulo}
      onSesionVencida={expirar} onVolver={() => aMenu(ruta.curso)}
      onGenerado={creados => setRuta({ vista: 'progreso', curso: ruta.curso, creados })} />}
    {ruta.vista === 'progreso' && <Progreso aid={ruta.curso.aid} creados={ruta.creados} onSesionVencida={expirar}
      onVolver={() => aMenu(ruta.curso)}
      onAbrir={rid => setRuta({ vista: 'recurso', curso: ruta.curso, rid, volver: ruta })} />}
    {ruta.vista === 'recursos' && <Recursos aidInicial={ruta.aid} onSesionVencida={expirar}
      onTrabajos={(aid, ids, rol, nombre) => setRuta({ vista: 'progreso', curso: { aid, rol, nombre },
        creados: ids.map(id => ({ id, herramienta: 'recurso', estado: 'en_cola' })) })}
      onAbrir={(aid, rid, rol) => setRuta({ vista: 'recurso', curso: { aid, rol }, rid, volver: { vista: 'recursos', aid } })} />}
    {ruta.vista === 'recurso' && <Recurso key={`${ruta.curso.aid}:${ruta.rid}`} aid={ruta.curso.aid} rid={ruta.rid} puedeValidar={ruta.curso.rol !== 'lector'}
      onTrabajos={ids => setRuta({ vista: 'progreso', curso: { ...ruta.curso, nombre: ruta.curso.nombre ?? 'Proyecto Formativo' },
        creados: ids.map(id => ({ id, herramienta: 'recurso', estado: 'en_cola' })) })}
      onSesionVencida={expirar} onVolver={() => setRuta(ruta.volver)} />}
    <PanelConsumo aid={aidAbierto} onSesionVencida={expirar} />
  </AppLayout>;
}
