# Prueba: ¿alcanza el sílabo para generar herramientas de alta calidad?

> **Estado:** en pausa desde el 2026-10-20. Se retoma al recibir la plantilla
> del área académica o sílabos de otras facultades. Plan, mejoras pendientes y
> procedimiento de trazabilidad en el spec, §16.1.

> **Fecha:** 2026-10-20 · **Modelo:** Qwen3-8B-AWQ (servidor de la universidad)
> **Scripts:** `pruebas/prueba_calidad.py` (ronda 1), `pruebas/prueba_calidad_v2.py`
> (ronda 2) y `pruebas/prueba_calidad_v3.py` (ronda 3) · **Resultados crudos:**
> `pruebas/resultados/`

## 1. Pregunta

¿Basta el sílabo, sin ningún documento de carrera (proyectos, mallas,
perfiles), para que el sistema genere herramientas de estudio de nivel
universitario, correctas y con la dificultad adecuada?

## 2. Método

| Aspecto | Detalle |
|---|---|
| Entrada | **Solo texto del sílabo**: la clase (contenidos y actividades), el RA, la evidencia del momento, los indicadores de la rúbrica, la competencia, el problema del territorio y la política de IA |
| Clases | **Análisis de Datos y Estadística** (3.er nivel), M3-S4: pruebas de hipótesis y ANOVA · **TIC en Ingeniería** (2.º nivel), M3-S1: ciberseguridad, con TAREA 3 (para probar integridad académica) |
| Herramientas | Cuestionario de 8 ítems (perfil Fundamentación: 2 receptivo, 3 resolutivo, 2 reflexivo, 1 crítico) y ficha de clase |
| Controles | Verificación determinista + revisor de IA a ciegas (opciones barajadas, sin clave) + **revisión humana ítem por ítem** |

## 3. Resultados

| Indicador | Ronda 1 | Ronda 2 |
|---|---|---|
| Ítems con pregunta bien formada | 4 / 16 | **16 / 16** |
| Ítems repetidos o casi idénticos | 7 / 16 | **0 / 16** |
| Ítems correctos y sin ambigüedad (revisión humana) | ~5 / 16 | **10 / 16** |
| Claves incorrectas o cuestionables | 4 | 2 |
| Ítems ambiguos (dos opciones defendibles) | — | 3 |
| Ítems que usan datos numéricos reales | 0 | 7 (todos correctos) |
| Revisor coincide con la clave | 13 / 16 (sin razonar) | 16 / 16 (razonando) |
| Ambigüedades detectadas por el revisor | 0 | 1 de 3 |
| Uso del caso del PIS (riesgo de resolver la tarea) | Sí (ficha de TIC) | **No** |
| Tiempo por cuestionario de 8 ítems con revisión | ~3 min | ~6 min |

### Cambios entre rondas (todos del generador, ninguno de la fuente)

1. Campo "pregunta" separado y verificado (termina en "?", no contiene opciones).
2. Un foco distinto por ítem, derivado de la clase y su rúbrica.
3. **El código calcula, la IA redacta:** en estadística, Python calcula
   Shapiro-Wilk, Levene, ANOVA, t e intervalo de confianza; el modelo solo
   redacta e interpreta. Los 7 ítems y la ficha con números quedaron
   numéricamente correctos.
4. Revisor que razona en texto libre y entrega el JSON al final (forzar JSON
   apagaba su razonamiento).
5. Casos con organizaciones ficticias distintas del PIS.

### Defectos que persisten en la ronda 2 (revisión humana)

| Ítem | Defecto |
|---|---|
| Datos D3 | Clave mal redactada ("la *media* de C no contiene…": es el *intervalo*) |
| Datos D4 | Ambiguo: "el ANOVA requiere pruebas post hoc" también es correcta |
| Datos D8 (crítico) | Clave exagerada: diferencia significativa ≠ "posible ataque" |
| TIC T2 | Ambiguo: el software de gestión también es un activo crítico |
| TIC T6 | Ambiguo (detectado por el revisor) y opción combinada |
| TIC T8 (crítico) | Clave discutible |
| Dificultad | Los ítems tienden a reconocer e interpretar; ningún ítem "crítico" exige de verdad evaluar una decisión. Los distractores de TIC son poco plausibles |

Las fichas de la ronda 2 son correctas y útiles: la de Datos recorre el
análisis completo con los números calculados; la de TIC modela el análisis de
un incidente con un caso distinto al del estudiante.

## 3b. Tercera ronda (`pruebas/prueba_calidad_v3.py`)

Mismo sílabo y mismo modelo (decisión: no se cambiará). Cambios: plantillas
por nivel (el ítem "crítico" presenta una conclusión con un error),
distractores declarados desde errores típicos, revisor que juzga cada opción
por separado razonando, y sobregeneración (12 ítems → 8 elegidos).

