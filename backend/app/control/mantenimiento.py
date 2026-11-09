"""Limpieza explícita de datos de seguridad vencidos; no borra recursos académicos."""
from app.config import ajustes
from app.db.conexion import conectar


def limpiar(conn, dias=30):
    if type(dias) is not int or not 1 <= dias <= 365:
        raise ValueError("Retención inválida")
    with conn.transaction():
        conn.execute("set local lock_timeout to '2s'")
        conn.execute("set local statement_timeout to '10s'")
        cuotas = conn.execute("delete from control_limite where vence<clock_timestamp()").rowcount
        accesos = conn.execute("delete from acceso_api where creado<clock_timestamp()-make_interval(days=>%s)", (dias,)).rowcount
        sesiones = conn.execute("delete from auth_sesion where vence<=clock_timestamp() "
                                "or actividad<=clock_timestamp()-interval '8 hours'").rowcount
        retos = conn.execute("delete from auth_reto where emitido<clock_timestamp()-interval '1 day' "
                             "and coalesce(vence,'-infinity')<clock_timestamp() "
                             "and coalesce(bloqueado_hasta,'-infinity')<clock_timestamp()").rowcount
    return {"cuotas": cuotas, "accesos": accesos, "sesiones": sesiones, "retos": retos}


def main():
    with conectar() as conn:
        conn.autocommit = True
        print(limpiar(conn, ajustes().auditoria_retencion_dias))


if __name__ == "__main__":
    main()
