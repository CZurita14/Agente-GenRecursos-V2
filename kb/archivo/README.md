# Archivo: base de conocimiento de carreras (retirada)

Código de la base de conocimiento con pgvector construida el 2026-10-20
(ingesta de la documentación oficial de las carreras, importación de mallas y
perfiles, enriquecimiento y consulta semántica).

**Se retiró el mismo día** porque las herramientas se generan **solo con el
sílabo** (decisión del usuario). Las tablas `documento`, `fragmento`,
`asignatura` y `elemento_curricular` se eliminaron de la base; solo queda el
catálogo de facultades y carreras (`kb/schema.sql`, `kb/sembrar_catalogo.py`).

El diseño, la cobertura por carrera y los hallazgos están en
`docs/base-conocimiento-carreras.md`. Para reconstruirla: crear las tablas de
`schema_completo.sql` y correr `ingesta.py` (que llama a `enriquecer.py`) y
`importar_estructurados.py`; los scripts esperan estar en `kb/`.