**Hallazgo técnico:** con el esquema más largo, la salida guiada entró en un
bucle de espacios hasta agotar los tokens. Se resolvió con
`repetition_penalty: 1.05` (2 de 2 respuestas válidas en la prueba aislada) más
reintento ante JSON inválido (hubo 2 reintentos en 12 lotes). **Esto pasa al
spec como regla de producción.**

| Indicador | Ronda 2 | Ronda 3 |
|---|---|---|
| Ítems sólidos de los 16 elegidos (revisión humana) | 10 | **8** |
| Datos / TIC | 5 / 5 | 4 / 4 |
| Ítems críticos que funcionan de verdad | 0 de 2 | 0 de 2 (el de Datos es incoherente; el de TIC es obvio) |
| Ítems que el revisor rechazó (de 24 generados) | — | 5 (1 de Datos, 4 de TIC) |
| Errores que el revisor no detectó | 2 de 3 ambigüedades | "Aceptar la hipótesis nula" como clave correcta (2 ítems) |
| Clave en la primera opción | — | 17 de 24 (sesgo de posición) |
| JSON inválido | 0 | 2 de 12 lotes (resueltos con reintento) |

**Defectos principales de la ronda 3:**

- **Datos 4 y 5:** la clave dice "aceptar la hipótesis nula", un error
  conceptual clásico (lo correcto es "no se rechaza"). Además son el mismo
  ítem: la selección eligió un duplicado marcado por la verificación.
- **Datos 8 (crítico):** el enunciado y la clave no son coherentes.
- **TIC 3 y 4:** no son preguntas (consignas sin "?"), y TIC 5 no tiene ninguna
  opción correcta (el revisor la rechazó, pero la selección la incluyó por
  falta de candidatos válidos de ese nivel).
- **TIC 8 (crítico):** técnicamente correcto pero obvio (tres opciones dicen
  "Es adecuada" para contraseñas simples).
- **Ficha de Datos:** concluye "solo la comparación entre C y A es
  significativa" sin haber hecho una prueba post hoc. La ficha de TIC es
  correcta.

**Lectura:** con Qwen3-8B, las mejoras de instrucciones llegan a un techo de
alrededor del **55 al 65 % de ítems sólidos**. Pedirle al modelo ítems de
nivel crítico (sembrar un error y construir opciones sobre él) supera lo que
hace con fiabilidad. Las fichas siguen siendo buenas, con algún matiz que el
docente debe revisar.

## 4. Veredicto

1. **El sílabo es suficiente como fuente.** Ningún defecto observado se debe a
   falta de información: el sílabo aportó tema, actividades, software, rúbrica,
   contexto y política de IA, y el modelo los usó. Un perfil de egreso o un
   proyecto de carrera no habría corregido ninguno de los fallos. **No hace
   falta solicitar documentos de carrera.**
2. **La calidad depende del tipo de herramienta.**
   - **Herramientas explicativas** (fichas, guías, tarjetas, glosario, mapas,
     repasos): buenas con Qwen3-8B desde la ronda 2.
   - **Herramientas sin IA** (hoja de ruta, autoevaluaciones con la rúbrica,
     listas de verificación): exactas por construcción.
   - **Cuestionarios y simulacros redactados por el modelo:** se estancan en
     55 a 65 % de ítems sólidos tras tres rondas; los niveles altos son los
     más débiles. No llegan a "alta calidad" solo con instrucciones.
3. **La revisión del docente es imprescindible** para cuestionarios y
   simulacros (ya prevista en el spec, §10): el revisor automático no detecta
   todos los errores.

## 5. Cómo llegar a calidad alta sin cambiar de modelo

Las rondas 2 y 3 probaron las mejoras de instrucciones (plantillas por nivel,
distractores declarados, revisor por opción, sobregeneración). Lo que sí
funcionó fue que **el código haga la parte exacta**. La propuesta es llevar
esa idea a los ítems:

| Mejora | Qué ataca | Estado |
|---|---|---|
| **Ítems paramétricos:** el código arma la decisión, la clave y los distractores desde un catálogo de errores típicos por tema (por ejemplo, "confundir no rechazar H0 con aceptarla"); el modelo solo redacta el contexto | Claves erróneas, niveles altos | Por probar |
| **Reglas de dominio por facultad** (en `agentes/<facultad>.yaml`): expresiones prohibidas en la clave correcta, como "aceptar la hipótesis nula" | Errores conceptuales que el revisor deja pasar | Por implementar |
| Barajar las opciones por código antes de publicar | Sesgo de posición (17 de 24 claves en la primera opción) | Trivial |
| Selección que descarta duplicados y rechazados, y genera más hasta completar el cupo | Ítems defectuosos elegidos por falta de candidatos | Trivial |
| `repetition_penalty: 1.05` y reintento ante JSON inválido | Bucles de espacios de la salida guiada | **Probado** |
| "El código calcula, la IA redacta" en todas las áreas cuantitativas | Precisión numérica | **Probado** en estadística |
| Plantilla del área académica | Formato y criterios institucionales | Pendiente de entrega |

