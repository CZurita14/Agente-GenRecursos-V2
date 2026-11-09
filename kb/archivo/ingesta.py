"""Ingesta de la documentación de carreras en PostgreSQL + pgvector.

Uso:
    .venv/Scripts/python kb/ingesta.py            # carga lo nuevo o cambiado
    .venv/Scripts/python kb/ingesta.py --forzar   # recarga todo

Lee el catálogo (kb/catalogo.yaml), recorre DOCS_CARRERAS, extrae el texto,
lo corta en fragmentos, calcula sus embeddings y los guarda. Es idempotente:
un archivo con el mismo SHA-256 no se vuelve a cargar.
Diseño: docs/base-conocimiento-carreras.md
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import openpyxl
import psycopg
import pymupdf
import yaml
from defusedxml import ElementTree as ET
from dotenv import load_dotenv
from fastembed import TextEmbedding
from pgvector.psycopg import register_vector

RAIZ = Path(__file__).resolve().parent.parent
MODELO = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
CACHE_MODELO = Path.home() / ".cache" / "matriz_curricular" / "modelos"

# El modelo solo lee 128 subpalabras: ~90 palabras en español.
PALABRAS_POR_FRAGMENTO = 90
SOLAPE = 15
# Por debajo de este promedio de caracteres por página el documento se
# considera escaneado o en imagen y queda pendiente de OCR.
MIN_CHARS_POR_PAGINA = 300

SECCIONES_PERSONALES = re.compile(
    r"hoja de vida|curriculum vitae|personal academico|planta docente|nomina|datos personales|"
    r"cedula de identidad|perfil del docente|claustro",
)
CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
TELEFONO = re.compile(r"(?:\+?593[\s-]?)?\b0?9\d{8}\b|\(0\d\)\s?\d{7}")
CEDULA = re.compile(r"\b\d{10}\b")

ASPECTOS = [  # (aspecto, patrón sobre sección + texto, sin tildes y en minúsculas)
    ("perfil_egreso", r"perfil de egreso|perfil del egresado|al egresar"),
    ("campo_ocupacional", r"perfil profesional|campo ocupacional|campo laboral|escenarios? laborales?|empleabilidad"),
    ("ra_carrera", r"resultados? de aprendizaje"),
    ("competencia", r"competencias?"),
    ("objeto_estudio", r"objeto de estudio|objetivos? de la carrera|objetivo general"),
    ("contenido", r"contenidos? minimos?|descripcion microcurricular|unidades tematicas"),
    ("asignatura", r"malla curricular|asignaturas?|unidad de organizacion curricular|creditos|horas"),
    ("metodologia", r"metodologia|ambientes de aprendizaje|practicas preprofesionales|vinculacion"),
    ("pertinencia", r"pertinencia|problemas? (del|de la) (territorio|profesion)|tensiones|necesidades"),
]


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()


# ─── Catálogo ────────────────────────────────────────────────────────────────

@dataclass
class Archivo:
    ruta: Path
    relativa: str
    carrera: str


def cargar_catalogo() -> dict:
    return yaml.safe_load((RAIZ / "kb" / "catalogo.yaml").read_text(encoding="utf-8"))


def resolver_archivos(catalogo: dict, docs: Path) -> tuple[list[Archivo], list[tuple[str, str]]]:
    excluidos = {sin_tildes(e["ruta"]).replace("\\", "/"): e["motivo"] for e in catalogo["excluir"]}

    def motivo_exclusion(relativa: str) -> str | None:
        r = sin_tildes(relativa)
        return next((m for ruta, m in excluidos.items() if r == ruta or r.startswith(ruta + "/")), None)

    archivos, omitidos = [], []
    for fac in catalogo["facultades"]:
        for car in fac["carreras"]:
            rutas: list[Path] = []
            for carpeta in car.get("carpetas", []):
                rutas += sorted(p for p in (docs / carpeta).rglob("*") if p.is_file())
            rutas += [docs / a for a in car.get("archivos", [])]
            for p in rutas:
                relativa = p.relative_to(docs).as_posix()
                if p.suffix.lower() == ".rar":
                    continue
                if (m := motivo_exclusion(relativa)):
                    omitidos.append((relativa, m))
                    continue
                archivos.append(Archivo(p, relativa, car["nombre"]))
    return archivos, omitidos


# ─── Extracción de texto ─────────────────────────────────────────────────────

def paginas_pdf(ruta: Path) -> list[str]:
    with pymupdf.open(ruta) as doc:
        return [pagina.get_text() for pagina in doc]


def paginas_xlsx(ruta: Path) -> list[str]:
    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hojas = []
    for hoja in libro:
        filas = [" | ".join(str(c).strip() for c in fila if c not in (None, "")) for fila in hoja.iter_rows(values_only=True)]
        hojas.append(f"{hoja.title}\n" + "\n".join(f for f in filas if f))
    return hojas


def paginas_docx(ruta: Path) -> list[str]:
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    raiz = ET.fromstring(zipfile.ZipFile(ruta).read("word/document.xml"))
    parrafos = ["".join(t.text or "" for t in p.iter(w + "t")) for p in raiz.iter(w + "p")]
    return ["\n".join(p for p in parrafos if p.strip())]


def extraer(ruta: Path) -> list[str]:
    ext = ruta.suffix.lower()
    if ext == ".pdf":
        return paginas_pdf(ruta)
    if ext == ".xlsx":
        return paginas_xlsx(ruta)
    if ext == ".docx":
        return paginas_docx(ruta)
    raise ValueError(f"Formato no soportado: {ruta.name}")


def limpiar(paginas: list[str]) -> list[str]:
    """Quita encabezados y pies repetidos, une palabras cortadas y redacta datos personales."""
    # Caracteres de control (incluido NUL, que PostgreSQL rechaza), salvo saltos de línea y tabuladores.
    paginas = [re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", p) for p in paginas]
    lineas = [[l.strip() for l in p.splitlines() if l.strip()] for p in paginas]
    if len(lineas) >= 5:
        frecuencia = Counter(l for p in lineas for l in set(p) if len(l) < 120)
        repetidas = {l for l, n in frecuencia.items() if n >= max(3, len(lineas) * 0.4)}
        lineas = [[l for l in p if l not in repetidas] for p in lineas]
    limpias = []
    for p in lineas:
        texto = "\n".join(p)
        texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)
        texto = CORREO.sub("[correo]", texto)
        texto = TELEFONO.sub("[teléfono]", texto)
        texto = CEDULA.sub("[número]", texto)
        limpias.append(texto)
    return limpias


# ─── Fragmentación ───────────────────────────────────────────────────────────

ES_TITULO = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+)?[A-ZÁÉÍÓÚÑ][^a-záéíóúñ]{3,}$|^\d+(?:\.\d+)+\.?\s+\S.{2,80}$")


@dataclass
class Fragmento:
    texto: str
    pagina_ini: int
    pagina_fin: int
    seccion: str | None
    aspecto: str = "otro"
    palabras: int = 0


def fragmentar(paginas: list[str]) -> tuple[list[Fragmento], int]:
    """Corta en fragmentos de ~90 palabras respetando secciones. Devuelve también
    cuántos fragmentos se descartaron por pertenecer a secciones con datos personales."""
    fragmentos: list[Fragmento] = []
    descartados = 0
    seccion: str | None = None
    buffer: list[tuple[str, int]] = []  # (palabra, página)

    def volcar(final: bool = False):
        nonlocal buffer, descartados
        while len(buffer) >= PALABRAS_POR_FRAGMENTO or (final and buffer):
            trozo = buffer[:PALABRAS_POR_FRAGMENTO]
            if seccion and SECCIONES_PERSONALES.search(sin_tildes(seccion)):
                descartados += 1
            else:
                fragmentos.append(Fragmento(
                    texto=" ".join(p for p, _ in trozo),
                    pagina_ini=trozo[0][1], pagina_fin=trozo[-1][1],
                    seccion=seccion, palabras=len(trozo),
                ))
            if len(buffer) <= PALABRAS_POR_FRAGMENTO:
                buffer = []
                break
            buffer = buffer[PALABRAS_POR_FRAGMENTO - SOLAPE:]

    for n, pagina in enumerate(paginas, start=1):
        for linea in pagina.splitlines():
            if ES_TITULO.match(linea) and len(linea) < 100:
                volcar(final=True)
                seccion = linea.strip()
            buffer += [(palabra, n) for palabra in linea.split()]
            volcar()
    volcar(final=True)
    for f in fragmentos:
        f.aspecto = clasificar(f)
    return [f for f in fragmentos if f.palabras >= 12], descartados


def clasificar(f: Fragmento) -> str:
    seccion = sin_tildes(f.seccion or "")
    for aspecto, patron in ASPECTOS:
        if re.search(patron, seccion):
            return aspecto
    texto = sin_tildes(f.texto)
    for aspecto, patron in ASPECTOS[:6]:
        if re.search(patron, texto):
            return aspecto
    return "otro"


def tipo_documento(relativa: str, paginas: int) -> str:
    nombre = sin_tildes(Path(relativa).stem)
    if relativa.lower().endswith(".xlsx") and "perfil" in nombre:
        return "perfiles_docentes"
    if "proyecto" in nombre or "rediseno" in nombre:
        return "proyecto_carrera"
    if "ajuste" in nombre:
        return "ajuste_curricular"
    if "descripcion" in nombre or "micro" in nombre:
        return "microcurricular"
    if paginas <= 1 or "malla" in nombre:
        return "malla"
    return "evidencia_malla"


# ─── Base de datos ───────────────────────────────────────────────────────────

def conectar() -> psycopg.Connection:
    con = psycopg.connect(
        host="127.0.0.1", port=os.environ["DB_PORT"], dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
    )
    register_vector(con)
    return con


def sembrar_catalogo(con: psycopg.Connection, catalogo: dict) -> dict[str, tuple[int, int]]:
    """Inserta o actualiza facultades y carreras. Devuelve carrera → (carrera_id, facultad_id)."""
    ids = {}
    with con.cursor() as cur:
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
                         SET nombres_alt = EXCLUDED.nombres_alt, nivel = EXCLUDED.nivel
                       RETURNING id""",
                    (fac_id, car["nombre"], car.get("nombres_alt", []), car["nivel"]),
                )
                ids[car["nombre"]] = (cur.fetchone()[0], fac_id)
    con.commit()
    return ids


