-- Ingreso con el SGA: ya no hay códigos por correo. Solo se cuentan los fallos de clave por usuario.
-- `usuario` guarda un seudónimo (HMAC) del nombre tecleado, nunca el texto: a veces se teclea la clave ahí.
-- `actualizado` permite limpiar contadores viejos sin conservar usuarios indefinidamente.
CREATE TABLE auth_bloqueo (
  usuario         text PRIMARY KEY,
  intentos        int NOT NULL DEFAULT 0,
  bloqueado_hasta timestamptz NULL,
  actualizado     timestamptz NOT NULL DEFAULT now()
);

DROP TABLE auth_reto;
