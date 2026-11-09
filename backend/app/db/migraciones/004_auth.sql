-- Retos serializados por correo y sesiones revocables. Ningún token en claro.
CREATE TABLE auth_reto (
  correo text PRIMARY KEY,
  codigo_hash text,
  nonce text,
  emitido timestamptz,
  vence timestamptz,
  intentos integer NOT NULL DEFAULT 0 CHECK (intentos BETWEEN 0 AND 5),
  bloqueado_hasta timestamptz
);

CREATE TABLE auth_sesion (
  token_hash text PRIMARY KEY,
  correo text NOT NULL,
  creada timestamptz NOT NULL,
  actividad timestamptz NOT NULL,
  vence timestamptz NOT NULL
);
CREATE INDEX auth_sesion_vence ON auth_sesion(vence);
