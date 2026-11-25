-- Cada consulta a SearchAPI (un crédito), también las que fallan: base del panel de consumo.
-- Guarda también cuánto tardó cada consulta. Solo guarda el motor, los temas buscados (del sílabo) y cuántos resultados volvieron.
CREATE TABLE busqueda_web (
  id bigserial PRIMARY KEY,
  asignatura_id uuid NOT NULL REFERENCES asignatura(id) ON DELETE CASCADE,
  momento smallint NOT NULL,
  proveedor text NOT NULL DEFAULT 'searchapi',
  motor text NOT NULL,
  consulta text NOT NULL CHECK (length(consulta) <= 300),
  ok boolean NOT NULL,
  resultados integer NOT NULL DEFAULT 0,
  error text,
  segundos numeric(10,3) NOT NULL DEFAULT 0 CHECK (segundos >= 0),
  creado timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX busqueda_web_asig_creado ON busqueda_web (asignatura_id, creado);
-- Las consultas hechas antes de este registro (solo constan como créditos por momento) entran como
-- consultas correctas sin tiempo medido, para que el total de créditos cuadre con la cuenta.
INSERT INTO busqueda_web (asignatura_id, momento, motor, consulta, ok, resultados, segundos, creado)
SELECT f.asignatura_id, f.momento, 'sin_registro', coalesce(f.consultas->>(g.n - 1), ''), true, 0, 0, f.consultado
FROM fuente_momento f CROSS JOIN LATERAL generate_series(1, f.creditos) AS g(n);
