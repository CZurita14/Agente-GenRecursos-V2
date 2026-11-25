-- Contexto de cada momento que define el docente (P10): complementa al sílabo en la generación.
-- Se guarda solo si pasa la validación determinista (app/momentos/contexto.py); cada cambio deja
-- historia y vuelve «por regenerar» la guía de estudio y las herramientas del momento.
CREATE TABLE momento_contexto (
  asignatura_id uuid NOT NULL REFERENCES asignatura(id) ON DELETE CASCADE,
  momento smallint NOT NULL CHECK (momento BETWEEN 1 AND 20),
  texto text NOT NULL CHECK (length(texto) <= 6000),
  revision integer NOT NULL CHECK (revision >= 1),
  actualizado_por text NOT NULL CHECK (length(actualizado_por) <= 254),
  actualizado timestamptz NOT NULL DEFAULT clock_timestamp(),
  verificaciones jsonb NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY (asignatura_id, momento)
);

CREATE TABLE momento_contexto_historial (
  id bigserial PRIMARY KEY,
  asignatura_id uuid NOT NULL REFERENCES asignatura(id) ON DELETE CASCADE,
  momento smallint NOT NULL,
  revision integer NOT NULL,
  texto_anterior text NOT NULL DEFAULT '',
  texto_nuevo text NOT NULL,
  usuario text NOT NULL,
  creado timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX momento_contexto_historial_asig ON momento_contexto_historial (asignatura_id, momento, revision);
