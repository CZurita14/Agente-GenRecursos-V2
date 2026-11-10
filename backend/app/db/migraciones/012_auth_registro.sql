-- Registro de ingresos y salidas: quién entró, cuándo y desde qué IP.
-- El correo solo se guarda cuando el SGA confirmó la identidad; en un intento fallido se guarda el
-- seudónimo HMAC del usuario tecleado (el mismo de auth_bloqueo), porque ahí puede ir una clave por error.
-- La clave nunca se guarda. La limpieza borra las filas de más de 90 días.
CREATE TABLE auth_registro (
  id bigserial PRIMARY KEY,
  creado timestamptz NOT NULL DEFAULT clock_timestamp(),
  evento text NOT NULL CHECK (evento IN ('ingreso', 'fallido', 'bloqueado', 'sga_no_disponible',
                                         'dominio_no_permitido', 'salida')),
  correo text CHECK (correo IS NULL OR length(correo) <= 254),
  usuario_hash text CHECK (usuario_hash IS NULL OR length(usuario_hash) <= 128),
  ip text NOT NULL CHECK (length(ip) <= 64)
);
CREATE INDEX auth_registro_creado ON auth_registro(creado);
CREATE INDEX auth_registro_correo ON auth_registro(correo, creado) WHERE correo IS NOT NULL;
