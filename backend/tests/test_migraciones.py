def test_crea_tablas(conn):
    filas = conn.execute(
        "select table_name from information_schema.tables where table_schema = current_schema()"
    ).fetchall()
    nombres = {f["table_name"] for f in filas}
    assert {"facultad", "carrera", "asignatura", "trabajo", "mensaje",
            "llamada_llm", "recurso", "migracion", "materia_sga"} <= nombres


def test_idempotente(conn):
    from app.db.migrar import aplicar_migraciones
    assert aplicar_migraciones(conn) == []


def test_011_cierra_sesiones_y_accesos_compartidos_de_v1(monkeypatch, tmp_path):
    """Tras actualizar a V2 se entra solo por el SGA y el acceso lo define solo el SGA."""
    import shutil
    import uuid

    from app.db import migrar
    from app.db.conexion import conectar

    previas = tmp_path / "previas"
    previas.mkdir()
    for ruta in migrar.DIR.glob("*.sql"):
        if ruta.name < "011":
            shutil.copy(ruta, previas / ruta.name)
    esquema = f"prueba_{uuid.uuid4().hex[:8]}"
    c = conectar()
    try:
        c.autocommit = True
        c.execute(f"create schema {esquema}")
        c.execute(f"set search_path to {esquema}")
        monkeypatch.setattr(migrar, "DIR", previas)
        migrar.aplicar_migraciones(c)
        c.execute("insert into auth_sesion (token_hash,correo,creada,actividad,vence) "
                  "values ('h','a@uti.edu.ec',now(),now(),now()+interval '1 day')")
        aid = c.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                        "values ('a@uti.edu.ec','X','1','general','{}') returning id").fetchone()["id"]
        c.execute("insert into asignatura_acceso (asignatura_id,correo,rol) values (%s,'b@uti.edu.ec','editor')",
                  (aid,))
        monkeypatch.setattr(migrar, "DIR", migrar.Path(migrar.__file__).parent / "migraciones")
        assert migrar.aplicar_migraciones(c)[0] == "011_acceso_solo_sga.sql"
        assert c.execute("select count(*) n from auth_sesion").fetchone()["n"] == 0
        assert c.execute("select count(*) n from asignatura_acceso").fetchone()["n"] == 0
        # La tabla y los roles se conservan para accesos que escriba un administrador en la base.
        assert c.execute("select count(*) n from asignatura").fetchone()["n"] == 1
    finally:
        c.execute(f"drop schema if exists {esquema} cascade")
        c.close()