**Criterio para dar la calidad por alcanzada (cuestionarios):** al menos 14 de
16 ítems sólidos en revisión humana, con al menos un ítem crítico real por
cuestionario, sobre las mismas dos clases y otras dos de facultades
distintas. Mientras no se alcance, cuestionarios y simulacros se publican como
**borrador para revisión del docente**, con las alertas del revisor visibles.

## 6. Humo del núcleo con Qwen real (2026-10-27)

Prueba `backend/tests/test_humo_servidor.py` (cuestionario de 4 ítems de M3-S4 y
ficha de M2-S1, Qwen3-8B-AWQ, ~12 min por corrida, ninguna llamada sobre
8 192 tokens). Las trazas completas, sin prompts ni razonamiento, están en
`pruebas/resultados/20261027-humo-p1*.json`.

| Corrida | Cambio | Ítems `ok` en la 1.ª revisión | Resultado final del cuestionario |
|---|---|---|---|
| 1 (`humo-p1`) | Ninguno | 1 de 4 | 1 de 4 `ok`; 3 devueltos por integridad; 1 casi duplicado |
| 2 (`-integridad`) | Criterio de integridad del revisor alineado con §9.4 regla 1 | 0 de 4 | 2 de 4 `ok`; 1 casi duplicado |
| 3 (`-entregables`) | La evidencia del momento entra en `entregables_momento`; el worker debe usar otros casos y datos; las correcciones que fallan la verificación se reintentan | 2 de 4 | 3 de 4 `ok`; 4 de 4 verificados |
| 4 (`-escenarios`) | El planificador asigna a cada ítem un escenario del perfil de la carrera y descarta los que comparten palabras clave con el entregable | 3 de 4 | **4 de 4 `ok`, `listo`**; 12 llamadas y 400 s (antes 19–24 llamadas y 680–964 s) |

**Causa raíz.** Todas las devoluciones de la corrida 1 fueron por integridad
(«resuelve el entregable…»), no por la clave. El revisor tenía razón a medias:
los ítems usaban el mismo escenario de la evidencia del M3 (tráfico normal
frente a ataques). Pero `contexto_clase` no pasaba esa evidencia como
entregable, porque solo tomaba los entregables por sesión, vacíos en este
sílabo. El worker no sabía qué caso evitar y el revisor lo deducía de la
rúbrica.

**Corrida 4.** Los casos (tienda en línea, inicio de sesión fallido, API REST y
compilación en Git) salen de `escenarios` en `agentes/ingenierias.yaml`. Solo se
devolvió el ítem del caso más cercano a seguridad, «intentos de inicio de sesión
fallidos», y quedó `ok` en la 2.ª ronda. Defectos para la fase de calidad: 3 de los
4 enunciados son «¿Qué tipo de prueba…?», y los valores críticos del ítem
reflexivo los inventa el modelo (falta «el código calcula» de §5).

**Lo que quedaba tras la corrida 3.** En la corrida 3 el revisor real también devolvió claves
dudosas (i2: «opción 4, no la 2»; i4: «opciones 2 y 4»), que es su trabajo. Un
ítem seguía en el escenario de picos de tráfico. Para variar los casos hace
falta darle al worker tipos de caso concretos distintos del entregable, junto
con las mejoras de §5 (en pausa hasta la plantilla académica).

## 7. Humo de herramientas de momento y asignatura (P3b, 2026-10-27)

Prueba `test_humo_momento` en `backend/tests/test_humo_servidor.py`, con Qwen3-8B-AWQ
real y la fixture de Datos. Traza en `pruebas/resultados/20261027-humo-p3b-momento.json`.

| Herramienta | Ámbito | Estado | Revisor de integridad | Verificador |
|---|---|---|---|---|
| Simulacro (4 ítems) | M3 | `requiere_revision` | 3/4 ítems `ok`; i3 marcado «resuelve el entregable» (H0/H1 en ANOVA) | sin fallos |
| Guía de la evidencia | M3 | `listo` | `ok` | sin fallos |
| Estudio de caso | M3 | `listo` | `ok` | sin fallos |
| Guía del producto final | asignatura | `listo` | `ok` | sin fallos |

17 llamadas en 503 s; la más grande usó 5 614 tokens (límite 8 192). La única
devolución es el mismo falso positivo de integridad que el P1 (§6): una pregunta
conceptual sobre la técnica del entregable. Con `/tokenize` real, el prompt más
grande de momento o asignatura mide 3 708 tokens. La corrida usó el código anterior
a las correcciones de la revisión, que no cambian lo generado (controles de copia,
requisitos del sílabo y contexto de asignatura sin contenidos por sesión).
