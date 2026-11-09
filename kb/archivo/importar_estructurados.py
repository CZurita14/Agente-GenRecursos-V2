"""Importa a la base de conocimiento los datos ya estructurados de otros proyectos.

- SILABOS (`SILABOS_SALIDA/<carrera>/carrera.json`): competencias, RA de carrera
  y asignaturas con sus RA y contenidos, revisados en ese proyecto.
- AGENTE-EMPLEO (`PERFILES_EGRESO/*.yaml`): perfil de egreso, perfil
  profesional, campo ocupacional y herramientas de cada carrera, con la marca
  documentado / inferido que trae cada clave.

Uso:
    .venv/Scripts/python kb/importar_estructurados.py

Es idempotente: borra y vuelve a insertar lo importado de cada fuente.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastembed import TextEmbedding

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingesta import CACHE_MODELO, MODELO, PALABRAS_POR_FRAGMENTO, RAIZ, conectar  # noqa: E402

# carpeta de salida de SILABOS → carrera del catálogo
SILABOS = {"software": "Software", "inicial": "Educación Inicial", "basica": "Educación Básica"}

# archivo de AGENTE-EMPLEO → carrera del catálogo (diseno-grafico queda fuera por decisión del usuario)
PERFILES = {
    "administracion-de-empresas": "Administración de Empresas",
    "contabilidad-y-auditoria": "Contabilidad y Auditoría",
    "educacion-basica": "Educación Básica",
    "educacion-inicial": "Educación Inicial",
    "enfermeria": "Enfermería",
    "finanzas-y-negocios-digitales": "Finanzas y Negocios Digitales",
    "idiomas": "Pedagogía de los Idiomas Nacionales y Extranjeros",
    "ingenieria-industrial": "Industrial",
    "inteligencia-de-negocios": "Inteligencia de Negocios",
    "marketing-digital": "Marketing Digital",
    "mecatronica": "Mecatrónica",
    "medicina": "Medicina",
    "negocios-internacionales": "Negocios Internacionales",
    "odontologia": "Odontología",
    "pedagogia-actividad-fisica-y-deporte": "Pedagogía de la Actividad Física y Deporte",
    "psicologia": "Psicología",
    "psicologia-clinica": "Psicología Clínica",
    "psicologia-educativa": "Psicología Educativa",
    "software": "Software",
}

# programa de posgrados.yaml → carrera del catálogo
POSGRADOS = {
    "Maestría en Administración de Empresas con mención en Innovación y Dirección Estratégica":
        "Maestría en Administración de Empresas mención Innovación y Dirección Estratégica",
    "Maestría en Finanzas con mención en Dirección Financiera": "Maestría en Finanzas mención Dirección Financiera",
    "Maestría en Gerencia Tributaria": "Maestría en Gerencia Tributaria",
    "Maestría en Inteligencia de Negocios y Ciencia de Datos": "Maestría en Inteligencia de Negocios y Ciencia de Datos",
}


def trozos(texto: str) -> list[str]:
    """Divide un texto largo en piezas que el modelo de embeddings lee completas."""
    frases = [f.strip() for f in re.split(r"(?<=[.;])\s+", texto) if f.strip()]
    piezas, actual = [], []
    for frase in frases:
        if actual and len(" ".join(actual + [frase]).split()) > PALABRAS_POR_FRAGMENTO:
            piezas.append(" ".join(actual))
            actual = []
        actual.append(frase)
    if actual:
        piezas.append(" ".join(actual))
    return piezas


def origen_de_clave(clave: str) -> str:
    return "inferido" if "inferid" in clave else "documentado"


def horas_totales(horas) -> int | None:
    if isinstance(horas, dict):
        total = sum(v for v in horas.values() if isinstance(v, (int, float)))
        return round(total) or None
    return None


class Importador:
    def __init__(self, con, modelo):
        self.con, self.modelo = con, modelo
        with con.cursor() as cur:
            cur.execute("SELECT nombre, id FROM carrera")
            self.carreras = dict(cur.fetchall())
        self.pendientes: list[tuple] = []  # (carrera_id, asignatura_id, tipo, codigo, texto, origen, fuente)

    def carrera_id(self, nombre: str) -> int:
        if nombre not in self.carreras:
            raise KeyError(f"Carrera '{nombre}' no está en el catálogo")
        return self.carreras[nombre]

    def elemento(self, carrera: str, tipo: str, texto: str, origen: str, fuente: str,
                 codigo: str | None = None, asignatura_id: int | None = None):
        for pieza in trozos(texto):
            self.pendientes.append((self.carrera_id(carrera), asignatura_id, tipo, codigo, pieza, origen, fuente))

    def asignatura(self, carrera: str, nombre: str, nivel, unidad: str | None, horas: int | None) -> int:
        with self.con.cursor() as cur:
            cur.execute(
                """INSERT INTO asignatura (carrera_id, nombre, nivel, unidad_curricular, horas)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (carrera_id, nombre) DO UPDATE
                     SET nivel = EXCLUDED.nivel, unidad_curricular = EXCLUDED.unidad_curricular, horas = EXCLUDED.horas
                   RETURNING id""",
                (self.carrera_id(carrera), nombre.strip(), int(nivel) if str(nivel).isdigit() else None,
                 unidad or None, horas),
            )
            return cur.fetchone()[0]

    def guardar(self, fuente_prefijo: str):
        with self.con.cursor() as cur:
            cur.execute("DELETE FROM elemento_curricular WHERE fuente LIKE %s", (fuente_prefijo + "%",))
            vectores = list(self.modelo.embed([p[4] for p in self.pendientes], batch_size=64))
            cur.executemany(
                """INSERT INTO elemento_curricular
                     (carrera_id, asignatura_id, tipo, codigo, texto, origen, fuente, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [(*p, v) for p, v in zip(self.pendientes, vectores)],
            )
        self.con.commit()
        n = len(self.pendientes)
        self.pendientes = []
        return n


