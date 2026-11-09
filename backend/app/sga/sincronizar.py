"""Sincroniza las materias y los sílabos del docente con el SGA.

El acceso lo define el SGA: una asignatura deja de ser accesible cuando su materia ya no
aparece en la lista (`asignatura.activa_sga`), pero nunca se borra. Cada materia se
procesa en su propia transacción para que una falla no deshaga las demás. Los mensajes
y `fallos` nombran rutas de campos, nunca valores del sílabo.
"""
from dataclasses import dataclass, field

from psycopg.types.json import Jsonb

from app.sga.proveedor import SGANoDisponible, SilaboNoDisponible
from app.sga.traductor import a_contrato
from app.silabo.integridad import SilaboInvalido, cargar_silabo


@dataclass(frozen=True)
class MateriaEstado:
    id_sga: str
    codigo_pf: str
    paralelo: str
    nombre: str
    estado: str  # importada | sin_cambios | no_disponible | invalida
    fallos: list[str] = field(default_factory=list)
    asignatura_id: str | None = None
    clases_cambiadas: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResultadoSync:
    materias: list[MateriaEstado]


def _procesar(conn, proveedor, permiso, materia, correo, servicio) -> MateriaEstado:
    """Importa el sílabo de una materia; devuelve su estado sin tocar `materia_sga`."""
    previa = conn.execute("select id,version_silabo from asignatura where dueno=%s and codigo_pf=%s",
                          (correo, materia.codigo_pf)).fetchone()
    previa_id = str(previa["id"]) if previa else None
    base = dict(id_sga=materia.id_sga, codigo_pf=materia.codigo_pf, paralelo=materia.paralelo, nombre=materia.nombre)
    try:
        crudo = proveedor.obtener_silabo(permiso, materia)
    except (SGANoDisponible, SilaboNoDisponible):
        return MateriaEstado(**base, estado="no_disponible", asignatura_id=previa_id)
    try:
        silabo = cargar_silabo(a_contrato(crudo))
    except SilaboInvalido as e:
        return MateriaEstado(**base, estado="invalida", fallos=list(e.fallos), asignatura_id=previa_id)
    if previa and previa["version_silabo"] == silabo.proyecto_formativo.version:
        return MateriaEstado(**base, estado="sin_cambios", asignatura_id=previa_id)
    guardado = servicio.guardar(correo, silabo)
    return MateriaEstado(**base, estado="importada", asignatura_id=guardado["id"],
                         clases_cambiadas=guardado["clases_cambiadas"])


def sincronizar(conn, proveedor, identidad, permiso, servicio) -> ResultadoSync:
    """Si el SGA no entrega la lista de materias, el error se propaga y no cambia nada."""
    correo = identidad.correo
    lista = proveedor.listar_materias(permiso)
    resultado = []
    for materia in lista:
        estado = _procesar(conn, proveedor, permiso, materia, correo, servicio)
        with conn.transaction():
            conn.execute(
                "insert into materia_sga (correo,id_sga,codigo_pf,paralelo,nombre,carrera,estado_sga,"
                "estado,fallos,asignatura_id,sincronizada) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()) "
                "on conflict (correo,id_sga) do update set codigo_pf=excluded.codigo_pf,"
                "paralelo=excluded.paralelo,nombre=excluded.nombre,carrera=excluded.carrera,"
                "estado_sga=excluded.estado_sga,estado=excluded.estado,fallos=excluded.fallos,"
                "asignatura_id=excluded.asignatura_id,sincronizada=excluded.sincronizada",
                (correo, materia.id_sga, materia.codigo_pf, materia.paralelo, materia.nombre,
                 materia.carrera, materia.estado, estado.estado, Jsonb(estado.fallos), estado.asignatura_id))
        resultado.append(estado)
    with conn.transaction():
        conn.execute("delete from materia_sga where correo=%s and not (id_sga = any(%s))",
                     (correo, [m.id_sga for m in lista]))
        codigos = [m.codigo_pf for m in lista]
        conn.execute("update asignatura set activa_sga = (codigo_pf = any(%s)) "
                     "where dueno=%s and activa_sga is distinct from (codigo_pf = any(%s))",
                     (codigos, correo, codigos))
    return ResultadoSync(resultado)
