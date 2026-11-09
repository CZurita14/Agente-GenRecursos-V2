-- P6b: validación del docente antes de exportar (spec §13). Una edición posterior la anula.
ALTER TABLE recurso ADD COLUMN validado_por text;
ALTER TABLE recurso ADD COLUMN validado_en timestamptz;
