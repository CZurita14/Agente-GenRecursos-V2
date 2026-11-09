# Base de conocimiento de facultades y carreras (PostgreSQL + pgvector)

> **Fecha:** 2026-10-20 · **Estado:** diseño inicial, antes de la ingesta
> **Fuente:** `CIA/Documentacion carreras/` (52 archivos; el `.rar` del
> 2026-10-20 contiene exactamente los mismos archivos que ya estaban
> extraídos).
> **Decisión posterior (2026-10-20):** las herramientas se generan **solo con
> el sílabo**. La base se **retiró**: se eliminaron fragmentos, elementos
> curriculares, asignaturas y documentos, y **solo queda el catálogo de
> facultades y carreras** (`kb/schema.sql`, `kb/catalogo.yaml`,
> `kb/sembrar_catalogo.py`), que el orquestador usa para enrutar. El código de
> la base completa quedó en `kb/archivo/`. Este documento se conserva como
> registro del diseño y de la cobertura documental por carrera.
>
> **Propósito original:** dar a cada agente de facultad el conocimiento de sus
> carreras (perfil de egreso, competencias, RA, asignaturas, contenidos
> mínimos y campo profesional).

---

## 1. Catálogo de facultades y carreras

Definido por el usuario el 2026-10-20.

| Facultad | Sigla | Carreras |
|---|---|---|
| Ingenierías | FING | Tecnologías de la Información · Industrial · Ingeniería Civil · Software · Mecatrónica · Electricidad |
| Arquitectura, Diseño y Artes | FADA | Diseño de Productos · Diseño de Medios Interactivos · Arquitectura |
| Ciencias Económicas, Administrativas y Negocios | FACEAN | Economía · Finanzas y Negocios Digitales · Administración de Empresas · Negocios Internacionales · Inteligencia de Negocios · Marketing Digital · Contabilidad y Auditoría |
| Ciencias de la Educación | — | Pedagogía de la Actividad Física y Deporte · Educación Inicial · Educación Básica · Pedagogía de los Idiomas Nacionales y Extranjeros |
| Ciencias del Medio Ambiente | — | *(sin carreras indicadas)* |
| Ciencias de la Salud y Bienestar Humano | — | Fisioterapia · Enfermería · Medicina · Odontología |
| Ciencias Sociales y Humanas | — | Psicología · Psicología Educativa · Psicología Clínica |
| Jurisprudencia y Ciencias Políticas | — | Derecho · Ciencias Políticas y Relaciones Internacionales |

**Nombres alternos:** el sílabo dice "FACULTAD DE INGENIERIAS" y "SOFTWARE";
cada facultad y carrera guarda sus variantes de nombre para enrutar sin
errores (comparación sin tildes ni mayúsculas).

---

## 2. Cobertura de la documentación

Inventario del 2026-10-20 (páginas, caracteres de texto extraíble, páginas
sin texto).

