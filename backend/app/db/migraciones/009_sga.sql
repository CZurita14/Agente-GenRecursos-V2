-- Materias que el SGA lista a cada docente y el resultado de importar su sílabo.
CREATE TABLE materia_sga (
  correo         text NOT NULL,
  id_sga         text NOT NULL,
  codigo_pf      text NOT NULL,
  paralelo       text NOT NULL,
  nombre         text NOT NULL,
  carrera        text NOT NULL,
  estado_sga     text NOT NULL,
  estado         text NOT NULL CHECK (estado IN ('importada', 'sin_cambios', 'no_disponible', 'invalida')),
  fallos         jsonb NOT NULL DEFAULT '[]'::jsonb,
  asignatura_id  uuid NULL REFERENCES asignatura(id),
  sincronizada   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (correo, id_sga)
);
CREATE INDEX materia_sga_asignatura ON materia_sga(asignatura_id);

-- Una asignatura deja de ser accesible cuando el SGA ya no lista su materia; no se borra nada.
ALTER TABLE asignatura ADD COLUMN activa_sga boolean NOT NULL DEFAULT true;
