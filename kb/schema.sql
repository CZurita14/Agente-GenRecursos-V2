-- Catálogo de facultades y carreras: lo usa el orquestador para enrutar cada
-- sílabo al agente de su facultad (spec §3.3 y §4.3).
-- La base de conocimiento completa (fragmentos y elementos curriculares) se
-- retiró el 2026-10-20 porque las herramientas se generan solo con el sílabo;
-- su diseño y código quedan en kb/archivo/.

CREATE TABLE IF NOT EXISTS facultad (
  id            serial PRIMARY KEY,
  sigla         text NOT NULL UNIQUE,
  nombre        text NOT NULL UNIQUE,
  nombres_alt   text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS carrera (
  id            serial PRIMARY KEY,
  facultad_id   int NOT NULL REFERENCES facultad(id),
  nombre        text NOT NULL,
  nombres_alt   text[] NOT NULL DEFAULT '{}',
  nivel         text NOT NULL CHECK (nivel IN ('grado', 'posgrado')),
  UNIQUE (facultad_id, nombre)
);