| Facultad | Carrera | Documentos | Calidad para la base |
|---|---|---|---|
| FING | Software | 2 evidencias de malla (CACES, 25 p c/u) + malla | ✅ Texto completo |
| FING | Industrial | Ajuste sustantivo (96 p) + malla | ✅ (7 p sin texto) |
| FING | Mecatrónica | Proyecto CES (22 p) + descripción curricular (47 p) + malla | ✅ |
| FING | Tecnologías de la Información, Civil, Electricidad | — | ❌ Sin documentos |
| FADA | Diseño de Productos, Medios Interactivos, Arquitectura | — | ❌ Sin documentos |
| FADA? | **Diseño Gráfico** (no está en el catálogo) | Evidencia de malla (100 p) | ⚠️ Falta saber a qué carrera actual corresponde |
| FACEAN | Administración de Empresas | Proyecto de carrera (81 p) + 3 evidencias de malla + Excel de perfiles docentes por asignatura | ✅ |
| FACEAN | Contabilidad y Auditoría | Rediseño (83 p) + 2 mallas | ✅ |
| FACEAN | Marketing Digital | 3 evidencias de malla (86 + 81 + 5 p) | ✅ |
| FACEAN | Negocios Internacionales | Malla (1 p) + matriz de planta docente | ⚠️ Solo malla |
| FACEAN | Inteligencia de Negocios | Malla (1 p) + planta docente | ⚠️ Solo malla |
| FACEAN | Finanzas y Negocios Digitales | Descripción microcurricular (30 p) | ⚠️ **Escaneado**: requiere OCR |
| FACEAN | Economía | — | ❌ Sin documentos |
| FACEAN | Posgrados (MBA, Finanzas, Gerencia Tributaria, Inteligencia de Negocios y Ciencia de Datos) | 4 mallas (1 p) + requerimiento de personal docente | ⚠️ Solo mallas |
| Educación | Educación Inicial | Ajuste curricular (64 p) | ✅ (8 p sin texto) |
| Educación | Educación Básica | Ajuste curricular (66 p) | ✅ |
| Educación | Pedagogía de la Actividad Física y Deporte | Proyecto aprobado (39 p, casi todo imagen) | ⚠️ Requiere OCR |
| Educación | Pedagogía de los Idiomas | Malla en Word **como imágenes** | ⚠️ Requiere OCR |
| Salud | Enfermería | Proyecto de creación (275 p) + malla en Excel | ✅ (39 p sin texto) |
| Salud | Medicina | Proyecto de creación (322 p) + malla | ✅ (33 p sin texto) |
| Salud | Odontología | Proyecto de creación (583 p) + malla | ✅ (73 p sin texto) |
| Salud | Fisioterapia | — | ❌ Sin documentos |
| Sociales | Psicología | Mallas (PDF y Word **como imágenes**), malla y microcurrículo (10 p) | ⚠️ Parcial |
| Sociales | Psicología Educativa | `malla educativa.pdf` (1 p) | ⚠️ Solo malla (asignación por confirmar) |
| Sociales | Psicología Clínica | Malla de ajustes (1 p) | ⚠️ Solo malla |
| Sociales | Maestría en Psicología | 2 mallas + psicoterapia + microcurrículo | ⚠️ Posgrado |
| Jurisprudencia | Derecho, Ciencias Políticas | — | ❌ Sin documentos |
| Medio Ambiente | — | — | ❌ Sin carreras ni documentos |

**Resumen:** 13 carreras de grado con documentación útil, 6 solo con malla o
que requieren OCR, y 11 sin documentos. La base funciona igual con huecos: un
agente sin conocimiento de carrera trabaja solo con el sílabo.

### 2.1 Documentos que no se cargan

| Documento | Motivo |
|---|---|
| `Planta Docente.pdf` (Inteligencia de Negocios) | Datos personales de docentes |
| `MATRIZPLANTADOCENTE NEGOCIOSINTERNACIONALES.pdf` | Datos personales de docentes |
| `ANEXO 0577. REQUERIMIENTO DE PERSONAL DOCENTE POSGRADO…xlsx` | Gestión de personal, no currículo |
| Duplicados exactos (`Psicologia/RV_ POrtafolio docente PSICOLOGIA/*` = archivos de `Psicologia` y `Psicologia Maestria`) | Se carga una sola copia (deduplicación por SHA-256) |

`ACTUALIZACION PERFILES ADM.xlsx` sí se carga: relaciona cada asignatura de
Administración con el perfil profesional requerido para dictarla (sin
nombres de personas).

---

## 3. Qué se extrae ("aspectos")

Dos capas complementarias:

1. **Fragmentos** (para búsqueda semántica): el texto de cada documento,
   cortado por secciones, con su embedding.
2. **Entidades estructuradas** (para filtrar y relacionar): perfil de egreso,
   competencias, resultados de aprendizaje de carrera, asignaturas por nivel,
   contenidos mínimos y RA de cada asignatura. Para Software, Educación
   Inicial y Educación Básica ya existen extraídas y revisadas en el proyecto
   `SILABOS` (`salida/*/carrera.json`); se importan.

| Aspecto | Dónde aparece normalmente |
|---|---|
| Objeto de estudio y campo de actuación | Proyecto de carrera / informe CACES |
| Perfil de egreso | Proyecto de carrera / informe CACES |
| Perfil profesional y campo ocupacional | Proyecto de carrera |
| Competencias (específicas y genéricas) | Proyecto / malla |
| Resultados de aprendizaje de carrera | Proyecto / descripción microcurricular |
| Asignaturas por nivel, unidad curricular, horas y créditos | Malla |
| Contenidos mínimos y RA por asignatura | Descripción microcurricular / ajuste curricular |
| Metodologías y escenarios de práctica | Proyecto de carrera |
| Pertinencia y problemas del territorio | Proyecto de carrera |

---

## 4. Esquema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE facultad (
  id            serial PRIMARY KEY,
  sigla         text UNIQUE,
  nombre        text NOT NULL UNIQUE,
  nombres_alt   text[] NOT NULL DEFAULT '{}'          -- como aparece en sílabos
);

