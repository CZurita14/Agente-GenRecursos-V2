"""Sincroniza las materias y los sílabos del docente con el SGA.

El acceso lo define el SGA: una asignatura deja de ser accesible cuando su materia ya no
aparece en la lista (`asignatura.activa_sga`), pero nunca se borra. Cada materia se
procesa en su propia transacción para que una falla no deshaga las demás. Los mensajes
y `fallos` nombran rutas de campos, nunca valores del sílabo.
"""
import time
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


def _procesar(conn, proveedor, permiso, materia, correo, servicio, pedir=True) -> MateriaEstado:
    """Importa el sílabo de una materia; devuelve su estado sin tocar `materia_sga`.

    Con `pedir` falso (presupuesto agotado) no se consulta al SGA: queda `no_disponible`
    y conserva la versión anterior, como si el SGA no hubiera respondido.
    """
    previa = conn.execute("select id,version_silabo from asignatura where dueno=%s and codigo_pf=%s",
                          (correo, materia.codigo_pf)).fetchone()
    previa_id = str(previa["id"]) if previa else None
    base = dict(id_sga=materia.id_sga, codigo_pf=materia.codigo_pf, paralelo=materia.paralelo, nombre=materia.nombre)
    if not pedir:
        return MateriaEstado(**base, estado="no_disponible", asignatura_id=previa_id)
    try:
        crudo = proveedor.obtener_silabo(permiso, materia)
    except (SGANoDisponible, SilaboNoDisponible):
        return MateriaEstado(**base, estado="no_disponible", asignatura_id=previa_id)
    try:
        silabo = cargar_silabo(a_contrato(crudo))
    except SilaboInvalido as e:
        return MateriaEstado(**base, estado="invalida", fallos=list(e.fallos), asignatura_id=previa_id)
    if silabo.proyecto_formativo.codigo != materia.codigo_pf:
        return MateriaEstado(**base, estado="invalida", asignatura_id=previa_id,
                             fallos=["proyecto_formativo.codigo: no coincide con la materia del SGA"])
    if previa and previa["version_silabo"] == silabo.proyecto_formativo.version:
        return MateriaEstado(**base, estado="sin_cambios", asignatura_id=previa_id)
    guardado = servicio.guardar(correo, silabo)
    return MateriaEstado(**base, estado="importada", asignatura_id=guardado["id"],
                         clases_cambiadas=guardado["clases_cambiadas"])


def sincronizar(conn, proveedor, identidad, permiso, servicio, *, presupuesto_s: float | None = None,
                reloj=time.monotonic) -> ResultadoSync:
    """Si el SGA no entrega la lista de materias, el error se propaga y no cambia nada.

    `identidad.correo` debe llegar ya normalizado. Con `presupuesto_s`, al agotarse el tiempo
    (medido con `reloj` desde el inicio) no se piden más sílabos: las materias restantes quedan
    `no_disponible` con su versión anterior y sus asignaturas siguen activas.
    """
    if not conn.autocommit:
        raise ValueError("sincronizar requiere una conexión en autocommit (una transacción por materia)")
    inicio = reloj()
    correo = identidad.correo
    lista = proveedor.listar_materias(permiso)
    resultado = []
    for materia in lista:
        pedir = presupuesto_s is None or reloj() - inicio < presupuesto_s
        estado = _procesar(conn, proveedor, permiso, materia, correo, servicio, pedir)
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
        conn.execute("set local lock_timeout to '2s'")
        codigos = [m.codigo_pf for m in lista]
        conn.execute("update asignatura set activa_sga = (codigo_pf = any(%s)) "
                     "where dueno=%s and activa_sga is distinct from (codigo_pf = any(%s))",
                     (codigos, correo, codigos))
    return ResultadoSync(resultado)
