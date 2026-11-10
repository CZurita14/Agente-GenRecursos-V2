"""Permisos por UUID de asignatura, comprobados dentro de la transacción."""
from contextlib import closing

from fastapi import HTTPException

from app.agentes.orquestador import crear_asignatura
from app.silabo.menu import clases_cambiadas, construir_menu
from app.silabo.modelo import SilaboUTI


def exigir_acceso(conn, aid, correo, *, editar=False):
    """Requiere transacción externa; retiene a la asignatura hasta terminar la operación.

    Una asignatura cuya materia el SGA ya no lista (`activa_sga` falso) se trata como inexistente.
    """
    fila = conn.execute("select * from asignatura where id=%s for share", (aid,)).fetchone()
    if fila is None or not fila["activa_sga"]:
        raise HTTPException(404, "Proyecto Formativo inexistente")
    # Nueva sentencia, nueva instantánea READ COMMITTED DESPUÉS de obtener el lock.
    # Un JOIN en la sentencia anterior podía conservar un permiso ya revocado.
    permiso = conn.execute("select rol from asignatura_acceso where asignatura_id=%s and correo=%s",
                           (aid, correo)).fetchone()
    rol = "dueno" if fila["dueno"] == correo else (permiso["rol"] if permiso else None)
    if rol is None or (editar and rol == "lector"):
        raise HTTPException(403, "Sin permiso sobre el Proyecto Formativo")
    return fila, rol


def _menu(silabo):
    return [s.model_dump(mode="json") for s in construir_menu(silabo)]


class ServicioAsignaturas:
    def __init__(self, conexion, catalogo, perfiles):
        self.conexion, self.catalogo, self.perfiles = conexion, catalogo, perfiles

    def guardar(self, correo, silabo):
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            with conn.transaction():
                conn.execute("set local lock_timeout to '2s'")
                # FOR UPDATE no puede bloquear una fila que aún no existe.
                clave = f"{len(correo)}:{correo}{silabo.proyecto_formativo.codigo}"
                conn.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))", (clave,))
                anterior = conn.execute("select silabo from asignatura where dueno=%s and codigo_pf=%s for update",
                                        (correo, silabo.proyecto_formativo.codigo)).fetchone()
                aid = crear_asignatura(conn, dueno=correo, silabo=silabo,
                                       catalogo=self.catalogo, perfiles=self.perfiles)
                cambios = (clases_cambiadas(SilaboUTI.model_validate(anterior["silabo"]), silabo)
                           if anterior else {s.id for m in silabo.momentos for s in m.sesiones})
                fila = conn.execute("select agente from asignatura where id=%s", (aid,)).fetchone()
                return {"id": str(aid), "agente": fila["agente"], "menu": _menu(silabo),
                        "clases_cambiadas": sorted(cambios)}

    def materias(self, correo):
        """Las materias que el SGA lista al docente y el resultado de importar cada sílabo."""
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            filas = conn.execute(
                "select id_sga,codigo_pf,paralelo,nombre,carrera,estado_sga,estado,asignatura_id "
                "from materia_sga where correo=%s order by codigo_pf,paralelo,id_sga", (correo,)).fetchall()
        return [{**f, "asignatura_id": str(f["asignatura_id"]) if f["asignatura_id"] else None} for f in filas]

    def listar(self, correo):
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            filas = conn.execute(
                "select a.id,a.dueno,a.codigo_pf,a.version_silabo,a.agente,"
                "a.silabo#>>'{proyecto_formativo,nombre}' nombre,"
                "case when a.dueno=%s then 'dueno' else p.rol end rol "
                "from asignatura a left join asignatura_acceso p on p.asignatura_id=a.id and p.correo=%s "
                "where (a.dueno=%s or p.correo=%s) and a.activa_sga order by a.creado,a.id",
                (correo, correo, correo, correo)).fetchall()
            return filas

    def menu(self, aid, correo):
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            with conn.transaction():
                conn.execute("set local lock_timeout to '2s'")
                fila, rol = exigir_acceso(conn, aid, correo)
                silabo = SilaboUTI.model_validate(fila["silabo"])
                return {"id": str(aid), "rol": rol, "version_silabo": fila["version_silabo"], "menu": _menu(silabo)}
