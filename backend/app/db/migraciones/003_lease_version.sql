-- Token de adquisición: distingue dos ejecuciones del mismo worker.
ALTER TABLE trabajo ADD COLUMN lease_version bigint NOT NULL DEFAULT 0;
