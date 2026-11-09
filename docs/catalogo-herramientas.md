# Catálogo de herramientas de estudio

> **Fecha:** 2026-10-20 · **Estado:** propuesta; el **formato final** de cada
> herramienta lo definirá la **plantilla que entregará el área académica**.
> **Restricciones vigentes:** solo el sílabo como fuente · modelo Qwen3-8B (no
> se cambiará) · contexto de 8 192 tokens · revisión del docente antes de
> publicar.

## Cómo leer la tabla

- **Cómo se produce:**
  - *Sin IA*: el código la arma directamente desde el sílabo; resultado exacto.
  - *IA*: el modelo llena un esquema y el código la dibuja.
  - *IA + código calcula*: los números los calcula el código; el modelo redacta.
  - *IA + revisor*: lleva además la revisión opción por opción.
- **Confianza con Qwen3-8B:** *alta* = lista para usar con revisión ligera;
  *media* = el docente debe revisar con atención (claves y ambigüedad).
  La evidencia está en [prueba-calidad-silabo.md](prueba-calidad-silabo.md).

## 1. Por clase (unidad base del menú)

| # | Herramienta | Qué recibe el estudiante | Insumos del sílabo | Cómo se produce | Confianza |
|---|---|---|---|---|---|
| 1 | **Ficha de estudio** | Ideas clave, ejemplo resuelto paso a paso, errores frecuentes, relación con el RA y preguntas de autocomprobación | Contenidos, actividades, RA, rúbrica | IA (+ código calcula en clases cuantitativas) | **Alta** (probada) |
| 2 | **Guía de clase invertida** | Qué revisar antes de la clase, preguntas guía y qué llevar resuelto | Actividades con el docente, recursos, metodología activa | IA | Alta |
| 3 | **Práctica guiada** | Ejercicios graduados con solución paso a paso, con el software de la sesión (JASP, Excel, etc.) | Actividades práctico-experimentales, software, contenidos | IA + código calcula | Media en lo cualitativo; alta en lo numérico |
| 4 | **Cuestionario autocorregible** | Preguntas de opción múltiple por niveles, con retroalimentación por opción | Contenidos, actividades, RA, rúbrica | IA + revisor (+ código calcula) | Media (en prueba) |
| 5 | **Tarjetas de repaso** | Concepto o procedimiento por un lado y explicación por el otro | Contenidos y actividades | IA | Alta |
| 6 | **Glosario de la clase** | Términos técnicos con definición y ejemplo de uso | Contenidos y actividades | IA | Alta |
| 7 | **Mapa conceptual** | Diagrama de conceptos y relaciones de la clase | Contenidos y actividades | IA define nodos y relaciones; el código dibuja el SVG | Alta |
| 8 | **Repaso de terminología** | Crucigrama o relación de columnas | Glosario de la clase | IA da términos y pistas; el código arma la grilla | Alta |

## 2. Por momento (al cerrar cada momento en el menú)

| # | Herramienta | Qué recibe el estudiante | Insumos del sílabo | Cómo se produce | Confianza |
|---|---|---|---|---|---|
| 9 | **Repaso integrador** | Síntesis de todas las clases del momento, conectadas al RA | Sesiones del momento, RA | IA | Alta |
| 10 | **Estudio de caso** | Caso de práctica (distinto del evaluado) con preguntas escalonadas | RA, problema del territorio, rúbrica | IA | Media |
| 11 | **Simulacro** | Prueba de práctica del momento con tabla de especificaciones y solucionario | RA, contenidos, rúbrica | IA + revisor (+ código calcula) | Media |
| 12 | **Autoevaluación con la rúbrica** | La rúbrica del sílabo convertida en autoevaluación; según el nivel elegido, qué hacer para subir | Rúbrica del momento | **Sin IA** (rúbrica tal cual) + IA opcional para las sugerencias | **Alta** |
| 13 | **Lista de verificación de la evidencia** | Checklist de lo que debe tener la evidencia del momento | Evidencia y rúbrica | **Sin IA** | **Alta** |
| 14 | **Guía de la evidencia** | Qué se pide, cómo se valora y errores comunes, **sin resolverla** | Evidencia, rúbrica, política de IA | IA + revisor de integridad | Media |

## 3. Por asignatura

| # | Herramienta | Qué recibe el estudiante | Insumos del sílabo | Cómo se produce | Confianza |
|---|---|---|---|---|---|
| 15 | **Hoja de ruta de la asignatura** | Calendario por semana y día: clases, momentos, entregables y fechas | Sesiones, fechas, entregables | **Sin IA** | **Alta** |
| 16 | **Guía del producto final** | Hoja de ruta del producto final por momento y criterios de su rúbrica | Producto final, rúbrica final, momentos | IA | Media |
| 17 | **Autoevaluación final** | La rúbrica del producto final como autoevaluación | Rúbrica final | **Sin IA** | **Alta** |

## 4. Fuera del catálogo

| Herramienta | Motivo |
|---|---|
| Rúbricas nuevas redactadas por IA | El sílabo ya trae las suyas; se entregan tal cual como herramienta sin IA (rúbrica del momento y del producto final) |
| Preguntas sobre libros o lecturas de la bibliografía | El sistema solo conoce el sílabo; no inventa el contenido de las fuentes |
| Pódcasts o audio | No hay servicio de voz en la infraestructura actual |
| Soluciones o borradores de tareas, PAE, evaluaciones o evidencias | Regla de integridad académica (spec §9.4) |

## 5. Prioridad sugerida para la Fase 1

1. **Sin IA, confianza alta y costo cero:** hoja de ruta (15), autoevaluaciones
   (12, 17), lista de verificación (13).
2. **IA con confianza alta:** ficha de estudio (1), guía de clase invertida
   (2), tarjetas (5), glosario (6), mapa conceptual (7), repaso integrador (9).
3. **IA con revisión atenta del docente:** cuestionario (4), práctica guiada
   (3), simulacro (11), estudio de caso (10), guías (14, 16).
