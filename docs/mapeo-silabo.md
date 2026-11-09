# Mapeo del sílabo UTI → unidades de generación

> **Fecha:** 2026-10-19 · **Estado:** propuesta para aprobar
> **Fuentes analizadas** (carpeta `Silabos/`, fuera de git):
>
> | Archivo | Proyecto formativo | Nivel | Créditos / horas | Momentos | Sesiones |
> |---|---|---|---|---|---|
> | `silabo_Datos_Software-signed.pdf` (10 pág.) | Análisis de Datos y Estadística para Ingeniería | 3.º | 3 / 144 h | 4 | 11 |
> | `TIC-Ingenieria.pdf` (15 pág.) | Tecnologías de la Información en Ingeniería | 2.º | 2 / 96 h | 4 | 6 |
>
> Ambos: Facultad de Ingenierías, carrera Software, periodo B26, modalidad en
> línea. **Falta confirmar con una facultad distinta y con modalidad
> presencial.**

---

## 1. Conclusión

1. **El sílabo es un documento generado por un sistema institucional** (pie:
   "Generado por <usuario> el <fecha>"), con la misma plantilla en los dos
   casos. Se puede leer con reglas fijas, sin IA.
2. **La unidad de generación es la sesión (clase).** El sílabo la trae
   explícita, con fecha, actividades, horas y contenidos.
3. **La semana se calcula a partir de la fecha de cada sesión** y sirve como
   vista para el estudiante.
4. **El momento agrupa sesiones** y aporta el resultado de aprendizaje, la
   evidencia y la rúbrica de 5 niveles: es la base de las herramientas
   integradoras.

```text
Proyecto formativo (asignatura de un nivel de una carrera)
 ├── Momento 1…N          RA, evidencia, rúbrica 5 niveles, recursos, política de IA
 │    └── Sesión 1…M      fecha → semana del periodo; actividades; contenidos
 └── Producto final        rúbrica de la evidencia central (sección V)
```

---

## 2. Estructura del documento

Las siete secciones siempre aparecen en el mismo orden (portada + I–VII).

| Sección | Campos | Uso en el aplicativo |
|---|---|---|
| Portada | Facultad, carrera, periodo (código, inicio, fin), proyecto formativo, código, versión y fecha de aprobación, docente | Enrutar al agente de la facultad; identificar la asignatura |
| I. Perfil del docente | Nombre, títulos, teléfono, correo, ORCID, experiencia | **No se usa ni se envía a la IA** (datos personales) |
| II. Presentación | Nombre, unidad de organización curricular, créditos, horas (total, contacto, autónomo, práctico), nivel, modalidad, nivel de formación, horario, prerrequisitos, correquisitos | Nivel de la malla → perfil de dificultad; horario → calendario |
| III. Mapa de formación | Competencia del perfil de egreso, competencia del PF, metacompetencia (marcada con X), habilidades blandas, ejes transversales, inclusión, **RA con su evidencia**, contribución al perfil, **problema del territorio**, pregunta o reto, **producto final**, PIS y su aporte, metodologías activas | Contexto de los casos y ejercicios; RA como eje de trazabilidad |
| IV. Momentos | Por momento: título, fechas, RA, evidencia, **tabla de sesiones**, recursos, política de IA, **rúbrica** | Unidades de generación (§3) |
| V. Evaluación | Rúbrica del producto final (indicadores × 5 niveles) | Herramientas de preparación del producto final |
| VI. Bibliografía | Básica y complementaria (referencia + enlace) | Solo se cita; no se inventa su contenido |
| VII. Firmas | Docente y coordinador | **No se usa** |

### 2.1 Tabla de sesiones (el corazón del mapeo)

| Columna | Contenido observado | Campo |
|---|---|---|
| Sesión – fecha | "Sesión 1 07/10/2026" | `numero`, `fecha` |
| Actividades con el docente + Horas | Clase sincrónica y, dentro de la misma celda, "Otras actividades con el docente (N h): …" (a veces marcadas "(A. asincrónica)") | `docente.sincronica`, `docente.asincronica`, horas de cada una |
| Actividades práctico-experimentales + Horas | Prácticas en software (JASP, Numiqo) o entregables "PAE n – …" | `practico` |
| Trabajo autónomo + Horas | Tareas "TAREA n – …" o avance del proyecto | `autonomo` |
| Contenidos | Lista con viñetas, 1 a 3 por sesión | `contenidos[]` |

Al final de cada tabla hay una fila "Total" con las horas del momento.

### 2.2 Rúbrica de cada momento

- Encabezado: evidencia del momento + texto completo de los RA asociados.
- Filas: indicadores (3 a 5), a veces numerados con una descripción entre
  paréntesis.
- Columnas: **Receptivo · Resolutivo · Reflexivo · Crítico · Cocreativo**.

---

## 3. Modelo de datos extraído

