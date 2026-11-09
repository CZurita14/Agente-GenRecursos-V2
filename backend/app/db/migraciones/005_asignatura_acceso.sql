CREATE TABLE asignatura_acceso (
  asignatura_id uuid NOT NULL REFERENCES asignatura(id) ON DELETE CASCADE,
  correo text NOT NULL,
  rol text NOT NULL CHECK (rol IN ('editor', 'lector')),
  PRIMARY KEY (asignatura_id, correo)
);
CREATE INDEX asignatura_acceso_correo ON asignatura_acceso(correo);
