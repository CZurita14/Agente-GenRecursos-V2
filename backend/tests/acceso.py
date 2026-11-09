"""Ayuda de pruebas: da o quita un rol en `asignatura_acceso` sin pasar por la API (ya no hay «compartir»)."""


def dar_acceso(conn, aid, correo, rol):
    conn.execute("insert into asignatura_acceso (asignatura_id,correo,rol) values (%s,%s,%s) "
                 "on conflict (asignatura_id,correo) do update set rol=excluded.rol", (aid, correo, rol))


def quitar_acceso(conn, aid, correo):
    conn.execute("delete from asignatura_acceso where asignatura_id=%s and correo=%s", (aid, correo))
