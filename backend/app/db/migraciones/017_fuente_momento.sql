-- Fuentes web de la guía de estudio por momento (SearchAPI). Se guardan para no gastar créditos
-- al regenerar: cada fuente conserva su enlace real y el modelo solo la cita por su id (F1, F2, …).
-- `consultas` son los temas del sílabo que se buscaron (nunca datos del docente ni de estudiantes).
CREATE TABLE fuente_momento (
  asignatura_id uuid NOT NULL REFERENCES asignatura(id) ON DELETE CASCADE,
  momento smallint NOT NULL CHECK (momento BETWEEN 1 AND 20),
  fuentes jsonb NOT NULL DEFAULT '[]'::jsonb,
  consultas jsonb NOT NULL DEFAULT '[]'::jsonb,
  creditos integer NOT NULL DEFAULT 0 CHECK (creditos >= 0),
  error text,
  consultado timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (asignatura_id, momento)
);