@dataclass
class Resumen:
    cargados: list[tuple[str, str, int, int]] = field(default_factory=list)  # carrera, archivo, fragmentos, descartados
    sin_cambios: list[str] = field(default_factory=list)
    requiere_ocr: list[tuple[str, int, int]] = field(default_factory=list)   # archivo, páginas, caracteres
    duplicados: list[tuple[str, str]] = field(default_factory=list)


def ingerir(forzar: bool) -> Resumen:
    load_dotenv(RAIZ / ".env")
    docs = Path(os.environ["DOCS_CARRERAS"])
    catalogo = cargar_catalogo()
    archivos, omitidos = resolver_archivos(catalogo, docs)
    modelo = TextEmbedding(MODELO, cache_dir=str(CACHE_MODELO), local_files_only=True)
    resumen = Resumen()

    with conectar() as con:
        ids = sembrar_catalogo(con, catalogo)
        for a in archivos:
            sha = hashlib.sha256(a.ruta.read_bytes()).hexdigest()
            carrera_id, facultad_id = ids[a.carrera]
            with con.cursor() as cur:
                cur.execute("SELECT archivo FROM documento WHERE sha256 = %s", (sha,))
                previo = cur.fetchone()
                if previo and previo[0] != a.relativa:
                    resumen.duplicados.append((a.relativa, previo[0]))
                    continue
                if previo and not forzar:
                    resumen.sin_cambios.append(a.relativa)
                    continue
                cur.execute("DELETE FROM documento WHERE archivo = %s OR sha256 = %s", (a.relativa, sha))

                paginas = limpiar(extraer(a.ruta))
                caracteres = sum(len(p) for p in paginas)
                sin_texto = sum(1 for p in paginas if len(p) < 50)
                escaneado = caracteres / max(len(paginas), 1) < MIN_CHARS_POR_PAGINA and caracteres < 20_000
                tipo = tipo_documento(a.relativa, len(paginas))
                cur.execute(
                    """INSERT INTO documento (carrera_id, tipo, archivo, sha256, paginas, paginas_sin_texto, estado)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (carrera_id, tipo, a.relativa, sha, len(paginas), sin_texto,
                     "requiere_ocr" if escaneado else "ingerido"),
                )
                doc_id = cur.fetchone()[0]
                if escaneado:
                    resumen.requiere_ocr.append((a.relativa, len(paginas), caracteres))
                    con.commit()
                    continue

                fragmentos, descartados = fragmentar(paginas)
                vectores = list(modelo.embed([f.texto for f in fragmentos], batch_size=64))
                cur.executemany(
                    """INSERT INTO fragmento (documento_id, carrera_id, facultad_id, pagina_ini, pagina_fin,
                                              seccion, aspecto, texto, tokens, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [(doc_id, carrera_id, facultad_id, f.pagina_ini, f.pagina_fin, f.seccion, f.aspecto,
                      f.texto, round(f.palabras * 1.35), v) for f, v in zip(fragmentos, vectores)],
                )
            con.commit()
            resumen.cargados.append((a.carrera, a.relativa, len(fragmentos), descartados))
            print(f"  {a.carrera}: {a.relativa} → {len(fragmentos)} fragmentos", flush=True)

    for relativa, motivo in omitidos:
        print(f"  omitido: {relativa} ({motivo})")
    return resumen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--forzar", action="store_true", help="recargar aunque el archivo no haya cambiado")
    args = parser.parse_args()
    r = ingerir(args.forzar)
    print(f"\nCargados: {len(r.cargados)} · sin cambios: {len(r.sin_cambios)} · "
          f"requieren OCR: {len(r.requiere_ocr)} · duplicados: {len(r.duplicados)}")
    for archivo, paginas, chars in r.requiere_ocr:
        print(f"  requiere OCR: {archivo} ({paginas} págs., {chars} caracteres)")
    for archivo, original in r.duplicados:
        print(f"  duplicado: {archivo} = {original}")
    descartados = sum(d for *_, d in r.cargados)
    if descartados:
        print(f"  fragmentos descartados por secciones con datos personales: {descartados}")
    if r.cargados:
        import enriquecer  # privacidad y aspecto de los fragmentos (incluye los recién cargados)
        enriquecer.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