def importar_silabos(imp: Importador, carpeta: Path) -> int:
    for sub, carrera in SILABOS.items():
        datos = json.loads((carpeta / sub / "carrera.json").read_text(encoding="utf-8"))
        fuente = f"SILABOS/{sub}"
        for c in datos["competencias"]:
            imp.elemento(carrera, "competencia", c["texto"], "documentado", fuente, codigo=c["id"])
        for r in datos["ra_carrera"]:
            imp.elemento(carrera, "ra_carrera", r["texto"], "documentado", fuente, codigo=r["id"])
        for a in datos["asignaturas"]:
            asig_id = imp.asignatura(carrera, a["nombre"], a.get("nivel"), a.get("unidad"), horas_totales(a.get("horas")))
            for ra in a.get("ra_propios") or []:
                imp.elemento(carrera, "ra_asignatura", ra, "documentado", fuente, asignatura_id=asig_id)
            if a.get("contenidos"):
                imp.elemento(carrera, "contenido_minimo", a["contenidos"], "documentado", fuente, asignatura_id=asig_id)
    return imp.guardar("SILABOS/")


def importar_perfiles(imp: Importador, carpeta: Path) -> int:
    for archivo, carrera in PERFILES.items():
        datos = yaml.safe_load((carpeta / f"{archivo}.yaml").read_text(encoding="utf-8"))
        fuente = f"AGENTE-EMPLEO/{archivo}.yaml"
        for tipo in ("perfil_egreso", "perfil_profesional"):
            for linea in datos.get(tipo) or []:
                imp.elemento(carrera, tipo, str(linea), "documentado", fuente)
        campo = datos.get("campo_ocupacional") or {}
        if isinstance(campo, dict):
            for clave, valores in campo.items():
                for v in valores if isinstance(valores, list) else [valores]:
                    imp.elemento(carrera, "campo_ocupacional", f"{clave.replace('_', ' ')}: {v}",
                                 origen_de_clave(clave), fuente)
        for h in datos.get("herramientas") or []:
            imp.elemento(carrera, "herramienta", str(h), "documentado", fuente)

    posgrados = yaml.safe_load((carpeta / "posgrados.yaml").read_text(encoding="utf-8"))
    for p in posgrados["programas"]:
        carrera = POSGRADOS.get(p["programa"])
        if not carrera:
            continue
        for nombre in p.get("asignaturas") or []:
            imp.asignatura(carrera, nombre, None, None, None)
    return imp.guardar("AGENTE-EMPLEO/")


def main() -> int:
    load_dotenv(RAIZ / ".env")
    modelo = TextEmbedding(MODELO, cache_dir=str(CACHE_MODELO), local_files_only=True)
    with conectar() as con:
        imp = Importador(con, modelo)
        n1 = importar_silabos(imp, Path(os.environ["SILABOS_SALIDA"]))
        n2 = importar_perfiles(imp, Path(os.environ["PERFILES_EGRESO"]))
    print(f"Elementos importados: SILABOS {n1} · AGENTE-EMPLEO {n2}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
