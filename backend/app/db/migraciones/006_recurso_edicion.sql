ALTER TABLE recurso ADD COLUMN revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0);
ALTER TABLE recurso ADD COLUMN actualizado timestamptz NOT NULL DEFAULT now();
ALTER TABLE recurso ADD COLUMN verificacion_edicion jsonb;
ALTER TABLE recurso ADD CONSTRAINT recurso_id_asignatura UNIQUE (id, asignatura_id);

-- Historial operativo: no se activa su uso para mejora/entrenamiento.
CREATE TABLE recurso_edicion (
  id bigserial PRIMARY KEY,
  recurso_id uuid NOT NULL,
  asignatura_id uuid NOT NULL,
  usuario text NOT NULL,
  revision integer NOT NULL CHECK (revision > 0),
  contenido_anterior jsonb NOT NULL,
  contenido_nuevo jsonb NOT NULL,
  estado_anterior text NOT NULL,
  verificaciones jsonb NOT NULL,
  uso_mejora boolean NOT NULL DEFAULT false,
  creado timestamptz NOT NULL DEFAULT now(),
  UNIQUE (recurso_id, revision),
  FOREIGN KEY (recurso_id, asignatura_id) REFERENCES recurso(id, asignatura_id) ON DELETE CASCADE
);
