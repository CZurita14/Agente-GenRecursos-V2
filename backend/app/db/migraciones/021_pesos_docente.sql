-- Pesos del plan de evaluación confirmados o ajustados por el docente (V4-4).
-- Una fila por versión del sílabo (huella): si el sílabo cambia, vuelven los pesos sugeridos hasta que el docente
-- confirme de nuevo. El docente solo reparte el peso dentro de cada calificación del RRA; cada calificación conserva
-- el % de la norma (lo valida el backend antes de guardar).
CREATE TABLE pesos_docente (
  asignatura_id  uuid NOT NULL REFERENCES asignatura (id) ON DELETE CASCADE,
  huella         text NOT NULL CHECK (length(huella) = 64),
  -- {"M2-S3/practico/practica_experimental": 7.5, …}: % de cada actividad dentro de su bloque.
  pesos          jsonb NOT NULL,
  confirmado_por text NOT NULL,
  confirmado_en  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (asignatura_id, huella)
);
