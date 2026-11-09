def test_crea_tablas(conn):
    filas = conn.execute(
        "select table_name from information_schema.tables where table_schema = current_schema()"
    ).fetchall()
    nombres = {f["table_name"] for f in filas}
    assert {"facultad", "carrera", "asignatura", "trabajo", "mensaje",
            "llamada_llm", "recurso", "migracion"} <= nombres


def test_idempotente(conn):
    from app.db.migrar import aplicar_migraciones
    assert aplicar_migraciones(conn) == []
