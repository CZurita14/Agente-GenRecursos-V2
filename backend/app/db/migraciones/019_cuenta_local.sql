-- Cuentas locales para la etapa de pruebas (CUENTAS_LOCALES=true; prohibido en producción).
-- Las crea un administrador con un correo @indoamerica.edu.ec o @uti.edu.ec, sin verificar el correo.
-- Solo se guarda el hash PBKDF2 de la clave. El docente cambia la clave inicial en su primer ingreso
-- y sube el PDF de su sílabo (no tiene materias del SGA).
CREATE TABLE cuenta_local (
  correo        text PRIMARY KEY CHECK (length(correo) <= 254),
  nombre        text NOT NULL DEFAULT '' CHECK (length(nombre) <= 200),
  clave_hash    text NOT NULL,
  cambiar_clave boolean NOT NULL DEFAULT true,
  activa        boolean NOT NULL DEFAULT true,
  creada        timestamptz NOT NULL DEFAULT now(),
  creada_por    text NOT NULL,
  actualizada   timestamptz NOT NULL DEFAULT now()
);
