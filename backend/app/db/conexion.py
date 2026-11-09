"""Conexión a PostgreSQL."""
import psycopg
from psycopg.rows import dict_row

from app.config import ajustes


def conectar(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or ajustes().database_url, row_factory=dict_row)
