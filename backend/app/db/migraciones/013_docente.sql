-- Cuenta del docente: se crea sola en su primer ingreso por el SGA y se actualiza en cada ingreso.
-- Es la base de la trazabilidad por docente (sus proyectos formativos por periodo vendrán después).
-- Solo guarda lo que el SGA confirma: correo y nombre. Nunca la clave.
CREATE TABLE docente (
  correo text PRIMARY KEY CHECK (length(correo) <= 254),
  nombre text NOT NULL DEFAULT '' CHECK (length(nombre) <= 200),
  primer_ingreso timestamptz NOT NULL,
  ultimo_ingreso timestamptz NOT NULL,
  ingresos integer NOT NULL DEFAULT 1 CHECK (ingresos >= 1)
);
