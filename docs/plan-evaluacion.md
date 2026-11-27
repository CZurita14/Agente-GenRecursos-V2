# Plan de evaluación implícito en el sílabo (V3)

> **Rama:** `V3-SilabosPesos` · **Fecha:** 2026-11-27 · **Estado:** V3-1 a V3-7 y V4-1 a V4-5 hechas.
> El docente no sube un plan de evaluación aparte: el plan **está en el sílabo**. El sistema lo lee, le aplica
> la norma de evaluación del RRA de la modalidad, sugiere los pesos y ofrece, junto a cada actividad
> evaluable, las herramientas que la preparan. El docente confirma los pesos o los reparte dentro de cada
> calificación (V4-4).

## 1. Norma de evaluación por modalidad

Tabla única en `backend/app/evaluacion/norma_rra.json`, que se valida al cargar (`app/evaluacion/norma.py`).

| Calificación | Presencial | En línea y distancia |
|---|---|---|
| C1 · aprendizaje en contacto con el docente | 5 | 5 |
| C3 · evaluación formativa | 20 | 10 |
| C5 · evaluación sumativa | 20 (la prueba de cada parcial) | 40 (prueba + proyecto final) |
| C2 · prácticas de aprendizaje experimental | 30 | 20 |
| C1 · aprendizaje autónomo | 5 | 5 |
| C4 · proyecto | 20 (todas las entregas) | 20 (avances) |
| **Bloques** | 2 parciales por fecha, cada uno sobre 100 | 1 bloque sobre 100 |

- **Semipresencial (= híbrida):** en espera de indicaciones. La pantalla muestra «norma pendiente» y no calcula pesos.
- **Supuesto sin confirmar:** en presencial, la nota final es el promedio 50/50 de los dos parciales.
- **Fin del Parcial 1:** la sesión cuyo texto nombra la prueba del primer parcial («primer parcial», «primer hemiciclo»…). Si ninguna la nombra, la primera prueba sumativa que no sea la última. Si tampoco hay, la mitad de las fechas.

## 2. Cómo se lee el plan del sílabo

1. **Lector del PDF del SGA** (`ciencia_datos/lector_pdf/momentos.py`): recupera las filas partidas entre páginas. Las celdas que vienen cortadas desde el propio PDF se avisan al docente al subirlo (`app/sga/traductor.py`).
2. **Reglas** (`app/evaluacion/clasificador.py`): leen los rótulos del prompt institucional («Aplicación de la evaluación diagnóstica…», «Práctica de aprendizaje experimental N…», «Foro virtual…», «Ensayo…», «Trabajo final…»). Cada una da el tipo, la calificación, el instrumento, la finalidad y el agente. Las actividades de avance («Práctica guiada…», «Ajuste…», «Repaso… para la prueba») no se califican. La misma evaluación escrita en varias columnas de una sesión cuenta una vez.
3. **IA, solo para lo que no tiene rótulo** (`app/evaluacion/ia.py`, `servicio.py`): un trabajo del worker por versión del sílabo (huella SHA-256). Recibe una lista cerrada de tipos y la consigna de ser selectivo. Las repeticiones del mismo texto se cuentan una vez y se admiten como máximo 2 prácticas por momento. Lo clasificado por la IA se marca «sugerida por IA».
4. **Pesos y auditor** (`app/evaluacion/pesos.py`): cada calificación se reparte en partes iguales entre sus actividades dentro de cada bloque, con 2 decimales que suman exacto. Las alertas nombran sesiones y calificaciones, nunca texto del sílabo:
   - calificación sin actividades;
   - falta la diagnóstica;
   - prácticas sin numerar;
   - sesión con más de 4 evaluaciones;
   - norma pendiente o desconocida.

## 3. Pantalla

`GET /asignaturas/{aid}/plan-evaluacion` alimenta `frontend/src/vistas/PlanEvaluacion.tsx`.

- **Norma de la modalidad:** barra del RRA, parciales con su suma sobre 100, alertas y aviso mientras la IA clasifica (la pantalla consulta cada 5 s).
- **En cada momento:** su % de la nota y sus evaluaciones, agrupadas por parcial, con la calificación, el peso, el instrumento, el agente y un botón por herramienta que la encola directamente.

## 4. Herramientas que preparan cada actividad

| Actividad del sílabo | Herramientas (ámbito) |
|---|---|
| Diagnóstica | **Prueba diagnóstica** de prerrequisitos (clase) |
| Prueba sumativa | **Simulacro acumulativo** (rango de momentos del parcial) · Repaso integrador (momento) |
| Cuestionario | Cuestionario · Tarjetas (clase) |
| Lectura con cuestionario | **Guía de la tarea autónoma** · Cuestionario (clase) |
| Foro | **Ficha del foro** con rúbrica (clase) |
| Estudio de caso | Estudio de caso · Rúbrica del momento (momento) |
| Práctica experimental | **Guía de la práctica y guía de observación** · Práctica guiada (clase) |
| Ensayo | **Guía de la tarea autónoma** (clase) · Rúbrica del momento |
| Portafolio | **Guía de la tarea autónoma** (clase) · Lista de verificación de la evidencia |
| Entrega de avance | **Guía de la entrega y lista de cotejo** · **Insumo de respaldo** (clase) |
| Proyecto final y su exposición | Guía del producto final · Rúbrica final · Autoevaluación final (asignatura) |
| Taller con coevaluación, autoevaluación | Rúbrica del momento · Autoevaluación con la rúbrica |

