# Análisis de referencia: Astra AI (preparación de exámenes)

> **Fecha del análisis:** 2026-10-13 · **Documentado:** 2026-10-19
> **Plataforma analizada:** `https://app.astra-ai.co` (sección `exam-preps`)
> **Herramienta:** REA (`rea-agents`, repositorio `morluto/rea`) observando un
> Chrome con sesión iniciada mediante el protocolo de depuración (CDP).
> **Propósito:** usar Astra como **referencia de producto y de experiencia de
> usuario** para la plataforma de apoyo al estudiante basada en sílabos. No se
> reutiliza su código, su contenido ni su API: el aplicativo se escribe desde
> cero.

---

## 1. Qué es Astra

Plataforma de estudio asistida por IA orientada al estudiante. El estudiante
arma "preparaciones" de examen por asignatura y nivel, y la plataforma genera
para cada una una ruta de estudio con lecciones, cuestionarios, tarjetas y
simulacros. Incluye además un tutor por chat, mini apps educativas,
gamificación y seguimiento de actividad.

---

## 2. Lo que quedó mapeado

### 2.1 Pantallas y navegación

| Ruta | Qué es |
|---|---|
| `/` | Chat con el tutor: preguntar, subir archivo, dibujar, teclado matemático, dictado y voz |
| `/exam-preps` | "Mi centro": mis preparaciones, próximas y pasadas |
| `/exam-preps/create` | Crear una preparación: se elige una asignatura general o se añade una propia |
| `/exam-preps/curriculum` | Plan de estudios por nivel educativo (ver 2.3) |
| `/exam-preps/official` | Catálogo de 22 exámenes oficiales (CCNA, CompTIA, IB, IELTS, USMLE, PMP…), cada uno con su lista de temas |
| `/exam-preps/school` | Preparaciones compartidas por colegio y una "partida diaria" entre compañeros |
| `/lab` | 59 mini apps educativas y un generador de apps a partir de una idea (ver 2.5) |
| `/dashboard` | Actividad: tiempo de aprendizaje de los últimos 7 días |
| `/calendar` | Calendario de eventos y exámenes |

La barra superior muestra en todas las pantallas las estrellas del día (meta
diaria, por ejemplo "0 de 50 hoy"), la racha y el perfil.

### 2.2 Lo que ofrece cada preparación

Según el diálogo de detalle (igual en plan de estudios y en exámenes oficiales):

1. Ruta de estudio creada por IA.
2. Lección inicial de diagnóstico.
3. Cuestionarios.
4. Tarjetas de memoria.
5. Pódcasts.
6. Exámenes orales.
7. Repetición espaciada.
8. Detección de puntos débiles.
9. Simulacro de examen completo, sin ayuda de IA.

### 2.3 Jerarquía de contenido

```text
Asignatura + nivel educativo
  └── Preparación (plan de estudios, examen oficial o propia)
        └── Temas numerados (bloques)
              └── Recursos: lección, cuestionario, tarjetas, simulacro…
```

Ejemplos observados:

- **Plan de estudios "Matemáticas, 1.º de universidad"**, 7 bloques:
  Fundamentos Matemáticos y Lógica · Álgebra Lineal · Cálculo Diferencial e
  Integral · Ecuaciones Diferenciales · Probabilidad y Estadística ·
  Matemáticas Discretas y Computacionales · Análisis Numérico y Optimización.
