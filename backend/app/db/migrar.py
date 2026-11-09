"""Aplicador de migraciones .sql en orden de nombre."""
from pathlib import Path

import psycopg

DIR = Path(__file__).parent / "migraciones"
# Clave estable compartida por todos los procesos/versiones del migrador.
CANDADO_MIGRACIONES = 0x47454E524543


def migraciones_preparadas(conn: psycopg.Connection) -> bool:
    """Solo lectura; una BD vacía o inaccesible no está preparada."""
    esperadas = {p.name for p in DIR.glob("*.sql")}
    if not esperadas:
        return False
    hechas = {f["nombre"] for f in conn.execute("select nombre from migracion").fetchall()}
    return esperadas <= hechas


def aplicar_migraciones(conn: psycopg.Connection) -> list[str]:
    """Serializa descubrimiento, creación inicial y aplicación completa.

    Requiere autocommit: cada SQL corre en su propia transacción, mientras el
    candado de sesión permanece adquirido incluso entre commits/rollbacks.
    """
    if not conn.autocommit:
        raise ValueError("El migrador requiere autocommit")
    conn.execute("select pg_advisory_lock(%s)", (CANDADO_MIGRACIONES,))
    try:
        rutas = sorted(DIR.glob("*.sql"))
        conn.execute(
            "create table if not exists migracion ("
            "nombre text primary key, aplicada timestamptz not null default now())"
        )
        hechas = {f["nombre"] for f in conn.execute("select nombre from migracion").fetchall()}
        aplicadas = []
        for ruta in rutas:
            if ruta.name in hechas:
                continue
            with conn.transaction():
                conn.execute(ruta.read_text(encoding="utf-8"))
                conn.execute("insert into migracion (nombre) values (%s)", (ruta.name,))
            aplicadas.append(ruta.name)
        return aplicadas
    finally:
        # Si la conexión se rompió, cerrar también libera el candado del servidor.
        try:
            conn.execute("select pg_advisory_unlock(%s)", (CANDADO_MIGRACIONES,))
        except psycopg.Error:
            conn.close()
            raise
