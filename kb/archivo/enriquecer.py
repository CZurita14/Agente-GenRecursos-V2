"""Enriquecimiento de los fragmentos ya cargados: privacidad y aspecto.

1. Marca como `personal` los fragmentos con forma de hoja de vida o planta
   docente; el agente nunca los recupera.
2. Redacta nombres precedidos de título académico ("Mgs. Juan Pérez" →
   "[docente]") y recalcula el embedding del fragmento.
3. Marca como `administrativo` el texto legal y de licencias.
4. Clasifica el resto por similitud con descripciones de cada aspecto
   (más fiable que los títulos de sección, que en estos PDF son ruidosos).

Uso:
    .venv/Scripts/python kb/enriquecer.py
Es idempotente; ingesta.py lo ejecuta al terminar.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from fastembed import TextEmbedding

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingesta import CACHE_MODELO, MODELO, RAIZ, conectar  # noqa: E402

# Aspectos que el agente de facultad NO recupera.
EXCLUIDOS = ("personal", "administrativo", "bibliografia")

# Hojas de vida y tablas de planta docente (pueden traer nombres de personas).
HOJA_DE_VIDA = re.compile(
    r"experiencia (profesional|docente)\s*:|t[ií]tulo (de )?(tercer|cuarto) nivel|registro senescyt|"
    r"c[eé]dula de (identidad|ciudadan[ií]a)|hoja de vida|curr[ií]culum vitae|"
    r"dedicaci[oó]n\s*:?\s*(tiempo completo|medio tiempo|tiempo parcial)|nombramiento definitivo|"
    r"titular (principal|agregado|auxiliar)|relaci[oó]n de dependencia|(horas|tiempo) de dedicaci[oó]n|"
    r"m[aá]ximo t[ií]tulo|categor[ií]a del docente|personal acad[eé]mico|t[ií]tulos relacionados a la asignatura",
    re.IGNORECASE,
)
TEXTO_LEGAL = re.compile(r"\b(warrant\w*|liabilit\w*|licensor|hereby|indemnif\w*|herein)\b", re.IGNORECASE)
BIBLIOGRAFIA = re.compile(r"\bISBN\b|\b97[89][\d-]{10,}|\bEditorial\b.*\b(19|20)\d{2}\b|\b(19|20)\d{2}\b.*\bEditorial\b",
                          re.IGNORECASE)
# Filas de malla o descripción microcurricular: son contenido de asignaturas.
FILA_MICROCURRICULAR = re.compile(
    r"no es de itinerario|unidad (b[aá]sica|profesional|de integraci[oó]n curricular|de titulaci[oó]n)|"
    r"\bRAP?\s*\d|descripci[oó]n micro ?curricular|contenidos m[ií]nimos",
    re.IGNORECASE,
)
TITULO = r"(?:Dr|Dra|Ing|Lic|Lcda|Lcdo|Mg|Mgs|Mgtr|MSc|Msc|PhD|Abg|Econ|Psic|Od|Arq|Tlgo)\.?"
NOMBRE = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|[A-ZÁÉÍÓÚÑ]{2,}"
TITULO_Y_NOMBRE = re.compile(rf"\b{TITULO}\s+(?:(?:{NOMBRE})\s+){{1,3}}(?:{NOMBRE})\b")

# Descripciones de cada aspecto; el fragmento toma el aspecto más parecido.
PROTOTIPOS = {
    "perfil_egreso": [
        "perfil de egreso: al finalizar la carrera el graduado será capaz de",
        "resultados que demuestra el profesional graduado de la carrera",
    ],
    "campo_ocupacional": [
        "campo ocupacional: cargos, puestos y espacios laborales donde se desempeña el profesional",
        "empleadores, sectores productivos e instituciones que contratan al graduado",
    ],
    "competencia": [
        "competencias específicas y genéricas que desarrolla el estudiante de la carrera",
    ],
    "ra_carrera": [
        "resultados de aprendizaje de la carrera que alcanza el estudiante",
    ],
    "objeto_estudio": [
        "objeto de estudio de la profesión y objetivos generales y específicos de la carrera",
    ],
    "contenido": [
        "contenidos mínimos de la asignatura, unidades temáticas y temas de estudio",
        "descripción microcurricular de una asignatura con sus contenidos y resultados",
    ],
    "asignatura": [
        "malla curricular por niveles con asignaturas, créditos, horas y unidades de organización curricular",
    ],
    "metodologia": [
        "metodología de enseñanza y aprendizaje, ambientes de aprendizaje y evaluación de los estudiantes",
        "prácticas preprofesionales, vinculación con la sociedad y escenarios de práctica",
    ],
    "pertinencia": [
        "pertinencia de la carrera: necesidades del territorio, tensiones y problemas que atiende la profesión",
        "plan nacional de desarrollo, matriz productiva y demanda social de profesionales",
    ],
    "investigacion": [
        "líneas, programas y proyectos de investigación de la carrera",
    ],
    "administrativo": [
        "requisitos de ingreso y titulación, normativa, reglamentos y resoluciones institucionales",
        "infraestructura, laboratorios, biblioteca, presupuesto y recursos de la universidad",
    ],
}
SIMILITUD_MINIMA = 0.30


def redactar(texto: str) -> str:
    return TITULO_Y_NOMBRE.sub("[docente]", texto)


def main() -> int:
    load_dotenv(RAIZ / ".env")
    modelo = TextEmbedding(MODELO, cache_dir=str(CACHE_MODELO), local_files_only=True)
    etiquetas, vectores = [], []
    for aspecto, frases in PROTOTIPOS.items():
        for v in modelo.embed(frases):
            etiquetas.append(aspecto)
            vectores.append(v / np.linalg.norm(v))
    prototipos = np.vstack(vectores)

    with conectar() as con, con.cursor() as cur:
        # Los proyectos repiten tablas: un mismo texto en la misma carrera se guarda una sola vez.
        cur.execute("""DELETE FROM fragmento a USING fragmento b
                       WHERE a.carrera_id = b.carrera_id AND a.texto = b.texto AND a.id > b.id""")
        duplicados = cur.rowcount
        cur.execute("SELECT id, texto, embedding FROM fragmento")
        filas = cur.fetchall()

        redactados = [(i, redactar(t)) for i, t, _ in filas if TITULO_Y_NOMBRE.search(t)]
        if redactados:
            nuevos = list(modelo.embed([t for _, t in redactados]))
            cur.executemany("UPDATE fragmento SET texto = %s, embedding = %s WHERE id = %s",
                            [(t, v, i) for (i, t), v in zip(redactados, nuevos)])
            nuevos_por_id = {i: v for (i, _), v in zip(redactados, nuevos)}
            textos_por_id = dict(redactados)
            filas = [(i, textos_por_id.get(i, t), nuevos_por_id.get(i, e)) for i, t, e in filas]

        matriz = np.vstack([e.to_numpy() if hasattr(e, "to_numpy") else np.asarray(e) for _, _, e in filas])
        matriz = matriz.astype(np.float32)
        matriz /= np.linalg.norm(matriz, axis=1, keepdims=True)
        similitudes = matriz @ prototipos.T

        cambios = []
        for (i, texto, _), fila in zip(filas, similitudes):
            if HOJA_DE_VIDA.search(texto):
                aspecto = "personal"
            elif TEXTO_LEGAL.search(texto):
                aspecto = "administrativo"
            elif BIBLIOGRAFIA.search(texto):
                aspecto = "bibliografia"
            elif FILA_MICROCURRICULAR.search(texto):
                aspecto = "contenido"
            else:
                mejor = int(fila.argmax())
                aspecto = etiquetas[mejor] if fila[mejor] >= SIMILITUD_MINIMA else "otro"
            cambios.append((aspecto, i))
        cur.executemany("UPDATE fragmento SET aspecto = %s WHERE id = %s", cambios)
        con.commit()

        cur.execute("SELECT aspecto, count(*) FROM fragmento GROUP BY 1 ORDER BY 2 DESC")
        print(f"Duplicados eliminados: {duplicados}. Nombres redactados en {len(redactados)} fragmentos. Aspectos:")
        for aspecto, n in cur.fetchall():
            print(f"  {aspecto:18} {n:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
