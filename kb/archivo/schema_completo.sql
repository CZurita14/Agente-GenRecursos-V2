-- Base de conocimiento de facultades y carreras.
-- Diseño: docs/base-conocimiento-carreras.md

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE facultad (
  id            serial PRIMARY KEY,
  sigla         text NOT NULL UNIQUE,
  nombre        text NOT NULL UNIQUE,
  nombres_alt   text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE carrera (
  id            serial PRIMARY KEY,
  facultad_id   int NOT NULL REFERENCES facultad(id),
  nombre        text NOT NULL,
  nombres_alt   text[] NOT NULL DEFAULT '{}',
  nivel         text NOT NULL CHECK (nivel IN ('grado', 'posgrado')),
  UNIQUE (facultad_id, nombre)
);

CREATE TABLE documento (
  id                serial PRIMARY KEY,
  carrera_id        int NOT NULL REFERENCES carrera(id),
  tipo              text NOT NULL,
  archivo           text NOT NULL,
  sha256            text NOT NULL UNIQUE,
  paginas           int,
  paginas_sin_texto int,
  estado            text NOT NULL DEFAULT 'ingerido' CHECK (estado IN ('ingerido', 'requiere_ocr')),
  ingerido          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fragmento (
  id            bigserial PRIMARY KEY,
  documento_id  int NOT NULL REFERENCES documento(id) ON DELETE CASCADE,
  carrera_id    int NOT NULL REFERENCES carrera(id),
  facultad_id   int NOT NULL REFERENCES facultad(id),
  pagina_ini    int,
  pagina_fin    int,
  seccion       text,
  aspecto       text NOT NULL DEFAULT 'otro',
  texto         text NOT NULL,
  tokens        int NOT NULL,
  embedding     vector(768) NOT NULL
);

CREATE TABLE asignatura (
  id                serial PRIMARY KEY,
  carrera_id        int NOT NULL REFERENCES carrera(id),
  nombre            text NOT NULL,
  nivel             int,
  unidad_curricular text,
  horas             int,
  creditos          numeric,
  UNIQUE (carrera_id, nombre)
);

CREATE TABLE elemento_curricular (
  id            bigserial PRIMARY KEY,
  carrera_id    int NOT NULL REFERENCES carrera(id),
  asignatura_id int REFERENCES asignatura(id),
  tipo          text NOT NULL CHECK (tipo IN
                  ('perfil_egreso', 'perfil_profesional', 'campo_ocupacional', 'herramienta',
                   'competencia', 'ra_carrera', 'ra_asignatura', 'contenido_minimo')),
  fuente        text NOT NULL,                       -- de dónde se importó (archivo o proyecto)
  codigo        text,
  texto         text NOT NULL,
  origen        text NOT NULL CHECK (origen IN ('documentado', 'inferido', 'revisado')),
  documento_id  int REFERENCES documento(id) ON DELETE SET NULL,
  embedding     vector(768) NOT NULL
);

CREATE INDEX fragmento_embedding_idx ON fragmento USING hnsw (embedding vector_cosine_ops);
CREATE INDEX elemento_embedding_idx  ON elemento_curricular USING hnsw (embedding vector_cosine_ops);
CREATE INDEX fragmento_filtros_idx   ON fragmento (facultad_id, carrera_id, aspecto);
CREATE INDEX elemento_filtros_idx    ON elemento_curricular (carrera_id, tipo);