CREATE TABLE carrera (
  id            serial PRIMARY KEY,
  facultad_id   int NOT NULL REFERENCES facultad(id),
  nombre        text NOT NULL,
  nombres_alt   text[] NOT NULL DEFAULT '{}',
  nivel         text NOT NULL CHECK (nivel IN ('grado','posgrado')),
  modalidades   text[] NOT NULL DEFAULT '{}',
  UNIQUE (facultad_id, nombre)
);

CREATE TABLE documento (
  id            serial PRIMARY KEY,
  carrera_id    int NOT NULL REFERENCES carrera(id),
  tipo          text NOT NULL,                        -- proyecto_carrera | informe_caces | malla | microcurricular | ajuste_curricular | perfiles_docentes
  archivo       text NOT NULL,                        -- ruta relativa a la carpeta fuente
  sha256        text NOT NULL UNIQUE,                 -- deduplicación
  paginas       int,
  paginas_sin_texto int,
  ingerido      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fragmento (
  id            bigserial PRIMARY KEY,
  documento_id  int NOT NULL REFERENCES documento(id) ON DELETE CASCADE,
  carrera_id    int NOT NULL REFERENCES carrera(id),
  facultad_id   int NOT NULL REFERENCES facultad(id),
  pagina_ini    int, pagina_fin int,
  seccion       text,                                 -- título detectado
  aspecto       text,                                 -- perfil_egreso | competencia | ra_carrera | asignatura | contenido | campo_ocupacional | metodologia | pertinencia | otro
  texto         text NOT NULL,
  tokens        int NOT NULL,
  embedding     vector(768) NOT NULL
);

CREATE TABLE asignatura (
  id            serial PRIMARY KEY,
  carrera_id    int NOT NULL REFERENCES carrera(id),
  nombre        text NOT NULL,
  nivel         int,
  unidad_curricular text,
  horas         int, creditos numeric,
  UNIQUE (carrera_id, nombre)
);

CREATE TABLE elemento_curricular (                    -- entidades estructuradas
  id            bigserial PRIMARY KEY,
  carrera_id    int NOT NULL REFERENCES carrera(id),
  asignatura_id int REFERENCES asignatura(id),        -- null = nivel carrera
  tipo          text NOT NULL,                        -- perfil_egreso | competencia | ra_carrera | ra_asignatura | contenido_minimo
  codigo        text,
  texto         text NOT NULL,
  origen        text NOT NULL,                        -- documentado | inferido | revisado
  documento_id  int REFERENCES documento(id),
  embedding     vector(768) NOT NULL
);

CREATE INDEX ON fragmento USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON elemento_curricular USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON fragmento (facultad_id, carrera_id, aspecto);
CREATE INDEX ON elemento_curricular (carrera_id, tipo);
```

**Consulta típica del agente de facultad** (al generar una clase): los 5
fragmentos más afines al RA y los contenidos de la sesión, filtrados por la
carrera del sílabo; si la carrera no tiene documentos, se amplía a la
facultad.

```sql
SELECT texto, aspecto, seccion
FROM fragmento
WHERE carrera_id = $1 AND aspecto IN ('perfil_egreso','competencia','contenido','campo_ocupacional')
ORDER BY embedding <=> $2
LIMIT 5;
```

---

## 5. Ingesta

```text
archivo → SHA-256 (¿ya cargado?) → extracción de texto por página
        → limpieza (encabezados y pies repetidos, palabras cortadas)
        → corte por secciones (títulos) y luego por tamaño (~90 palabras, solape 15;
          el modelo de embeddings solo lee 128 subpalabras y trunca el resto)
        → redacción de correos, teléfonos y cédulas; descarte de secciones de
          hojas de vida y planta docente
        → clasificación del aspecto (reglas por título; IA solo si no hay regla)
        → embedding → INSERT
```

- **Texto:** PyMuPDF por página; Excel con openpyxl; Word con python-docx.
- **Páginas sin texto y documentos escaneados:** se registran y se omiten
  hasta tener OCR (pendiente 4).
- **Embeddings:** `paraphrase-multilingual-mpnet-base-v2` (768 dimensiones,
  multilingüe), local con `fastembed`; el modelo ya está descargado en este
  equipo por el proyecto `SILABOS`. El servidor de IA de la universidad no
  ofrece embeddings, solo el modelo de chat.
- **Idempotente:** volver a correr la ingesta no duplica nada (SHA-256 y
  reemplazo por documento).

---

## 6. Implementación

| Pieza | Archivo |
|---|---|
| Base de datos (desarrollo) | `docker-compose.yml`: `pgvector/pgvector:pg18`, contenedor `genrecursos-db`, solo en `127.0.0.1:15432` (el 5433 está bloqueado por Windows en este equipo) |
| Esquema | `kb/schema.sql` |
| Catálogo y asignación de documentos | `kb/catalogo.yaml` |
| Ingesta de documentos | `kb/ingesta.py` |
| Importación de datos estructurados | `kb/importar_estructurados.py`: mallas revisadas de `SILABOS/salida` (Software, Educación Inicial, Educación Básica) y 19 perfiles de `AGENTE-EMPLEO/docs/perfiles-egreso` |
| Consulta de prueba | `kb/consultar.py "texto" --carrera X` o `--facultad SIGLA`; `--resumen` |
| Credenciales | `.env` (no se versiona); plantilla en `.env.example` |

## 7. Estado de la carga (2026-10-20)

- **44 documentos** registrados (42 con texto, 2 pendientes de OCR);
  **7 895 fragmentos únicos** con embedding (se eliminaron 1 004 repetidos,
  porque los proyectos repiten tablas). De ellos, **6 532 los puede recuperar
  el agente**; 1 363 están excluidos por ser `personal`, `administrativo` o
  `bibliografia`.
- **Enriquecimiento** (`kb/enriquecer.py`, se ejecuta al final de cada
  ingesta): marca hojas de vida y tablas de planta docente como `personal`,
  redacta nombres precedidos de título académico, separa texto legal y
  bibliografía, y asigna el aspecto por similitud con descripciones de cada
  aspecto. Los aspectos son aproximados: el agente usa la similitud semántica
  y solo excluye los tres aspectos anteriores.
- **986 elementos estructurados**: 431 de SILABOS (competencias, RA de carrera,
  RA y contenidos de 137 asignaturas) y 555 de AGENTE-EMPLEO (perfil de
  egreso, perfil profesional, campo ocupacional, herramientas).
- **Pendientes de OCR:** Finanzas y Negocios Digitales, Pedagogía de la
  Actividad Física y Deporte, Idiomas y las dos mallas de Psicología en Word.
- **34 fragmentos descartados** por pertenecer a secciones con datos
  personales.
- Duración de la carga completa: ~25 min en CPU (Odontología, 583 páginas, es
  la mayor parte).

**Hallazgos de la carga:**

1. **Aspectos:** con títulos de sección, el 81 % quedaba como "otro"; con el
   enriquecimiento baja al 11 %. Es una clasificación aproximada (por
   ejemplo, algunos convenios quedan como "investigación").
2. **Los cargos "inferidos" de AGENTE-EMPLEO** aparecen en búsquedas
   académicas. Al generar herramientas, el agente consulta primero lo
   `documentado` (perfil de egreso, competencias, RA, contenidos) y usa el
   campo ocupacional solo como contexto profesional.
3. **Nombres de personas:** las hojas de vida y tablas de planta docente
   quedan excluidas (210 fragmentos) y se redactan correos, teléfonos, cédulas
   y nombres precedidos de título. Una muestra de las secuencias de palabras
   en mayúscula que quedan mostró nombres de asignaturas y encabezados, y
   autores en citas bibliográficas, no datos personales.
4. **Desbalance:** Odontología aporta cerca del 30 % de los fragmentos. Las
   consultas siempre filtran por carrera o facultad, así que no afecta a otras
   carreras.

## 8. Pendientes

| # | Pendiente |
|---|---|
| 1 | En producción, la base va al servidor de la universidad (mismo contenedor) |
| 2 | **Diseño Gráfico** fuera hasta confirmar si hubo rediseño hacia una carrera de FADA (usuario) |
| 3 | ¿`malla educativa.pdf` es la malla de **Psicología Educativa**? (asignado así de forma provisional) |
| 4 | OCR para los documentos en imagen |
| 5 | Documentos de las carreras sin documentación (TI, Civil, Electricidad, FADA, Economía, Fisioterapia, Derecho, Ciencias Políticas) y de Medio Ambiente |
| 6 | Siglas oficiales de las facultades marcadas como provisionales en `kb/catalogo.yaml` |
| 7 | Si la clasificación aproximada resulta insuficiente al generar herramientas, reclasificar por lotes con el modelo de la universidad |
