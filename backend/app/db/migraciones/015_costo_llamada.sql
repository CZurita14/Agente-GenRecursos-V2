-- Costo de cada llamada igual al que cobra DeepSeek: modelo, tokens de entrada en caché y costo
-- calculado con la tarifa vigente a la hora de la llamada (app/llm/precios.py). Las llamadas
-- anteriores quedan con modelo y costo nulos: el panel las estima y lo indica.
ALTER TABLE llamada_llm ADD COLUMN modelo text;
ALTER TABLE llamada_llm ADD COLUMN tokens_cache integer NOT NULL DEFAULT 0 CHECK (tokens_cache >= 0);
ALTER TABLE llamada_llm ADD COLUMN costo_usd numeric(14, 8) CHECK (costo_usd >= 0);
