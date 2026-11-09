"""Carga o actualiza el catálogo de facultades y carreras desde kb/catalogo.yaml.

Uso:
    .venv/Scripts/python kb/sembrar_catalogo.py

Idempotente: inserta lo nuevo y actualiza nombres alternos y nivel.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent


def main() -> int:
    load_dotenv(RAIZ / ".env")
    catalogo = yaml.safe_load((RAIZ / "kb" / "catalogo.yaml").read_text(encoding="utf-8"))
    with psycopg.connect(host="127.0.0.1", port=os.environ["DB_PORT"], dbname=os.environ["POSTGRES_DB"],
                         user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"]) as con:
        with con.cursor() as cur:
            cur.execute((RAIZ / "kb" / "schema.sql").read_text(encoding="utf-8"))
            for fac in catalogo["facultades"]:
                cur.execute(
                    """INSERT INTO facultad (sigla, nombre, nombres_alt) VALUES (%s, %s, %s)
                       ON CONFLICT (sigla) DO UPDATE SET nombre = EXCLUDED.nombre, nombres_alt = EXCLUDED.nombres_alt
                       RETURNING id""",
                    (fac["sigla"], fac["nombre"], fac.get("nombres_alt", [])),
                )
                fac_id = cur.fetchone()[0]
                for car in fac["carreras"]:
                    cur.execute(
                        """INSERT INTO carrera (facultad_id, nombre, nombres_alt, nivel) VALUES (%s, %s, %s, %s)
                           ON CONFLICT (facultad_id, nombre) DO UPDATE
                             SET nombres_alt = EXCLUDED.nombres_alt, nivel = EXCLUDED.nivel""",
                        (fac_id, car["nombre"], car.get("nombres_alt", []), car["nivel"]),
                    )
            cur.execute("SELECT (SELECT count(*) FROM facultad), (SELECT count(*) FROM carrera)")
            facultades, carreras = cur.fetchone()
    print(f"Catálogo: {facultades} facultades, {carreras} carreras")
    return 0


if __name__ == "__main__":
    sys.exit(main())
