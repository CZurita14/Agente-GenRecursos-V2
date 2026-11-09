-- Historial privado por asignatura y solicitante. La cola solo guarda el ID.
ALTER TABLE trabajo ADD COLUMN tipo text NOT NULL DEFAULT 'generacion'
  CHECK (tipo IN ('generacion', 'chat'));
CREATE TABLE chat_pedido (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  orden bigserial UNIQUE NOT NULL,
  asignatura_id uuid NOT NULL REFERENCES asignatura(id) ON DELETE CASCADE,
  usuario text NOT NULL,
  peticion_id uuid NOT NULL,
  mensaje text NOT NULL CHECK (length(mensaje) BETWEEN 1 AND 2000),
  recurso_id uuid,
  revision integer CHECK (revision >= 0),
  trabajo_id uuid UNIQUE REFERENCES trabajo(id),
  estado text NOT NULL DEFAULT 'en_cola' CHECK (estado IN ('en_cola','procesando','completado','conflicto','error')),
  respuesta text,
  accion jsonb,
  entrada_accion jsonb,
  silabo jsonb NOT NULL,
  revision_resultado integer,
  trabajos jsonb NOT NULL DEFAULT '[]',
  creado timestamptz NOT NULL DEFAULT now(),
  uso_mejora boolean NOT NULL DEFAULT false CHECK (uso_mejora = false),
  UNIQUE (asignatura_id,usuario,peticion_id),
  FOREIGN KEY (recurso_id,asignatura_id) REFERENCES recurso(id,asignatura_id) ON DELETE CASCADE,
  CHECK ((recurso_id IS NULL) = (revision IS NULL))
);
CREATE INDEX chat_historial ON chat_pedido (asignatura_id,usuario,orden DESC);
CREATE INDEX chat_pendiente ON chat_pedido (usuario) WHERE estado IN ('en_cola','procesando');
ALTER TABLE recurso_edicion ADD COLUMN revision_ia jsonb;