```jsonc
{
  "facultad": "FACULTAD DE INGENIERIAS",
  "carrera": "SOFTWARE",
  "periodo": { "codigo": "B26", "inicio": "2026-10-05", "fin": "2027-03-01" },
  "proyecto_formativo": {
    "nombre": "ANALISIS DE DATOS Y ESTADISTICA PARA INGENIERIA",
    "codigo": "B26-SOFT-3-56146-1727",
    "version": "1.0", "aprobado": "2026-10-06",
    "uoc": "TITULACION", "nivel": 3, "modalidad": "EN LINEA",
    "creditos": 3.0,
    "horas": { "total": 144, "contacto": 72, "autonomo": 24, "practico": 48 },
    "horario": [ { "dia": "miercoles", "inicio": "20:00", "fin": "20:59" } ]
  },
  "competencia_perfil": "…", "competencia_pf": "…",        // puede venir vacía
  "metacompetencia": "Pensamiento sociocrítico y sistémico…",
  "resultados_aprendizaje": [ { "id": "RA1", "texto": "…", "evidencia": "…" } ],
  "problema": { "descripcion": "…", "reto": "…", "producto_final": "…" },
  "pis": { "nombre": "…", "aporte": "…" },
  "metodologias": ["Clase Invertida", "ABP", "Aprendizaje Cooperativo"],
  "momentos": [
    {
      "numero": 1, "titulo": "Sensibilización y Conceptualización - …",
      "fecha_inicio": "2026-10-07", "fecha_fin": "2026-10-08",
      "ra": ["RA1"], "evidencia": "…",
      "recursos": "…", "politica_ia": "…",
      "rubrica": [ { "indicador": "…", "niveles": { "receptivo": "…", "resolutivo": "…",
                    "reflexivo": "…", "critico": "…", "cocreativo": "…" } } ],
      "sesiones": [
        {
          "id": "M1-S1", "numero": 1, "fecha": "2026-10-07",
          "semana_periodo": 1,                                // calculada
          "docente":   { "texto": "…", "horas": 6.0,
                         "asincronica": { "texto": "…", "horas": 5.0 } },
          "practico":  { "texto": "…", "horas": 4.0 },
          "autonomo":  { "texto": "…", "horas": 2.0 },
          "contenidos": ["Análisis de datos unidimensionales. Tasas de variación e indicadores."],
          "entregables": []                                   // detectados: TAREA n, PAE n, evaluación cognitiva n
        }
      ]
    }
  ],
  "rubrica_producto_final": [ /* igual que la de momento */ ],
  "bibliografia": { "basica": ["…"], "complementaria": ["…"] }
}
```

**Campos calculados por el lector (no están escritos en el sílabo):**

| Campo | Regla |
|---|---|
| `semana_periodo` | Semanas desde el lunes de inicio del periodo (2026-10-05 = semana 1). Se usa la semana **del periodo**, no la de la asignatura, para que el estudiante vea todas sus asignaturas en la misma semana |
| `id` de sesión | `M<momento>-S<sesión>`; la numeración del sílabo se reinicia en cada momento |
| `entregables` | Detección de "TAREA n", "PAE n" y "EVALUACIÓN COGNITIVA n" en las actividades |
| `horario` | Separación de "Miércoles 20:00 a 20:59" en día y horas |

---

## 4. Los dos sílabos mapeados

### 4.1 Análisis de Datos y Estadística para Ingeniería (3.er nivel)

| Semana | Sesión | Fecha | Momento / RA | Contenidos | Entregable |
|---|---|---|---|---|---|
| 1 | M1-S1 | mié 07/10 | M1 · RA1 | Datos unidimensionales; tasas de variación e indicadores | — |
| 1 | M1-S2 | jue 08/10 | M1 · RA1 | (mismos) | — |
| 2 | M2-S1 | mié 14/10 | M2 · RA2 | Distribuciones estadísticas (discreta y continua) | Cuestionario (1.ª mitad) |
| 2 | M2-S2 | jue 15/10 | M2 · RA2 | Distribuciones (multidimensional, Teorema de Bayes) | Cuestionario (final) |
| 3 | M3-S1 | mié 21/10 | M3 · RA3 | Estimación de parámetros (intervalos de confianza) | — |
| 3 | M3-S2 | jue 22/10 | M3 · RA3 | Parámetros estadísticos | — |
| 4 | M3-S3 | mié 28/10 | M3 · RA3 | Hipótesis de grupos (H0/H1, supuestos) | — |
| 4 | M3-S4 | jue 29/10 | M3 · RA3 | Hipótesis estadísticas (pruebas t, ANOVA) | — |
| 5 | M4-S1 | mié 04/11 | M4 · RA4 | Predicciones (regresión múltiple) | — |
| 5 | M4-S2 | jue 05/11 | M4 · RA4 | Predicciones (clasificación, series temporales) | — |
| 6 | M4-S3 | mié 11/11 | M4 · RA4 | Estadística no paramétrica; socialización | Portafolio final |

### 4.2 Tecnologías de la Información en Ingeniería (2.º nivel)

