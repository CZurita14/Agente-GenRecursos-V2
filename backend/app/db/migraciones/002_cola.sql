-- Cola: índice parcial para tomar_siguiente. Solo cubre trabajos que aún pueden
-- tomarse (pendientes o activos), así los terminados no pesan en la búsqueda.
CREATE INDEX trabajo_pendiente ON trabajo (creado)
  WHERE estado IN ('en_cola', 'en_espera', 'generando', 'verificando', 'revisando');
