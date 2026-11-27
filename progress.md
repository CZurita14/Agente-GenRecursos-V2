# Progreso — Generador de Recursos UTI · V2 (sílabos desde el SGA)

> **Para qué sirve:** es la memoria del proyecto V2. Al retomar, **se lee primero este archivo** y solo después, si hace falta, el documento puntual que enlaza.
>
> **Última actualización:** 2026-11-26 · **Bloque activo:** V3 — herramientas según el plan de evaluación del RRA (rama `V3-SilabosPesos`). Ver la sección *Bloque V3* justo abajo; el bloque V2 queda como historia.

## Cómo se actualiza

1. **Al cerrar una tarea** (aprobada por el revisor e integrada), el coordinador:
   - cambia su estado en el tablero;
   - anota fecha, commit, pruebas y desviaciones en *Bitácora*.
2. **Al tomar una decisión** que cambie el plan o el contrato, se registra en *Decisiones* con un enlace al documento modificado.
3. **Al abrirse o resolverse un bloqueo**, se actualiza *Bloqueos*.
4. Las entradas son **breves** (1–3 líneas). El detalle va en el commit o en `docs/`.
5. Nunca se borra la historia: lo resuelto se marca como resuelto, no se elimina.

Estados: `⬜ pendiente` · `🔄 en curso` · `🔁 devuelta (ronda n)` · `✅ hecha` · `⛔ bloqueada`

---

## Bloque V5 — preparar el parcial, calidad real y seguridad

**Objetivo:**
- que el docente prepare de una vez las herramientas de un parcial, sabiendo antes cuánto cuesta;
- medir con el worker real la calidad de cada herramienta y ajustar donde falle;
- revisar la seguridad de toda la rama antes de fusionarla.

