"""Fixtures compartidas de las pruebas del backend."""
import copy
import json
import uuid
from pathlib import Path

import psycopg
import pytest

from app.config import ajustes
from app.db.conexion import conectar
from app.db.migrar import aplicar_migraciones
from app.silabo.modelo import SilaboUTI


@pytest.fixture(autouse=True)
def _limpiar_ajustes():
    ajustes.cache_clear()
    yield
    ajustes.cache_clear()


# --- Base de datos (Tarea 2) ------------------------------------------------

@pytest.fixture
def conn():
    """Conexión autocommit a un esquema temporal con las migraciones aplicadas."""
    esquema = f"prueba_{uuid.uuid4().hex[:8]}"
    c = conectar()
    try:
        c.autocommit = True
        try:
            c.execute(f"create schema {esquema}")
            c.execute(f"set search_path to {esquema}")
            aplicar_migraciones(c)
            c._esquema = esquema
            yield c
        finally:
            c.execute(f"drop schema if exists {esquema} cascade")
    finally:
        c.close()


@pytest.fixture
def nueva_conexion(conn):
    """Fábrica de conexiones extra sobre el mismo esquema (concurrencia)."""
    abiertas: list[psycopg.Connection] = []

    def _nueva() -> psycopg.Connection:
        c = conectar()
        c.autocommit = True
        c.execute(f"set search_path to {conn._esquema}")
        abiertas.append(c)
        return c

    yield _nueva
    for c in abiertas:
        c.close()


# --- Sílabo (Tarea 3) -------------------------------------------------------

_RUTA_SILABO = Path(__file__).parent / "fixtures" / "silabo_datos.json"
_DATOS_SILABO = json.loads(_RUTA_SILABO.read_text(encoding="utf-8"))


@pytest.fixture
def datos() -> dict:
    """Copia nueva de los datos del sílabo de Análisis de Datos, mutable por prueba."""
    return copy.deepcopy(_DATOS_SILABO)


@pytest.fixture
def silabo(datos) -> SilaboUTI:
    """Sílabo de Análisis de Datos (M2 y M3) validado."""
    return SilaboUTI.model_validate(datos)