| Semana | Sesión | Fecha | Momento / RA | Contenidos | Entregable |
|---|---|---|---|---|---|
| 1 | M1-S1 | jue 08/10 | M1 · RA1, RA2 | Panorama de las TI en ingeniería; software y hardware; aplicaciones | TAREA 1 (infografía) |
| 2 | M2-S1 | jue 15/10 | M2 · RA2, RA3 | Evaluación y selección de soluciones TI; casos de estudio | TAREA 2 (matriz) |
| 2 | M2-S2 | vie 16/10 | M2 · RA2, RA3 | (ídem) + aplicaciones de las TI | PAE 1; evaluación cognitiva 1 |
| 3 | M3-S1 | jue 22/10 | M3 · RA2, RA3 | Ciberseguridad en ingeniería; casos de estudio | TAREA 3 (incidente) |
| 3 | M3-S2 | vie 23/10 | M3 · RA2, RA3 | Ciberseguridad; aspectos éticos y legales; tendencias | PAE 2; evaluación cognitiva 2 |
| 4 | M4-S1 | jue 29/10 | M4 · RA1–RA3 | Integración de los anteriores | TAREA 4; evaluación individual **sin IA** |

---

## 5. Qué genera el agente en cada nivel

| Nivel | Herramientas para el estudiante | Insumos del sílabo |
|---|---|---|
| **Sesión** (unidad base) | Ficha de estudio de la clase · ejercicios o práctica guiada (por ejemplo, en JASP) · cuestionario de comprobación · tarjetas de conceptos | Contenidos **y actividades** de la sesión (las actividades distinguen dos sesiones con el mismo contenido), RA del momento, recursos y software indicados |
| **Semana** (vista) | Agrupa las sesiones de la semana de todas las asignaturas del estudiante; repaso semanal opcional | Fechas |
| **Momento** | Repaso integrador · simulacro · **autoevaluación con la rúbrica** (el estudiante se ubica entre Receptivo y Cocreativo en cada indicador) · guía de apoyo para la evidencia del momento | RA, evidencia, rúbrica, política de IA |
| **Proyecto formativo** | Guía de preparación del producto final y autoevaluación con su rúbrica | Sección V, problema del territorio, PIS |

**Reglas que salen directamente del sílabo:**

1. **La política de IA de cada momento manda.** Las herramientas preparan al
   estudiante, pero **nunca resuelven una tarea, una PAE, una evaluación ni
   la evidencia del momento.** Si el momento dice "evaluación individual sin
   asistencia de IA", el agente solo genera material de repaso previo, no
   material sobre el caso evaluado.
2. **La dificultad se ancla en la rúbrica.** Los ejercicios apuntan a los
   niveles Resolutivo a Crítico de los indicadores del momento, y el nivel de
   la malla (2.º, 3.º…) ajusta el punto de partida.
3. **Las herramientas de una sesión se publican antes de su fecha**, para
   apoyar la clase invertida que declaran ambos sílabos.

---

## 6. Casos que el lector debe resolver

| Caso | Dónde aparece | Tratamiento |
|---|---|---|
| Fila de sesión partida entre dos páginas | Ambos | Una fila sin "Sesión N – fecha" continúa la anterior |
| "Otras actividades con el docente (N h)" dentro de la celda del docente | Ambos | Separarla como actividad asincrónica con sus horas |
| Momento con varios RA | TIC (M1: RA1, RA2) | `ra` es una lista |
| Columnas con 0 horas o vacías | TIC | Campo vacío, sin error |
| Campo obligatorio vacío | TIC: "Competencia específica del PF" | Se acepta vacío |
| Texto en mayúsculas sostenidas | TIC | Se conserva para mostrar; se normaliza solo para comparar |
| Fragmentos LaTeX (`$H_0/H_1$`, `$Z$`) | Datos | Se conservan y se dibujan como fórmulas |
| Texto de actividad que empieza a mitad de frase ("sobre el uso de…") | Datos | Se toma tal cual |
| Mismo contenido en varias sesiones | Ambos | Se diferencia la sesión por sus actividades |
| "Pregunta o reto" con texto que no es una pregunta | TIC | Se toma tal cual |
| PDF firmado electrónicamente o sin firmar | Datos firmado, TIC no | Indiferente para la lectura |
| Datos personales (teléfono, correo, ORCID, nombres) | Ambos | Se excluyen antes de cualquier llamada a la IA |

**Por confirmar al construir el lector:** que el PDF tenga capa de texto
seleccionable (todo indica que sí, porque es generado) y que las tablas se
extraigan bien con `pdfplumber`.

---

## 7. Pendiente

1. **Un sílabo de otra facultad** (idealmente presencial) para confirmar que
   la plantilla es institucional.
2. **Interpretar el código** `B26-SOFT-3-56146-1727`: parece periodo, carrera,
   nivel y dos identificadores; falta confirmarlo.
3. **Cuándo se genera:** todas las sesiones al subir el sílabo, o cada sesión
   cuando el estudiante la abre (o unos días antes de su fecha).
4. **Aula virtual:** ambos sílabos usan **Canvas** (evaluaciones cognitivas,
   retroalimentación). Queda resuelta la duda del LMS del spec (§11 y §14).
