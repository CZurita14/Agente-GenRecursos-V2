"""La limpieza elimina solo seguridad vencida y no las asignaturas."""
import pytest
from psycopg.types.json import Jsonb

from app.control.mantenimiento import limpiar


def test_limpieza_preserva_registros_activos_y_academicos(conn, silabo):
    conn.execute("insert into control_limite values ('viejo',%s,now(),1,now()-interval '1 minute'),"
                 "('activo',%s,now(),1,now()+interval '1 minute')", ("a" * 64, "b" * 64))
    conn.execute("insert into acceso_api (operacion,metodo,estado,duracion_ms,ip_hash,creado) "
                 "values ('auth.yo','GET',200,1,%s,now()-interval '31 days'),"
                 "('auth.yo','GET',200,1,%s,now())", ("a" * 64, "b" * 64))
    conn.execute("insert into auth_sesion values (%s,'viejo@uti.edu.ec',now()-interval '2 days',"
                 "now()-interval '9 hours',now()+interval '1 day'),"
                 "(%s,'activo@uti.edu.ec',now(),now(),now()+interval '7 days')", ("a" * 64, "b" * 64))
    conn.execute("insert into auth_reto (correo,emitido,vence,bloqueado_hasta) values "
                 "('viejo@uti.edu.ec',now()-interval '2 days',now()-interval '1 day',null),"
                 "('bloqueado@uti.edu.ec',now()-interval '2 days',now()-interval '1 day',now()+interval '15 minutes')")
    conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                 "values ('dueno@uti.edu.ec','PF','1','ingenierias',%s)", (Jsonb(silabo.model_dump(mode="json")),))
    resultado = limpiar(conn)
    assert resultado == {"cuotas": 1, "accesos": 1, "sesiones": 1, "retos": 1}
    assert conn.execute("select count(*) n from asignatura").fetchone()["n"] == 1
    assert conn.execute("select correo from auth_reto").fetchone()["correo"] == "bloqueado@uti.edu.ec"
    assert limpiar(conn) == {"cuotas": 0, "accesos": 0, "sesiones": 0, "retos": 0}


@pytest.mark.parametrize("dias", [0, -1, 366, True, 1.5])
def test_retencion_invalida_no_abre_transaccion(dias):
    with pytest.raises(ValueError):
        limpiar(None, dias)