En negrita, las herramientas nuevas de la V3-6 (`app/agentes/workers/evaluacion.py`, esquemas en `app/herramientas/esquemas_evaluacion.py`). Se ofrecen solo desde el plan, junto a su actividad, y no en «Más herramientas». Como las demás, pasan por el verificador determinista y el revisor, el docente las valida y se descargan en Word y HTML.

| Herramienta | Qué trae | Qué controla el código |
|---|---|---|
| Guía de la práctica | Título, objetivo, RA, materiales, procedimiento, qué registrar, producto, condiciones y guía de observación (Logrado / En proceso / No logrado) | RA del momento; criterios sin repetir |
| Ficha del foro (§5.3) | Tema, contenido de la sesión, pregunta detonante, aporte inicial con APA 7, réplicas, uso de IA, rúbrica por niveles | Plazos sugeridos (sesión + 3 y + 6 días) y tipo de evaluación; §5.4: que sea pregunta, que no se responda con una definición y que use un contenido de la sesión |
| Guía de la tarea autónoma (§4) | Producto, propósito, RA, modalidad, condiciones, pasos, criterios por nivel, uso de IA | Criterios alineados a indicadores de la rúbrica del momento |
| Prueba diagnóstica | De 3 a 5 prerrequisitos y de 6 a 12 preguntas con explicación y «si fallas, repasa…» | Una pregunta por prerrequisito como mínimo; opciones distintas. El HTML del estudiante no lleva la clave |
| Guía de la entrega (§6.4) | Qué se entrega, sobre qué se construye, qué avance nuevo se califica, pasos, lista de cotejo, errores comunes | Ítems alineados a la rúbrica del momento |
| Insumo de respaldo (§6.3) | Tarea, insumo previo, tipo (plantilla, proyecto base, datos, versión de referencia), material listo para usar y cómo usarlo | Que no copie un entregable del momento |

**Simulacro acumulativo.** El simulacro de cada prueba sumativa cubre desde el momento siguiente a la prueba anterior hasta el suyo. Por ejemplo, las pruebas de M2-S4 y M4-S4 dan `M1-M2` y `M3-M4`. El ámbito `M1-M2` (tipo momento) combina los contenidos y RA de sus momentos, con la rúbrica y la política de IA del último. Se agrupa en la pestaña del momento que cierra el parcial y se muestra como «Momentos 1 a 2».

## 5. Verificación con los 4 sílabos piloto (V3-7)

Corrida del 26/11/2026 con DeepSeek (`deepseek-v4-pro`). Cada sílabo pasó por lectura, reglas, IA para lo que no tiene rótulo, pesos, alertas y botones del plan, con una muestra generada de cada herramienta nueva.

| Proyecto formativo | Modalidad | Evaluables | Bloques (suma sobre 100) | Botones del plan | Alertas del auditor |
|---|---|---|---|---|---|
| Programación Estructurada | En línea | 13 | Bloque único 100 | 23 | Prácticas sin numerar (M2-S3, M3-S4) |
| Electiva II | En línea | 10 | Bloque único 80 | 16 | Falta C4 proyecto (20 %); prácticas sin numerar; M2-S2 con 4 evaluaciones |
| Programación y Pensamiento Computacional | Presencial | 26 | Parcial 1: 95 · Parcial 2: 100 | 45 | Parcial 1: falta una actividad autónoma (5 %) |
| Electiva 5 | Híbrida | 13 (coincide 13/13 con su plan aprobado) | — (norma pendiente) | 23 | Norma semipresencial pendiente |

- **Lo que el sistema detecta:** que Electiva II sume 80 y el Parcial 1 de PPC sume 95 no es un error de cálculo. Son vacíos reales del sílabo frente a la norma, y el auditor los señala para que el docente los corrija.
- **Herramientas nuevas:** se generaron 19 muestras y las 19 pasaron el verificador, de 7 a 17 s cada una.
- **Botones:** ningún botón del plan queda sin poder encolarse. El plan oculta las herramientas que el sílabo no permite; por ejemplo, Electiva II no trae rúbrica final y no se le ofrece la guía del producto final.
- **Correcciones hechas en esta verificación:**
  - **Copia de un entregable:** la guía de la tarea, la de la entrega y el insumo se marcaban como copia por repetir el entregable al decir qué se entrega. Ahora ese campo puede citarlo y el resto de la herramienta no, como en la guía de la evidencia.
  - **Botón inútil:** el plan ofrecía la guía del producto final sin rúbrica final. Ahora no la ofrece.
  - **HTML con respuestas:** el HTML de la diagnóstica, que es la versión del estudiante, mostraba la clave. Ya no la muestra.
