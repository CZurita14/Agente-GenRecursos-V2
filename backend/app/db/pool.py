"""Pool mínimo de conexiones para la API.

Cada petición autenticada usaba al menos cinco conexiones nuevas (cuotas, sesión,
ruta, auditoría) a unos 15 ms cada una. El pool las reutiliza sin cambiar el código
que las usa: `pool()` entrega un préstamo con la misma interfaz que una conexión,
y su `close()` la devuelve en lugar de cerrarla.
"""
import threading
from collections.abc import Callable

import psycopg
from psycopg.pq import TransactionStatus


class _Prestamo:
    """Conexión prestada: delega todo y, al cerrarse, vuelve al pool una sola vez."""

    def __init__(self, pool: "PoolConexiones", conn: psycopg.Connection):
        object.__setattr__(self, "_pool", pool)
        object.__setattr__(self, "_conn", conn)

    def __getattr__(self, nombre):
        conn = self.__dict__["_conn"]
        if conn is None:
            raise psycopg.InterfaceError("la conexión ya fue devuelta al pool")
        return getattr(conn, nombre)

    def __setattr__(self, nombre, valor):
        setattr(self.__dict__["_conn"], nombre, valor)

    def close(self) -> None:
        conn = self.__dict__["_conn"]
        if conn is not None:
            object.__setattr__(self, "_conn", None)
            self.__dict__["_pool"]._devolver(conn)

    def __enter__(self):
        return self

    def __exit__(self, *excepcion):
        self.close()


class PoolConexiones:
    def __init__(self, fabrica: Callable[[], psycopg.Connection], max_inactivas: int = 10):
        if max_inactivas < 0:
            raise ValueError("max_inactivas no puede ser negativo")
        self._fabrica, self._max = fabrica, max_inactivas
        self._libres: list[psycopg.Connection] = []
        self._candado = threading.Lock()

    def __call__(self) -> _Prestamo:
        with self._candado:
            conn = self._libres.pop() if self._libres else None
        return _Prestamo(self, conn if conn is not None else self._fabrica())

    def _devolver(self, conn: psycopg.Connection) -> None:
        # Solo vuelve una conexión sana, sin transacción abierta y sin ajustes de sesión
        # heredados (el código usa `set statement_timeout` a nivel de sesión).
        reutilizable = not conn.closed and not conn.broken
        if reutilizable:
            try:
                if conn.info.transaction_status != TransactionStatus.IDLE:
                    reutilizable = False
                else:
                    conn.autocommit = True
                    # Solo lo que la API cambia por sesión; `reset all` borraría también
                    # ajustes legítimos de la conexión, como el search_path.
                    conn.execute("reset statement_timeout")
                    conn.execute("reset lock_timeout")
            except psycopg.Error:
                reutilizable = False
        with self._candado:
            if reutilizable and len(self._libres) < self._max:
                self._libres.append(conn)
                return
        conn.close()

    def cerrar(self) -> None:
        with self._candado:
            libres, self._libres = self._libres, []
        for conn in libres:
            conn.close()
