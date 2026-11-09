-- Núcleo multiagente: asignaturas, cola de trabajos con carril por asignatura,
-- mensajes tipados entre agentes, bitácora de llamadas al LLM y recursos.

CREATE TABLE asignatura (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dueno           text NOT NULL,
  codigo_pf       text NOT NULL,
  version_silabo  text NOT NULL,
  agente          text NOT NULL,
  silabo          jsonb NOT NULL,
  creado          timestamptz DEFAULT now(),
  UNIQUE (dueno, codigo_pf)
);

CREATE TABLE trabajo (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asignatura_id     uuid NOT NULL REFERENCES asignatura(id),
  agente            text NOT NULL,
  ambito_tipo       text NOT NULL CHECK (ambito_tipo IN ('clase', 'momento', 'asignatura')),
  ambito_id         text NOT NULL,
  herramienta       text NOT NULL,
  parametros        jsonb NOT NULL DEFAULT '{}',
  estado            text NOT NULL DEFAULT 'en_cola' CHECK (estado IN (
    'en_cola', 'generando', 'verificando', 'revisando',
    'listo', 'requiere_revision', 'error', 'en_espera')),
  lotes_total       int DEFAULT 0,
  lotes_hechos      int DEFAULT 0,
  rondas_revision   int DEFAULT 0,
  intentos          int DEFAULT 0,
  worker_id         text,
  lease_hasta       timestamptz,
  disponible_desde  timestamptz NOT NULL DEFAULT now(),
  tokens_entrada    int DEFAULT 0,
  tokens_salida     int DEFAULT 0,
  error             text,
  creado            timestamptz DEFAULT now(),
  actualizado       timestamptz DEFAULT now()
);

-- Carril por asignatura: a lo sumo un trabajo activo, aunque dos workers compitan.
CREATE UNIQUE INDEX trabajo_carril ON trabajo (asignatura_id)
  WHERE estado IN ('generando', 'verificando', 'revisando');

CREATE TABLE mensaje (
  id             bigserial PRIMARY KEY,
  trabajo_id     uuid NOT NULL REFERENCES trabajo(id),
  asignatura_id  uuid NOT NULL,
  tipo           text NOT NULL,
  cuerpo         jsonb NOT NULL,
  creado         timestamptz DEFAULT now()
);

CREATE TABLE llamada_llm (
  id             bigserial PRIMARY KEY,
  trabajo_id     uuid,
  asignatura_id  uuid,
  rol            text NOT NULL,
  tokens_entrada int NOT NULL,
  tokens_salida  int NOT NULL,
  segundos       real NOT NULL,
  ok             boolean NOT NULL,
  creado         timestamptz DEFAULT now()
);

CREATE TABLE recurso (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  trabajo_id       uuid NOT NULL UNIQUE REFERENCES trabajo(id),
  asignatura_id    uuid NOT NULL,
  ambito_id        text NOT NULL,
  herramienta      text NOT NULL,
  version_silabo   text NOT NULL,
  version_esquema  int NOT NULL DEFAULT 1,
  contenido        jsonb NOT NULL,
  evidencia        jsonb NOT NULL,
  estado           text NOT NULL CHECK (estado IN ('listo', 'requiere_revision')),
  creado           timestamptz DEFAULT now()
);
