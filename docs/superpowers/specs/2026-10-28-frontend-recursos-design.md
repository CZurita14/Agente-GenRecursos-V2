# Frontend · Mis recursos (P6b) — Diseño

**Fecha:** 2026-10-28 · **Aprobado por el usuario:** el recorrido de cinco pantallas de `.superpowers/brainstorm/…/recursos-flujo.html` («está bien, continúa con el desarrollo»).

## Intención

El docente, con su asignatura ya subida, prepara las herramientas de una clase. En sus palabras: **«elige la clase, elige la actividad a realizar, genera la herramienta, revisa, valida y lista para subir a Canvas»**.

## El recorrido (aprobado)

1. **Elegir la clase:** el menú de la asignatura por semana (día, fecha, momento y contenidos). Cada clase muestra cuántos recursos tiene. Al cerrar cada momento aparece una tarjeta con sus herramientas de momento.
2. **Elegir la actividad:** el catálogo del ámbito, con las recomendadas primero, la marca «con IA» o «sin IA» y la política de IA del momento. Si el momento está restringido (§9.4.2), se muestra el motivo y solo lo permitido.
3. **Generar:** los trabajos se encolan y la pantalla muestra el avance de cada uno. El docente puede salir y volver.
4. **Revisar y validar:** el recurso, con las alertas por ítem o sección. Cuando el docente está conforme, pulsa «Validar recurso».
5. **Listo para Canvas:** descarga de un HTML autónomo que se sube a Canvas.

## Decidido por Claude (revisable)

- **La descarga queda bloqueada hasta validar.** La API responde `409` si el recurso no está validado. Así lo exige el pie de cada herramienta (§13): «Recurso generado con asistencia de IA y revisado por el docente».
- **Validar** registra quién y cuándo (`validado_por` y `validado_en`). Cualquier edición posterior anula la validación. Se puede validar un recurso con alertas: el docente decide, pero la interfaz le pide confirmarlo.
- **Formato de esta entrega: solo HTML.** Es un archivo único, sin CDN. Los cuestionarios y simulacros son autocorregibles con JavaScript en línea. PDF y Word llegan después: necesitan librerías nuevas y su formato depende de la plantilla académica (B3).
- **Todo texto del recurso se escapa** al construir el HTML. El contenido viene del LLM y del docente, así que no se interpreta como HTML.
- **La edición de ítems queda fuera** de esta entrega. El docente ve las alertas y valida; editar llega en P6c junto con el chat de ajustes (P5).
- **Navegación:**
  - «Mis asignaturas» → clic en una fila → **Asignatura** (menú por semana y sus recursos);
  - «Mis recursos» → lista de recursos por asignatura, con su estado y validación;
  - desde ambas se abre la vista **Recurso**.
- **Generación real:** necesita el proceso `worker` y el servidor de IA. Las pruebas usan la API simulada.

## No-metas

- Publicar directo en Canvas por API (fuera de alcance según el spec).
- QTI (Fase 2).
- Editar ítems.
- PDF y Word.

## Restricciones

- Mismas reglas del P6a: cookie HttpOnly, `Origin`, mensajes en español y accesibilidad de la plantilla.
- El HTML exportado no carga nada externo y su JavaScript no usa `eval` ni recursos de red.