- **Examen oficial CCNA**, 6 temas ("1.0 Network Fundamentals" a "6.0
  Automation and Programmability").
- **Creación de una preparación**: 14 asignaturas generales (Matemáticas,
  Física, Química, Informática, Inglés, Alemán, Español, Francés, Biología,
  Geografía, Historia, Economía, Filosofía, Psicología) o "Añade tu asignatura".

### 2.4 API (nombres de procedimientos, estilo tRPC)

Extraídos del código de las pantallas. Solo se conocen los nombres, no los
campos que reciben o devuelven.

| Grupo | Procedimientos |
|---|---|
| `examPrep.management` | `list`, `getPageData`, `getNextExamPrep`, `leave`, `reviewMaterials`, `generateTextFileTitle`, `listSchoolSubjects` |
| `examPrep.curriculum` | `getOrCreateCurriculum`, `canExamPrepCurriculumBeCreated` |
| `examPrep.*` | `officialExams`, `sharing`, `onboardingDrafts` |
| `subjects` | `list`, `add`, `search`, `popular` |
| Gamificación | `stars`, `streak`, `badges`, `league`, `challenges` |
| Límites y pagos | `usage`, `limits`, `subscriptions` (incluye `createPaymentSession`) |
| Cuenta | `profile.getProfile`, `relations.getRelatedUsers` |
| Otros | `banners.list`, `appVersion.checkForUpdates`, `pushNotifications.reportOpen` |

`reviewMaterials` y `generateTextFileTitle` indican que, al crear una
preparación propia, el estudiante sube materiales y la plataforma los revisa y
titula. **Es el flujo más parecido a subir un sílabo.**

### 2.5 Mini apps (`/lab`)

- 59 apps: 35 simulaciones, 16 minijuegos y 8 herramientas.
- Por asignatura: Matemáticas 27, Física 16, Química 6, Biología 4, Inglés 2,
  General 4.
- Ejemplos: Atlas del Cuerpo Humano, Célula 3D, Sistema Solar, Laboratorio
  Virtual, Taller de cohetes, Puertas Lógicas, Sudoku, Nonograma, Verbos
  irregulares, Sala de escape, Temporizador Pomodoro, Ajedrez.
- Valoraciones y número de usos públicos por app, y "Crea tu propia app" a
  partir de una idea.

### 2.6 Stack y servicios

- Next.js con React, compilado con Turbopack, servido desde Vercel.
- API por procedimientos con nombre (`router.procedimiento`), al estilo tRPC.
- Analítica y errores: PostHog y Sentry; píxeles de Meta y TikTok.
- Modelo de usuarios: estudiantes, padres vinculados para seguir el progreso, y
  suscripciones de pago con códigos de promoción.

---

## 3. Lo que no quedó mapeado

| Pendiente | Por qué importa | Cómo cerrarlo |
|---|---|---|
| Interior de una preparación: ruta, lección, cuestionario, tarjetas, simulacro | Referencia de experiencia de usuario para nuestras pantallas principales | Recorrido corto dentro de una preparación |
| Creación con materiales propios (`reviewMaterials`) | Es el equivalente directo a subir un sílabo | Crear una preparación subiendo un sílabo real |
| Chat y mini apps por dentro | Referencia para el tutor y para recursos interactivos | La captura se cortó por falta de memoria del equipo; baja prioridad |
| Forma de los datos de la API | Solo se conocen nombres de procedimientos | No se necesita: el modelo de datos propio sale del sílabo |

Unirse a una preparación o crear una queda registrado en la cuenta y puede
consumir el cupo del plan gratuito, por eso no se hizo de forma automática.

---

## 4. Qué se toma para nuestra plataforma

Diferencia de fondo: **en Astra el estudiante arma su preparación; en nuestra
plataforma el docente sube el sílabo aprobado y todos los estudiantes de la
asignatura reciben recursos alineados con él.**

| En Astra | En nuestra plataforma |
|---|---|
| Asignatura + nivel | Asignatura del sílabo, con carrera, facultad y nivel de la malla |
| Preparación | Curso generado a partir de un sílabo |
| Temas numerados | Unidades, momentos o resultados de aprendizaje del sílabo, ordenados por su cronograma |
| Ruta de estudio por IA | Ruta construida desde la planificación del sílabo |
| Lección de diagnóstico | Diagnóstico inicial por resultado de aprendizaje |
| Cuestionarios y tarjetas | Cuestionarios y tarjetas con nivel universitario (ver spec, §5) |
| Simulacro sin IA | Simulacro por unidad o parcial |
| Repetición espaciada y puntos débiles | Seguimiento por tema a partir de los errores del estudiante |
| Calendario | Fechas de evaluación del sílabo en el calendario del estudiante |
| Tutor por chat | Tutor con el sílabo y los recursos del curso como contexto |
| Pódcasts, examen oral, gamificación, mini apps | Para fases posteriores |

---

## 5. Evidencia y privacidad

- Las capturas en bruto de REA (27 archivos JSON, unos 4,5 MB) **no se
  incluyen en el repositorio**: se tomaron con una sesión iniciada en Astra y
  pueden contener datos de la cuenta.
- Quedaron en la carpeta temporal de la sesión del 2026-10-13, que puede
  borrarse en cualquier momento. Este documento es el registro que se conserva.
- El análisis se limitó a pantallas, textos visibles y nombres de
  procedimientos. No se descargaron contenidos de la plataforma ni se usó su
  API.
