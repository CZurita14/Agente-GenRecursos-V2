CREATE TABLE control_limite (
  regla text NOT NULL,
  clave text NOT NULL,
  ventana timestamptz NOT NULL,
  contador integer NOT NULL CHECK (contador > 0),
  vence timestamptz NOT NULL,
  PRIMARY KEY (regla, clave)
);
CREATE INDEX control_limite_vence ON control_limite(vence);

CREATE TABLE acceso_api (
  id bigserial PRIMARY KEY,
  operacion text NOT NULL,
  metodo text NOT NULL,
  estado integer NOT NULL CHECK (estado BETWEEN 100 AND 599),
  duracion_ms integer NOT NULL CHECK (duracion_ms >= 0),
  ip_hash text NOT NULL,
  actor_hash text,
  creado timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX acceso_api_creado ON acceso_api(creado);