- **Punta a punta en la app local:** desde el plan de Programación Estructurada se encolaron las 7 herramientas, incluido el simulacro acumulativo M1-M3, con el worker real. Las 7 quedaron «listo», se validaron y se descargaron en Word y HTML.

## 6. Costo medido

Todas las mediciones se hicieron entre las 16:54 y las 17:26 UTC, en el horario de descuento de DeepSeek.

| Concepto | Costo medido |
|---|---|
| Clasificación con IA de las columnas sin rótulo | US$ 0,0001 a 0,005 por sílabo, una vez por versión (los 4 pilotos casi no la necesitan) |
| Herramienta nueva, solo redacción | US$ 0,002 a 0,006 |
| Herramienta nueva con verificador y revisor (punta a punta) | US$ 0,008 a 0,016 |
| Simulacro acumulativo de 6 preguntas, punta a punta | US$ 0,08 |

Estimación si el docente pulsa **todos** los botones del plan una vez:

| | Horario de descuento | Horario normal (estimado ×1,81) |
|---|---|---|
| Por proyecto formativo (promedio de los 4 pilotos) | US$ 0,47 (0,32 a 0,79) | US$ 0,85 (0,58 a 1,43) |
| 135 proyectos formativos | **US$ 63** | **US$ 114** |

- **Base de la estimación:** las herramientas con IA que ya existían, salvo el cuestionario, se calculan con el costo de una de clase (US$ 0,011). El cuestionario se calcula como el simulacro (US$ 0,08). Las herramientas sin IA no cuestan.
- **Factor ×1,81:** es la razón entre el horario normal y el de descuento que tiene el costo del informe general (US$ 487,38 frente a 268,86). Es una estimación, no una medición.
- **Por qué es un techo:** en la práctica no se pulsan todos los botones ni se regeneran todas las herramientas.

## 7. El plan, accionable (bloque V4)

**Revisión en la app (V4-1).**
- Donde la política del momento excluye la IA en una evaluación (§9.4), el plan solo ofrece herramientas sin IA y dice por qué (`ia_restringida`).
- El aviso de error aparece junto a la actividad.
- El simulacro de un rango dice «Simulacro · Momentos 1 a 3».

**Dependencias entre sesiones (V4-2, §6)** (`app/evaluacion/dependencias.py`, reglas sin IA).
- Cada tarea práctico-experimental o autónoma es **independiente** o **complementaria**.
- El insumo previo de una complementaria se busca en este orden:
  1. la sesión, práctica o momento que nombra;
  2. el producto (prototipo, portafolio, programa…) en la sesión anterior más cercana.
- **Eslabón roto** solo si la referencia no existe o el origen no tiene horas. Si el producto no aparece antes, se pide **revisar**.
- En la pantalla, cada complementaria dice de dónde viene y que se califica solo el avance nuevo (§6.4).
- El **insumo de respaldo** se ofrece solo en tareas evaluables complementarias, con el insumo detectado como indicación para la IA.
- En los 60 sílabos B26: 96 complementarias, 45 con origen, 51 para revisar y 1 eslabón roto.
- La cadena entre evidencias de momentos (§6.5) no se revisa con reglas: en el corpus la señal salía en más de la mitad de las transiciones.

**Alertas con sugerencia (V4-3).** El plan devuelve `avisos` ([{texto, sugerencia}]) y cada alerta dice cómo corregirse:
- **Calificación que falta en un bloque:** en qué sesión agregarla (la del bloque con menos evaluaciones que tiene la columna adecuada; la prueba sumativa, al cierre) y con qué rótulo del prompt institucional.
- **Diagnóstica:** en M1-S1.
- **Prácticas:** la numeración correlativa.
- **Sesión sobrecargada:** sesiones vecinas.
- **Dependencias:** cómo nombrar el insumo (§6.3).

Lo que completa el docente va entre corchetes; nunca se copia texto del sílabo.

**Pesos confirmados por el docente (V4-4).** Decisión del usuario: el docente solo reparte el peso **dentro de cada calificación**, y cada calificación conserva el % de la norma.
- **API:**
  - `PUT /asignaturas/{aid}/plan-evaluacion/pesos` con `{pesos: {clave: %}}`. Responde 422 si una calificación no suma su % y 409 si la IA aún clasifica; el lector no puede.
  - `DELETE /asignaturas/{aid}/plan-evaluacion/pesos` vuelve a los sugeridos.
- **Guardado:** tabla `pesos_docente`, una fila por versión del sílabo (huella). Si el sílabo cambia, vuelven los sugeridos y la pantalla pide confirmar de nuevo.
- **Pantalla:** editor por calificación, con su suma frente al % de la norma. «Confirmar pesos» se activa solo cuando todo cuadra.

## 8. Pendiente

- Confirmar el promedio 50/50 de los parciales presenciales.
- Definir la norma semipresencial (híbrida).
- Revisión del área académica sobre el formato de las herramientas nuevas, en especial la rúbrica del foro y la guía de observación.
