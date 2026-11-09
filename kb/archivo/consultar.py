"""Consulta semántica de la base de conocimiento (prueba y depuración).

Uso:
    .venv/Scripts/python kb/consultar.py "intervalos de confianza" --carrera Software
    .venv/Scripts/python kb/consultar.py "cuidado del paciente" --facultad FCSBH -k 8
    .venv/Scripts/python kb/consultar.py --resumen
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastembed import TextEmbedding

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enriquecer import EXCLUIDOS  # noqa: E402
from ingesta import CACHE_MODELO, MODELO, RAIZ, conectar  # noqa: E402


def resumen(con) -> None:
    with con.cursor() as cur:
        cur.execute("""
            SELECT f.sigla, c.nombre,
                   count(DISTINCT d.id) FILTER (WHERE d.estado = 'ingerido')     AS docs,
                   count(DISTINCT d.id) FILTER (WHERE d.estado = 'requiere_ocr') AS ocr,
                   (SELECT count(*) FROM fragmento x WHERE x.carrera_id = c.id)  AS fragmentos,
                   (SELECT count(*) FROM elemento_curricular e WHERE e.carrera_id = c.id) AS elementos,
                   (SELECT count(*) FROM asignatura a WHERE a.carrera_id = c.id) AS asignaturas
            FROM carrera c JOIN facultad f ON f.id = c.facultad_id
            LEFT JOIN documento d ON d.carrera_id = c.id
            GROUP BY f.id, f.sigla, c.id, c.nombre ORDER BY f.id, c.id""")
        print(f"{'Facultad':8} {'Carrera':62} {'docs':>4} {'ocr':>3} {'frag':>5} {'elem':>5} {'asig':>4}")
        for sigla, carrera, docs, ocr, frag, elem, asig in cur.fetchall():
            print(f"{sigla:8} {carrera[:62]:62} {docs:>4} {ocr:>3} {frag:>5} {elem:>5} {asig:>4}")


def buscar(con, modelo, texto: str, carrera: str | None, facultad: str | None, k: int) -> None:
    vector = next(iter(modelo.embed([texto])))
    filtros, params = [], [vector]
    if carrera:
        filtros.append("c.nombre = %s")
        params.append(carrera)
    if facultad:
        filtros.append("f.sigla = %s")
        params.append(facultad)
    with con.cursor() as cur:
        for tabla, etiqueta in (("fragmento", "aspecto"), ("elemento_curricular", "tipo")):
            condiciones = list(filtros)
            extra = []
            if tabla == "fragmento":  # lo que el agente de facultad nunca recupera
                condiciones.append("x.aspecto <> ALL(%s)")
                extra.append(list(EXCLUIDOS))
            donde = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
            cur.execute(f"""
                SELECT 1 - (x.embedding <=> %s) AS similitud, c.nombre, x.{etiqueta}, x.texto
                FROM {tabla} x JOIN carrera c ON c.id = x.carrera_id JOIN facultad f ON f.id = c.facultad_id
                {donde} ORDER BY x.embedding <=> %s LIMIT %s""", params + extra + [vector, k])
            print(f"\n── {tabla} ──")
            for sim, car, et, txt in cur.fetchall():
                print(f"{sim:.3f} [{car} · {et}] {txt[:160]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("texto", nargs="?")
    parser.add_argument("--carrera")
    parser.add_argument("--facultad")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--resumen", action="store_true")
    args = parser.parse_args()
    load_dotenv(RAIZ / ".env")
    with conectar() as con:
        if args.resumen or not args.texto:
            resumen(con)
        else:
            modelo = TextEmbedding(MODELO, cache_dir=str(CACHE_MODELO), local_files_only=True)
            buscar(con, modelo, args.texto, args.carrera, args.facultad, args.k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
