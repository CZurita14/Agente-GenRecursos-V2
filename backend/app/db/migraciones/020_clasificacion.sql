-- Clasificación de las actividades del sílabo según el plan de evaluación del RRA (V3-3).
-- El plan está implícito en el sílabo: las reglas leen los rótulos y la IA clasifica, una sola vez por
-- versión del sílabo (huella), las columnas que no traen rótulo. El docente confirma en la pantalla.
ALTER TABLE trabajo DROP CONSTRAINT trabajo_tipo_check;
ALTER TABLE trabajo ADD CONSTRAINT trabajo_tipo_check CHECK (tipo IN ('generacion', 'chat', 'clasificacion'));

CREATE TABLE clasificacion_silabo (
  asignatura_id uuid NOT NULL REFERENCES asignatura (id) ON DELETE CASCADE,
  huella        text NOT NULL CHECK (length(huella) = 64),
  estado        text NOT NULL CHECK (estado IN ('en_curso', 'lista', 'error')),
  -- {"M1-S3/docente": "avance", "M2-S1/autonomo": "portafolio", …}: solo las columnas sin rótulo.
  tipos         jsonb NOT NULL DEFAULT '{}'::jsonb,
  trabajo_id    uuid REFERENCES trabajo (id) ON DELETE SET NULL,
  creado        timestamptz NOT NULL DEFAULT now(),
  actualizado   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (asignatura_id, huella)
);
