-- Imágenes de las diapositivas (Pexels u Openverse), guardadas por su SHA-256 al generar.
-- El recurso solo guarda el hash y el crédito (autor, licencia, fuente, enlace).
CREATE TABLE imagen (
  hash text PRIMARY KEY CHECK (hash ~ '^[0-9a-f]{64}$'),
  tipo text NOT NULL CHECK (tipo IN ('image/jpeg', 'image/png', 'image/webp', 'image/gif')),
  datos bytea NOT NULL CHECK (octet_length(datos) <= 5242880),
  creado timestamptz NOT NULL DEFAULT clock_timestamp()
);