TLS estricto queda para el final, cuando el usuario haga las pruebas finales (decisión del 2026-11-27). Se trabaja en `V3-SilabosPesos` (PR #4 en borrador).

### Tablero V5

| # | Tarea | Estado |
|---|---|---|
| V5-1 | Generar por parcial: un botón por bloque que encola las herramientas de sus evaluaciones, con el costo estimado antes de confirmar | ✅ hecha |
| V5-2 | Calidad real por herramienta: generar en los pilotos con el worker real, medir las devoluciones del revisor y el costo, ajustar los prompts | ✅ hecha (59 de 81: la cuenta de DeepSeek se quedó sin saldo) |
| V5-3 | Revisión de seguridad de la rama (sin TLS): permisos, texto del sílabo en los prompts, escape en las exportaciones, abuso y costo del encolado masivo, secretos | ✅ hecha |
| V5-4 | Validación completa, documentación y push | ✅ hecha |
| V5-5 | Una sola pantalla por Proyecto Formativo: los momentos son la pantalla principal y las clases van dentro de cada momento | ✅ hecha |

### Bitácora V5

- **2026-11-27 · V5-5 (pantalla única):** pedido del usuario para reducir clics.
  - **Al entrar a un Proyecto Formativo** se abren sus momentos (`Momentos.tsx`). Ya no existe la pantalla «Paso 1 · Elige la clase» (`Asignatura.tsx` se eliminó).
  - **En cada momento,** debajo de «Herramientas generadas», van sus clases por semana con «N recursos / sin generar»; cada una abre sus herramientas.
  - **Arriba** quedan «Ver recursos» y «Herramientas del Proyecto Formativo»; «Volver» lleva a la lista de Proyectos Formativos.
  - **Se recuerda el momento abierto:** al volver de una clase, de «Generando herramientas» o de un recurso se abre el mismo momento.
  - «Mis recursos» pasa el nombre real del Proyecto Formativo, que antes aparecía como «Asignatura».
  - Pruebas de navegador: 43 (la API simulada responde momentos, plan y resumen; dos pruebas nuevas). Verificado en la app con Electiva II.

- **2026-11-27 · V5-4 (cierre):** suite estándar del backend 1 580 pasan; frontend 37 unitarias, 42 de navegador, tipos y build; `docs/plan-evaluacion.md` §8 y §9; push a `V3-SilabosPesos` (PR #4 en borrador, sin fusionar).

- **2026-11-27 · V5-2 (calidad real):** «Preparar» en todos los bloques de los 4 pilotos, con la cuenta local `prueba.v5`: 81 trabajos y US$ 2,10, en horario normal.
  - **Resultados:**
    - las 29 herramientas de una sección que terminaron quedaron listas (1 devuelta y corregida en la revisión);
    - cuestionario y simulacro: 4 de 5 listos, unos US$ 0,22 y entre 12 y 15 minutos con 12 preguntas;
    - sin IA: 22 de 22.
  - **Corte por saldo:** a las 03:42 UTC DeepSeek respondió 402 «Insufficient Balance» (saldo de US$ 0,15) y los 22 trabajos restantes terminaron en error en un minuto.
  - **Corregido:**
    - `ClienteVLLM._pedir` convierte un 402 o un 429 en `ServidorNoDisponible`, así que el trabajo queda en espera con backoff y se reanuda solo;
    - el revisor reintenta con el doble de salida cuando el razonamiento agota los 7 000 tokens (5 de 123 revisiones);
    - `costos.py` se recalibró con lo medido, contando las preguntas en los cuestionarios.
  - **Pendiente del usuario:** recargar DeepSeek. Después, «Preparar» vuelve a ofrecer los 22 trabajos que faltaron. La cuenta de prueba sigue creada para eso.

- **2026-11-27 · V5-3 (seguridad, sin TLS):** revisión de la superficie nueva de V3 a V5; el detalle está en `docs/plan-evaluacion.md` §9.
  - **Corregido:**
    - `PUT /plan-evaluacion/pesos` aceptaba `NaN`, que esquivaba la validación y terminaba en 503. Ahora el modelo exige números finitos entre 0 y 100 y claves acotadas, y `validar_ajustes` vuelve a comprobarlo.
    - Dos «Preparar» simultáneos podían duplicar las herramientas con indicaciones. Ahora hay un candado de la base por asignatura (409).
    - En la clasificación con IA, una celda del sílabo podía imitar otra actividad en el prompt. Ahora el texto va en una línea, sin `|` ni «id=», y con un aviso de que es dato.
  - **Sin hallazgos:** permisos, SQL parametrizado, escape del HTML, `innerHTML` y secretos en el diff.
  - **Riesgo aceptado y documentado:** la clasificación que dispara un GET, que es idempotente y casi sin costo.
  - Pruebas nuevas en `test_evaluacion_servicio.py` y `test_evaluacion_pesos.py`.
- **2026-11-27 · V5-1 (preparar el parcial):**
  - `GET` y `POST /plan-evaluacion/lote`, con `ServicioMomentos.lote_parcial` y `preparar_parcial`. El lote sale del mismo plan, así que respeta §9.4, los requisitos y las dependencias; omite lo ya generado o en curso; el tope es de 40.
  - `app/evaluacion/costos.py` da el costo estimado: US$ 0,011 por herramienta de una sección, US$ 0,08 por cuestionario o simulacro y 0 sin IA; el horario normal es ×1,81.
  - **Pantalla:** «Preparar de una vez» por bloque, con la vista previa (cuántas, cuántas con IA, costo estimado y lista) antes de encolar.
  - **Verificado en la app:** Programación Estructurada, 23 herramientas (17 con IA), estimadas en US$ 0,33, encoladas y abiertas en «Generando herramientas».

---

## Bloque V4 — el plan de evaluación, accionable

**Objetivo:** que el plan implícito en el sílabo sea más útil para el docente. Revisar a la vista la pantalla de la V3; detectar la cadena de dependencias entre sesiones (prompt institucional §6); explicar cómo corregir cada alerta; y que el docente confirme o ajuste los pesos sugeridos. Se trabaja en la rama `V3-SilabosPesos` (PR #4 en borrador, sin fusionar con `main` hasta el final). Tareas elegidas por el usuario el 2026-11-26.

### Tablero V4

| # | Tarea | Estado |
|---|---|---|
| V4-1 | Revisión visual del plan en la app (botones nuevos, simulacro acumulativo en su pestaña) | ✅ hecha |
| V4-2 | Dependencias entre sesiones (§6): tareas complementarias, insumo previo, eslabones rotos; insumo de respaldo solo donde hay dependencia | ✅ hecha |
| V4-3 | Alertas con sugerencia de corrección (qué agregar y dónde) | ✅ hecha |
| V4-4 | El docente confirma o ajusta los pesos dentro de cada calificación (decisión del usuario: cada calificación conserva su % de la norma), guardado por versión del sílabo | ✅ hecha |
| V4-5 | Validación completa, documentación y push a la rama | ✅ hecha |

### Bitácora V4

- **2026-11-27 · V4-5 (cierre):** suite estándar del backend (1 568 pasan), frontend (37 unitarias, 42 de navegador, tipos y build), `docs/plan-evaluacion.md` §7 y push a `V3-SilabosPesos` (PR #4 en borrador, sin fusionar). Cuenta de prueba `prueba.v4` borrada. La base local `genrecursos-db` se había detenido al reiniciarse Docker; se volvió a arrancar.
- **2026-11-27 · V4-4 (pesos del docente):** decisión del usuario: el docente reparte el peso solo dentro de cada calificación, y cada una conserva su % de la norma.
  - **Backend:**
    - migración `021_pesos_docente.sql` (una fila por huella del sílabo);
    - `pesos.calcular(..., ajustes)`, `grupos` y `validar_ajustes`;
    - `PUT` y `DELETE /plan-evaluacion/pesos`;
    - el plan devuelve `pesos` (origen, quién y cuándo confirmó, `desactualizados` si se confirmó otra versión del sílabo), `grupos` y la `clave` de cada actividad.
  - **Pantalla:** «Confirmar o ajustar pesos», con la suma de cada calificación frente a su %; el botón se activa solo si todo cuadra; «Volver a los sugeridos».
  - **Verificado en la app con PPC:** C3 del Parcial 1 repartida en 12 / 8 → 6 % y 4 % de la nota; restaurar vuelve a 10 / 10.

- **2026-11-27 · V4-3 (alertas con sugerencia):** `Plan.alertar(texto, sugerencia)` en `pesos.py`. El plan devuelve `avisos` ([{texto, sugerencia}]) y conserva `alertas`. Sugerencias:
  - **Calificación que falta en un bloque:** propone la sesión del bloque con menos evaluaciones que tiene la columna adecuada (la prueba sumativa, al cierre del bloque), con un rótulo del prompt institucional que el docente completa.
  - **Diagnóstica:** en M1-S1.
  - **Prácticas sin numerar:** la numeración correlativa en todo el periodo.
  - **Sesión sobrecargada:** sesiones vecinas con menos evaluaciones.
  - **Dependencias:** cómo nombrar el insumo (§6.3) y medir solo el avance nuevo (§6.4).

  Nunca copian texto del sílabo; lo que el docente completa va entre corchetes. Verificado en la app con PPC.

- **2026-11-26 · V4-2 (dependencias, §6):** `app/evaluacion/dependencias.py`, con reglas deterministas y sin IA.
  - **Clasificación:** cada tarea (columna práctico-experimental o autónoma) es independiente o complementaria. Marcadores: versión corregida o final, iteración, ajuste, aplicación de mejoras, incorporación, fase de desarrollo o entrega, «continúa con», «a partir del prototipo…». Las lecturas previas, los prerrequisitos, los ajustes razonables (DUA), «incorpora retroalimentación» y «continua» como adjetivo cuentan como independientes.
  - **Insumo previo:** primero la sesión, práctica o momento que nombra; después el producto (prototipo, portafolio, programa…) en la sesión anterior más cercana que lo menciona; la misma sesión, solo al final. El prototipo del PIS es externo y no se busca.
  - **Severidad:**
    - eslabón roto (alerta) solo si la referencia no existe o el origen no tiene horas;
    - si el producto no aparece antes, se pide revisar, porque buscar por nombre de producto es una señal débil.
  - **Sin alerta de la cadena de evidencias (§6.5):** en el corpus salía en 106 de unas 180 transiciones, así que era ruido.
  - **Corpus B26 (60 sílabos):** 96 complementarias, 45 con origen, 51 para revisar y 1 eslabón roto.
  - **En la pantalla:** cada tarea complementaria dice de dónde viene y que se califica solo el avance nuevo (§6.4).
  - **Insumo de respaldo:** se ofrece solo en tareas evaluables complementarias, y el botón le pasa a la IA el insumo previo detectado. Antes aparecía en toda entrega de avance.
  - Pruebas: `test_evaluacion_dependencias.py`.

- **2026-11-26 · V4-1 (revisión visual):** recorrido en el navegador con PPC (presencial). La norma, los parciales, el % por momento y las evaluaciones con sus botones nuevos se ven bien. Corregido:
  - **Error de fondo:** el plan ofrecía herramientas con IA en un momento cuya política prohíbe la IA en una evaluación (M3 de PPC). Al pulsar, el backend respondía 422 y el aviso quedaba al final del momento, fuera de la vista. Ahora `disponibles` aplica la regla §9.4; el plan devuelve `ia_restringida` y la pantalla explica por qué solo hay herramientas sin IA.
  - El aviso de error aparece junto a la actividad cuyo botón se pulsó.
  - El botón del simulacro de un rango dice «Simulacro · Momentos 1 a 3».
  - El % del momento usa el mismo redondeo (un decimal) en la pestaña y en el plan (antes «35 %» frente a «34,99 %»).

---

## Bloque V3 — herramientas según el plan de evaluación (RRA)

**Objetivo:** dejar de ofrecer todas las herramientas en todas las clases. Cada actividad del sílabo se clasifica (evaluable o de avance; calificación del RRA, instrumento, insumo previo) y el sistema ofrece solo lo que la prepara, con el peso que tiene en la nota. Mockup aprobado el 2026-11-26.

### Norma (decisiones del usuario)

| Modalidad | Contacto / práctico / autónomo | C5 sumativa | C4 proyecto | Bloques |
|---|---|---|---|---|
| Presencial | 45 / 30 / 25 (C1 5 · C3 20 · C5 20) | prueba acumulativa de cada parcial | todas las entregas | 2 parciales por fecha, cada uno 100 % |
| En línea y distancia | 55 / 20 / 25 (C1 5 · C3 10 · C5 40) | prueba + proyecto final | avances | un bloque |
| Semipresencial (híbrida) | 45 / 30 / 25 (C5 30) | ⏸ en espera | ⏸ | ⏸ — aviso «norma pendiente», sin pesos |

Fuentes: «3. Armonización del plan de evaluación con el RRA» y «2. Plan_de_evaluacion_PF_UTI _ Presencial». Supuesto por confirmar: nota final = promedio 50/50 de los parciales.

### Tablero V3

| # | Tarea | Estado |
|---|---|---|
| V3-0 | Commit de las cuentas locales de prueba (`a7720a6`) | ✅ hecha |
| V3-1 | Lector: filas partidas entre páginas y aviso de celdas cortadas | ✅ hecha |
| V3-2 | Norma por modalidad (tabla configurable) y parciales por fecha | ✅ hecha |
| V3-3 | Clasificador de actividades (rótulos y, sin rótulo, IA) | ✅ hecha |
| V3-4 | Pesos sugeridos, suma por momento y parcial, auditor con alertas | ✅ hecha |
| V3-5 | API y pantalla de momentos del mockup (reemplaza el menú fijo por clase) | ✅ hecha |
| V3-6 | Herramientas nuevas: ficha de foro, guía de la práctica, guía de observación, guía de la tarea autónoma, diagnóstica, simulacro acumulativo, guía de la entrega, insumo de respaldo | ✅ hecha |
| V3-7 | Verificación con los 4 sílabos piloto, costo medido y documentación | ✅ hecha |

Sílabos piloto: Programación Estructurada (en línea), Electiva 2 (en línea), PPC (presencial), Electiva 5 (híbrida) — en `Desktop/SILABOS B26/`.

### Bitácora V3

- **2026-11-26 · V3-7 (verificación, costo y documentación):**
  - Los 4 pilotos de punta a punta con DeepSeek:
    - Programación Estructurada: 13 evaluables, bloque 100.
    - Electiva II: 10 evaluables, bloque 80 (falta C4 proyecto).
    - PPC: 26 evaluables, P1 95 (falta una autónoma) y P2 100.
    - Electiva 5: 13 evaluables, coincide 13/13; norma pendiente.
  - 19 muestras de las herramientas nuevas pasan el verificador.
  - Correcciones:
    - El campo que dice qué se entrega (guía de la tarea, guía de la entrega, insumo) puede citar la entrega del sílabo, y el resto no (`CITA_ENTREGA`). Antes daba «copia un entregable» en 3 de 18 casos.
    - El plan oculta las herramientas que no se pueden encolar (`disponibles`), por ejemplo la guía del producto final sin rúbrica final (Electiva II).
  - Costo medido en horario de descuento:
    - herramienta nueva de punta a punta: US$ 0,008 a 0,016;
    - simulacro acumulativo: US$ 0,08;
    - todos los botones del plan: US$ 0,47 por PF y unos US$ 63 para 135 PF (unos US$ 114 en horario normal, estimado).
  - Documentación: `docs/plan-evaluacion.md` y README.
  - Pruebas: backend 1 544 pasan; frontend 37 unitarias y tipos.

- **2026-11-26 · V3-6 (herramientas nuevas):**
  - Seis herramientas de clase, de una sección, en `app/agentes/workers/evaluacion.py`. Sus esquemas están en `app/herramientas/esquemas_evaluacion.py` y sus verificadores en `verificador.py`:
    - `guia_practica`: guía de la práctica experimental con su guía de observación (criterios observables; Logrado / En proceso / No logrado);
    - `ficha_foro` (prompt institucional §5.3): tema, contenido de la sesión, pregunta detonante, aporte inicial con APA 7, réplicas, uso de IA y rúbrica alineada a la del momento. Los plazos sugeridos (sesión + 3 y + 6 días) y el tipo de evaluación los pone el código. El verificador aplica la §5.4: la pregunta no se responde con una definición y usa un contenido de la sesión;
    - `guia_tarea` (§4): producto, propósito, RA, modalidad, condiciones, pasos, criterios por nivel y uso de IA;
    - `prueba_diagnostica`: de 3 a 5 prerrequisitos y de 6 a 12 preguntas, al menos una por prerrequisito. Las respuestas van solo en la versión del docente;
    - `guia_entrega`: qué se entrega, sobre qué se construye y qué avance nuevo se califica (§6.4), con su lista de cotejo;
    - `insumo_respaldo` (§6.3): plantilla, proyecto base, conjunto de datos o versión de referencia para quien no completó la actividad previa.
  - Las seis se ofrecen desde el plan de evaluación, junto a su actividad, y no en «Más herramientas» (`DEL_PLAN`).
  - Simulacro acumulativo: el `simulacro` de cada prueba sumativa se genera sobre un rango de momentos (`M1-M2`), desde la prueba anterior hasta la suya (`rangos_acumulados`). El rango usa los contenidos y RA de todos sus momentos y la rúbrica y la política de IA del último. Se agrupa en el momento que cierra el parcial y se muestra como «Momentos 1 a 2».
  - Prueba real con DeepSeek (Electiva 5 y Programación Estructurada): 10 herramientas, todas pasan el verificador, de US$ 0,002 a 0,006 cada una y de 10 a 19 s.
  - E2E local con el worker real (Programación Estructurada): las 7 herramientas, incluido el simulacro `M1-M3`, se encolan desde el plan, quedan «listo», se validan y se descargan en Word y HTML. El HTML de la diagnóstica (del estudiante) no lleva clave ni repaso. Cuenta de prueba borrada.
  - Pruebas: suite estándar del backend 1 540 pasan, 28 nuevas en `test_herramientas_evaluacion.py` (incluye el trabajo completo con el coordinador para cada herramienta); frontend 37 unitarias, 42 de navegador, tipos y build.

- **2026-11-26 · V3-5 (API y pantalla):**
  - `GET /asignaturas/{aid}/plan-evaluacion` en `ServicioMomentos.plan_evaluacion` devuelve norma, bloques, actividades con su calificación, peso, instrumento y herramientas, más los totales por momento y bloque, las alertas y el estado de la IA. El dueño o editor encola la clasificación con IA si falta; el lector no.
  - `app/evaluacion/herramientas.py` relaciona cada tipo de actividad con las herramientas existentes y su ámbito (clase, momento o asignatura).
  - Frontend:
    - `vistas/PlanEvaluacion.tsx` con `NormaModalidad` (barra del RRA, parciales con su suma sobre 100, alertas, aviso de IA en curso con consulta cada 5 s) y `PlanMomento` (evaluables por parcial, con su calificación, peso, instrumento, «sugerida por IA» y un botón por herramienta que la encola directamente);
    - `Momentos.tsx` muestra el % de la nota en cada pestaña; «Herramientas del momento» pasa a «Herramientas generadas» y «Más herramientas» conserva el selector anterior.
  - Correcciones al probar con Salud:
    - «Evaluación / examen (del primer / segundo) hemiciclo» y «examen institucional» son pruebas sumativas;
    - la misma evaluación escrita en varias columnas de la sesión cuenta una vez;
    - el Parcial 1 cierra en la primera prueba sumativa clasificada si el texto no nombra el parcial. Adulto Mayor cierra el 30/11 en M2-S13.
  - E2E local:
    - cuenta de prueba con tres PDF (Programación Estructurada, PPC y Adulto Mayor; este último clasificado por el worker con IA);
    - la pantalla de PPC muestra la norma presencial, P1 95/100 con su alerta, P2 100/100, el peso de cada momento y las 6 evaluaciones de M1;
    - el botón «Lista de verificación de la evidencia» encola (202) y abre «Generando herramientas».
  - Pruebas: suite estándar del backend 1 501 pasan; frontend 35 unitarias y 42 de navegador, tipos y build.
- **2026-11-26 · V3-4:** `app/evaluacion/pesos.py`:
  - Cada calificación del RRA se reparte en partes iguales entre sus actividades dentro de cada bloque, con 2 decimales que suman exacto. Cada bloque suma 100; en presencial cada parcial vale la mitad de la nota (supuesto).
  - Totales por bloque y por momento.
  - Alertas, que nombran sesiones y calificaciones y nunca texto del sílabo:
    - calificación sin actividades;
    - falta la diagnóstica;
    - prácticas experimentales sin numerar;
    - sesión con 4 o más evaluaciones;
    - norma pendiente o desconocida (sin pesos).
  - Pilotos:
    - Programación Estructurada: suma 100 (M1 1 %, M2 25 %, M3 32 %, M4 42 %);
    - PPC: P1 95/100 (falta la autónoma) y P2 100/100;
    - Electiva 2: 80/100 (falta C4, avances) y M2-S2 sobrecargada;
    - Electiva 5: sin pesos (híbrida en espera).
  - Pruebas: `test_evaluacion_pesos.py` 7 nuevas.
- **2026-11-26 · V3-3 (parte 2, IA):** `app/evaluacion/ia.py`, `servicio.py`, migración `020_clasificacion.sql` (`trabajo.tipo` admite `clasificacion` y la tabla `clasificacion_silabo` por huella del sílabo):
  - La IA solo elige el tipo de una lista cerrada; la calificación, el instrumento y el tipo de evaluación los pone el mismo mapa de las reglas. El prompt lleva solo el texto de las actividades.
  - Se clasifica una vez por versión del sílabo (huella SHA-256), como trabajo del worker; no se duplica, un error se puede reintentar, y un sílabo sin columnas sin rótulo no llama a la IA.
  - Criterios para no calificar de más:
    - la misma actividad repetida se califica solo en su última sesión;
    - la IA sugiere como máximo 2 prácticas por momento;
    - el pedido dice cuántas evaluaciones ya reconocieron las reglas.
  - Real con DeepSeek en 4 sílabos de Salud (Farmacología con 0 rótulos, Adulto Mayor, Enfermería Madre y Recién Nacido, Enfermería Quirúrgica): de 19 a 29 evaluables por sílabo, 1–2 llamadas, 10–20 s, **US$ 0,002–0,005 por sílabo**.
  - Pruebas: `test_evaluacion_servicio.py` 11 nuevas.
- **2026-11-26 · V3-3 (parte 1, reglas):** `app/evaluacion/clasificador.py`:
  - Cada columna de cada sesión se clasifica por sus rótulos en evaluable o de avance. Las evaluables llevan su calificación del RRA, instrumento, finalidad y agente. El proyecto final va a C5 en la modalidad en línea y a C4 en la presencial.
  - Electiva 5 coincide 13/13 con su plan de evaluación aprobado (mismo instrumento y tipo); Programación Estructurada da 13 evaluables, Electiva 2 10 y PPC 26, todas con 0 columnas sin rótulo.
  - En los 60 sílabos B26 legibles (40 presenciales, 13 en línea, 7 híbridos): 386 evaluables (6,4 por sílabo, de 0 a 26) y **33 % de columnas sin rótulo**, concentradas en Salud (Adulto Mayor, Enfermería, Farmacología) y con «estudio de caso» muy usado (94).
  - ✅ Decisión del usuario (2026-11-26): no se pide el plan de evaluación; el plan está **implícito en el sílabo**. Lo que no trae rótulo lo clasifica la IA (parte 2).
  - Pruebas: `test_evaluacion_clasificador.py` 25 nuevas; suite estándar 1 451 pasan.
- **2026-11-26 · V3-2:** `app/evaluacion/norma.py` + `norma_rra.json`:
  - Tabla configurable con las seis calificaciones del RRA. Se valida al cargar: cada modalidad definida suma 100 y no admite calificaciones desconocidas.
  - Alias de modalidad: PRESENCIAL; EN LINEA, ONLINE y VIRTUAL; DISTANCIA (= en línea); SEMIPRESENCIAL o HIBRIDA (pendiente). Una modalidad desconocida devuelve `None`, sin pesos inventados.
  - Bloques por fecha: un solo bloque en línea; en presencial, el Parcial 1 cierra en la sesión de su prueba acumulativa («primer parcial») o, si no se reconoce, a la mitad del periodo; la norma pendiente no arma bloques.
  - Pilotos: PPC con P1 del 05/10 al 03/12 (cierra en M3-S4) y P2 del 07/12 al 11/02, 18 sesiones cada uno; los dos cursos en línea en un bloque; Electiva 5 pendiente. Pruebas: `test_evaluacion_norma.py` 21 nuevas.
- **2026-11-26 · V3-1:** lector (`ciencia_datos/lector_pdf/momentos.py`):
  - Una fila de sesión partida entre páginas ya no se pierde cuando su primera celda arrastra el final de la fecha («14/12/2026»).
  - Cada fila se lee con el mapa de columnas de su ancho, porque en la página siguiente la tabla puede llegar sin la celda combinada.
  - El traductor avisa las actividades que terminan en coma o en una palabra que exige continuación. El aviso da la ruta y nunca el texto.
  - Al subir el PDF, el docente ve esos avisos legibles («Momento 1, sesión 4 · trabajo autónomo»).
  - Recuperados: Programación Estructurada M1-S1 (diagnóstica y foro) y Electiva 5 M1-S4 (foro y ensayo) y M4-S3 (trabajo final).
  - En los 61 PDF de `SILABOS B26`, 11 celdas de otras facultades siguen cortadas, pero vienen así en el PDF del SGA (verificado en Patología Estomatológica M4-S4) y ahora generan aviso. `Silabo SIstemas de Control.pdf` sigue ilegible; queda fuera del alcance.
  - Pruebas: backend 1 430 pasan (suite estándar); frontend 35 unitarias y 42 de navegador; tipos y build sin errores. E2E en local: cuenta de prueba, subida de Programación Estructurada (sin avisos) y Patología Estomatológica (3 avisos visibles en la pantalla).
  - Push de la rama `V3-SilabosPesos` a `origin` (primera vez) con autorización del usuario.
- **2026-11-26 · V3-0:** commit `a7720a6` de las cuentas locales (admin crea cuentas @indoamerica.edu.ec / @uti.edu.ec, PBKDF2, cambio obligatorio, PDF del sílabo). Pruebas de esa entrega: 1 428 backend y 34 frontend.

---

## Estado en una línea

V2 funcionalmente completa en la rama `v2/sga`: el docente ingresa con su usuario y clave del SGA, el sistema sincroniza sus materias y sus sílabos en JSON, los valida (esquema + 7 reglas) y genera las mismas 13 herramientas que V1 (equivalencia: 59/59 huellas iguales). Documentación hecha y hallazgos de la revisión final corregidos. **Falta:** el adaptador real del SGA (B-SGA1, TI), la verificación E2E final y el push.

## Origen

- **V1:** https://github.com/CZurita14/Agente-GenRecursos (`main` = `011bd68`). Su historia (P1–P10) y sus planes quedan allí.
- **Contrato del sílabo:** [docs/api-silabo/](docs/api-silabo/). Pasadas en V1: 23/23 prompts idénticos, 31/32 campos consumidos.

## Tablero

| # | Tarea | Estado |
|---|---|---|
| 0 | Copia limpia y `progress.md` | ✅ hecha |
| 1 | Contrato en el código e integridad | ✅ hecha |
| 2 | Proveedor SGA, traductor, SGA simulado y esquemas de materias y autenticación | ✅ hecha |
| 3 | Sincronización de materias y sílabos | ✅ hecha |
| 4 | Ingreso con el SGA | ✅ hecha |
| 5 | API de materias y eliminación del PDF | ✅ (incluye la 7) |
| 6 | Frontend | ✅ hecha |
| 7 | Ciencia de datos con JSON | ✅ (fusionada en la 5) |
| 8 | Equivalencia con V1 y herramienta de comparación | ✅ hecha |
| 9 | Documentación, verificación final y entrega | ✅ documentación (la verificación E2E final y el push los hace el coordinador) |

## Bloqueos

- **B-SGA1 (abierto):** TI debe definir el mecanismo de autenticación del SGA, las consultas de materias y sílabo y una cuenta o entorno de prueba. Hasta entonces se valida contra el SGA simulado.

## Decisiones

- **2026-11-09:**
  - La autenticación es la del SGA, para que el docente tenga las mismas materias que en el SGA.
  - Se elimina por completo la entrada por PDF.
  - El sistema no aprueba sílabos: consume y genera.
  - La V2 parte de una copia limpia, sin el historial de V1.
- **2026-11-09:**
  - La clave del SGA no se guarda: se sincroniza todo al ingresar.
  - El acceso lo define solo el SGA, así que se quita «compartir».
  - Un sílabo por código PF, compartido entre paralelos.
- **2026-11-09:**
  - Se elimina «compartir» (servicio, endpoints, ruta de auditoría y modelo); la tabla `asignatura_acceso` y los roles se conservan.
  - `asignatura.activa_sga` (migración `009_sga.sql`): al sincronizar, una asignatura cuya materia el SGA ya no lista queda inactiva (404 y fuera del listado); nunca se borra y vuelve si la materia regresa.
  - Una asignatura por `(docente, codigo_pf)`: dos paralelos son dos filas de `materia_sga` apuntando a la misma.
- **2026-11-09:**
  - Se elimina el SMTP por completo (`app/auth/correo.py`, campos `smtp_*`, variables en `.env.example`, `infra/`) y con él `/auth/codigo` y `/auth/verificar`; el ingreso es `POST /auth/ingresar` contra el SGA.
  - El bloqueo sigue la convención de V1: 5 claves erróneas seguidas por usuario → **429** «Demasiados intentos» con `Retry-After: 900` (no 423). Tabla `auth_bloqueo` (`010_auth_sga.sql`, con una columna `actualizado` para limpiar contadores viejos); `auth_reto` se elimina.
  - Cuotas: `limite_ingresar_usuario_minuto` (20) y `limite_ingresar_ip_minuto` (60) reemplazan las cuatro de código/verificar.
- **2026-11-09:** El contrato también define los JSON de la lista de materias y de la autenticación (Tarea 2).
- **2026-11-10 (revisión final):**
  - La migración `011_acceso_solo_sga.sql` borra las sesiones de V1 (`auth_sesion`) para forzar un ingreso por el SGA, y los accesos compartidos de V1 (`asignatura_acceso`): el acceso lo define solo el SGA. La tabla y los roles se conservan; solo la escribe un administrador en la base.
  - Presupuesto de sincronización `SGA_SINCRONIZACION_MAX_S` (45 s por omisión, menor que los 65 s del proxy): al agotarse no se piden más sílabos y las materias restantes quedan `no_disponible`, con su versión anterior y sus asignaturas activas.
  - `SGA_PROVEEDOR` pasa a `real` por omisión: el validador de `Ajustes` rechaza `simulado` en producción y, con el simulado, exige una carpeta con `usuarios.json` (relativa a la raíz).
  - El usuario llega al SGA sin pasar a minúsculas; solo el bloqueo y la cuota lo normalizan. El correo del SGA se normaliza antes de escribir nada (otro dominio → 403).

## Bitácora (lo ya hecho)

### 2026-11-09
- **Tarea 0:**
  - Se exportó V1 `011bd68` con `git archive`, sin `docs/propuestas/`, `Silabos/` ni `.env`.
  - Los planes P1–P10 quedan en V1. `progress.md` es nuevo.
  - Pruebas (`-m "not servidor and not modelo"`): 1216 pasan y 23 se saltan solo porque piden un PDF de `Silabos/`, que no se versiona (1216 + 23 = 1239, igual que V1). 14 deseleccionadas.
  - Con `.venv-ciencia`, `-m modelo` en `test_razonador.py` + `test_cd_*.py`: 10 pasan. Frontend: 25 pasan.
- **Tarea 1:** `SilaboUTI` acepta el contrato JSON (9 campos pasan a opcionales) y `app/silabo/integridad.py` añade `cargar_silabo` y `SilaboInvalido` con fallos `ruta: regla` sin valores. Pruebas: `test_contrato.py` 11 nuevas; suite estándar 1227 pasan, 23 se saltan (1216 + 11 nuevas).
- **Tarea 2:** `app/sga/` (interfaz `ProveedorSGA`, traductor de lista blanca, SGA simulado con fixtures `S91-SIMU-…`, real pendiente de TI), esquemas `materias-api` y `auth-sga` con ejemplos, y 3 campos en la configuración. Sin `jsonschema`: las pruebas leen las claves de los esquemas. Pruebas: `test_sga_proveedor.py` 22 nuevas; suite estándar 1249 pasan, 23 se saltan (1227 + 22 nuevas).
- **Tarea 3:** `app/sga/sincronizar.py` y migración `009_sga.sql` (`materia_sga`, `asignatura.activa_sga`); una transacción por materia, estados `importada/sin_cambios/no_disponible/invalida`. Se quita «compartir». Pruebas: `test_sga_sincronizar.py` 10 nuevas, 3 nuevas y 4 borradas de «compartir» en `test_asignaturas_api.py`; suite estándar 1259 pasan, 23 se saltan (1249 + 10).
- **Tarea 4:** `POST /auth/ingresar` (bloqueo → SGA → sincronización → sesión con la misma cookie de V1); la clave solo es un parámetro local (pruebas con `caplog` y búsqueda en todas las columnas de texto). Si la sincronización falla se entra igual y solo se registra el nombre de la excepción. SGA caído → 503 sin contar fallo. Se borra `test_correo_auth.py` y se reescribe `test_auth.py` (32 casos); `test_control_api.py` cambia las cuotas de código por las de ingreso. Suite estándar 1247 pasan, 23 se saltan (1259 + las nuevas − las del código por correo; la base citada era 1261).
- **Tareas 5 y 7 (fusionadas):** `GET /materias` (solo las del docente, por `codigo_pf` y `paralelo`); se borra la entrada por PDF (`POST /silabos`, `app/silabo/lector/`, `aislado.py`, `pdf_*`, `limite_pdf_correo_hora`, `lector_pdf`, `SilaboIlegible`) y `pdfplumber` sale de las dependencias de la API (queda solo en `dev` y en la etapa de pruebas de la imagen, porque las pruebas de exportación leen el PDF generado). La 7 se fusiona porque borrar el lector rompía `ciencia_datos/corpus.py`: ahora solo lee `.json` (`a_contrato` + `cargar_silabo`), ignora los `.pdf` con un aviso y su conteo. `compose.yaml` pasa `SGA_*`; nginx `client_max_body_size 1m`. Pruebas borradas: `tests/lector/` y 2 archivos de PDF más casos sueltos; nuevas: `test_materias_api.py` (4), 3 en `test_cd_corpus.py` y 1 en `test_infra_config.py`. Suite estándar: 1173 pasan, 0 se saltan, 13 deseleccionadas (eran 14: se borró `test_prompt_de_momento_cabe`, marcada `servidor`, que leía PDFs reales). Ronda de corrección 1: se rehace esa prueba con los JSON del SGA (+ variante sin servidor), se convierte `test_criterio_2_reales` y `test_materias_api.py` pasa por `sincronizar`; suite estándar 1177 pasan, 14 deseleccionadas; `modelo`: 10 pasan; `test_materias_api.py`: 4.
- **Tarea 6:** frontend con el SGA: `Ingreso` pide usuario y clave (`type=password`, la clave se borra del estado tras cada respuesta, 401/429/503 con mensajes propios en `utils/materias.ts`); `Generar` lista `GET /materias` («CODIGO PARALELO n»), abre `importada`/`sin_cambios` en su menú y muestra desactivadas `no_disponible`/`invalida` con su motivo. Se quitan `subirSilabo`, `/auth/codigo`, `/auth/verificar` y `DropZone`. Pruebas: 28 unitarias (25 − 3 retiradas + 6 nuevas), 42 de navegador (Playwright, API simulada), typecheck y build sin errores.
- **Tarea 8:** oráculo de huellas generado con el código de V1 `011bd68` (`tests/fixtures/v1/generar_oraculo.py` + `huellas_silabo_datos.json`); `test_equivalencia_v1.py`: las 59 entradas (contexto, prompt, plan, requisitos, sin IA, menú, entrenamiento, agente) del fixture pasado por `a_contrato` + `cargar_silabo` son idénticas a V1, y los 3 sílabos del SGA simulado no cambian al quitar campos privados. `app/sga/comparar.py` (`python -m app.sga.comparar <sga> <ref>`: rutas y % de coincidencia, nunca valores) con `test_sga_comparar.py` (4).
- **Tarea 9 (documentación):** `README.md` reescrito para la V2 (flujo con el SGA, modelo matemático, SGA simulado, pruebas, equivalencia y lista de documentos de V1 como historia); `docs/sga/para-TI.md` (nuevo: qué debe entregar TI y dónde se conecta el adaptador); `docs/api-silabo/README.md` con los 3 contratos, las 7 reglas y el traductor; `ciencia-datos.md`, `operacion.md`, `entrega-ti.md` y `desarrollo-api.md` sin PDF, SMTP ni código por correo; `tests/fixtures/v1/README.md` con las dos aclaraciones de la Tarea 8. Solo documentación. Suite estándar: 1185 pasan, 14 deseleccionadas. Pendientes del coordinador: verificación E2E final y push.

### 2026-11-10

- **Revisión final, ronda única de correcciones** (hallazgos en `.superpowers/sdd/2026-11-09-v2-sga-json/revision-final-hallazgos.md`): correo del SGA normalizado antes de escribir (otro dominio → 403); migración `011_acceso_solo_sga.sql` (borra `auth_sesion` y `asignatura_acceso`); materias `no_disponible`/`invalida` con asignatura se abren con la última versión importada y `estadoMateria` usa lista blanca; `SGA_SIMULADO_DIR` relativa a la raíz y arranque que falla sin `usuarios.json`; `SGA_PROVEEDOR` `real` por omisión y `simulado` rechazado en producción por `Ajustes`; presupuesto `SGA_SINCRONIZACION_MAX_S` (45 s) con reloj inyectable; usuario sin minúsculas hacia el SGA; una sola consulta de materias (`ServicioAuth.materias` eliminado); `comparar` acepta paralelos idénticos y nombra el código si difieren; `horas` del esquema con sus 4 campos obligatorios; aviso de privacidad, README, `desarrollo-api.md`, `operacion.md`, `para-TI.md`, `.env.example` y comentario de `compose` al día; `onSubir` → `onGenerar`. Pruebas: suite estándar 1202 pasan, 14 deseleccionadas (1185 + 17 nuevas); frontend 30 unitarias (28 + 2), 42 de navegador, typecheck y build sin errores. Desviación: el default de `SGA_PROVEEDOR` cambia a `real` (con `simulado` por omisión, el validador de producción rechazaría toda configuración sin la variable). Informe: `.superpowers/sdd/2026-11-09-v2-sga-json/revision-final-correcciones.md`.

---

## Siguiente paso

1. Pedir a TI lo del bloqueo B-SGA1 con [docs/sga/para-TI.md](docs/sga/para-TI.md) y escribir `app/sga/real.py` cuando respondan.
2. Verificación E2E final (Qwen real, docker compose con el SGA simulado), revisión de toda la rama y push a `Agente-GenRecursos-V2` solo con aprobación del usuario.
