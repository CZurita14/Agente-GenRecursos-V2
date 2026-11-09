# Generador de Recursos de Estudio UTI — Especificación v1.1

> **Fecha:** 2026-10-19 · **Estado:** borrador para revisión
> **Reemplaza a:** v1.0 (2026-10-13).
> **Documentos relacionados:**
> - [mapeo-silabo.md](mapeo-silabo.md): estructura del sílabo real y modelo de
>   datos extraído. **Es la referencia del lector.**
> - [analisis-astra-ai.md](analisis-astra-ai.md): plataforma usada como
>   referencia de producto.
>
> Lo que sigue sin confirmar está marcado **[PENDIENTE]** y reunido en §14.

### Cambios frente a v1.0

| Tema | v1.0 | v1.1 |
|---|---|---|
| Sílabo de referencia | Plantilla vacía de la propuesta 2026 | **Sílabos reales del periodo B26** (formato institucional generado por sistema) |
| Unidad de generación | RA, momento o rango de semanas | **La clase (sesión)**, con momento y proyecto formativo como niveles superiores |
| Cuándo se genera | Al configurar un recurso | **Bajo demanda del docente**, eligiendo la clase en un menú por semana y día |
| Arquitectura | Un solo generador | **Orquestador + un agente por facultad** sobre un núcleo común |
| Herramientas | Orientadas al docente (rúbrica, examen A/B) | **Orientadas al estudiante**, organizadas por nivel (clase, momento, asignatura) |
| Persistencia | Sesiones temporales de 6 h | **Persistente por asignatura**, porque el docente vuelve a generar clase a clase |
| Aula virtual | Sin confirmar | **Canvas** (lo nombran los sílabos) |

---

## 1. Visión general

### 1.1 Qué hace

El docente sube el sílabo de su asignatura (proyecto formativo), **en su
versión final y aprobada**. El sistema lo lee y presenta un **menú de clases
organizado por semana y día**. Cuando el docente lo decide, elige una clase (o
un momento, o la asignatura completa) y el **agente de su facultad** genera
herramientas de estudio para sus estudiantes, alineadas con lo que el sílabo
planifica para esa clase.

El sílabo no se evalúa, no se corrige ni se modifica: se toma tal como está.

### 1.2 Principios

- **Una sola entrada:** el sílabo. No se sube ningún otro documento.
- **La IA nunca escribe HTML ni JavaScript:** llena un esquema tipado; el
  código comprueba ese esquema y dibuja el recurso de forma determinista, con
  todo el texto escapado.
- **Trazabilidad:** cada herramienta indica de qué clase, momento, RA y
  contenido del sílabo sale.
- **Apoyo, no sustitución:** las herramientas preparan al estudiante, pero
  **nunca resuelven una tarea, una PAE, una evaluación ni la evidencia de un
  momento** (§7.4).
- **Nivel universitario:** la dificultad se especifica, se planifica y se
  verifica (§5).

---

## 2. Usuarios y flujo

**Usuario del aplicativo:** el docente. **Destinatario de las herramientas:**
los estudiantes de su asignatura, de cualquier nivel de la carrera.

```text
1. Subir sílabo  →  2. Menú de clases       →  3. Elegir clase y      →  4. Revisar y      →  5. Publicar /
   (PDF)             por semana y día           herramientas             ajustar              exportar
                     (estado de cada clase)     (generar)                ítem por ítem        (Canvas, PDF, DOCX)
```

- El sílabo se sube **una vez por asignatura y periodo**. Al volver, el docente
  encuentra su menú con lo que ya generó.
- Si sube una versión nueva del mismo sílabo (mismo código de proyecto
  formativo), el menú se actualiza y las clases cuyo contenido cambió se
  marcan como "sílabo actualizado".

---

## 3. Arquitectura multiagente

### 3.1 Componentes

```text
                         ┌───────────────────────────────┐
  PDF del sílabo  ─────► │ Núcleo: lector del sílabo     │  (determinista, común)
                         └──────────────┬────────────────┘
                                        │ SilaboUTI (JSON)
                         ┌──────────────▼────────────────┐
                         │ Orquestador                    │  enruta por "Facultad"
                         └──┬───────────┬──────────────┬──┘
                            │           │              │
                  ┌─────────▼──┐  ┌─────▼──────┐  ┌────▼─────────┐
                  │ Agente     │  │ Agente     │  │ Agente       │  …uno por facultad
                  │ Ingenierías│  │ FACEAN     │  │ Educación    │  + agente general
                  └─────────┬──┘  └─────┬──────┘  └────┬─────────┘
                            └───────────┼──────────────┘
                         ┌──────────────▼────────────────┐
                         │ Núcleo: planificador, control │  (común)
                         │ de calidad, renderizadores,   │
                         │ exportadores                  │
                         └───────────────────────────────┘
```

### 3.2 Qué es común y qué es de cada facultad

| Común (núcleo, un solo código) | Propio de cada agente de facultad (configuración + conocimiento) |
|---|---|
| Lector del sílabo y modelo de datos | Carreras que cubre y su perfil de egreso |
| Menú de clases y cálculo de semanas | Vocabulario técnico y tipos de caso del área (código y datos en Ingenierías; estados financieros en FACEAN; planificaciones de aula en Educación…) |
| Esquemas de herramientas y renderizadores | Herramientas recomendadas y su orden para la facultad |
| Planificador de dificultad (§5) | Software y recursos habituales (JASP, Numiqo, Excel, simuladores…) |
| Control de calidad (§8) | Ejemplos de referencia para el prompt |
| Exportación, persistencia, registro de consumo | — |

Un agente de facultad **no es otra aplicación**: es una configuración
(`agentes/<facultad>.yaml`) más su base de conocimiento, que el orquestador
inyecta en el prompt. Una corrección en el núcleo sirve para todas las
facultades.

### 3.3 Enrutamiento

1. El lector obtiene la facultad de la portada del sílabo ("FACULTAD DE
   INGENIERIAS").
2. El orquestador la busca en el catálogo de facultades (§3.4), con
   comparación normalizada (sin tildes ni mayúsculas).
3. Si no hay coincidencia, se usa el **agente general** y se registra la
   facultad desconocida para darla de alta.

### 3.4 Catálogo de facultades y carreras

| Facultad (como aparece en el sílabo) | Carreras confirmadas | Fuente |
|---|---|---|
| FACULTAD DE INGENIERIAS | Software | Sílabos B26 |
| **[PENDIENTE]** resto de facultades | — | Sílabos que enviará el usuario |

El catálogo se completa con un sílabo real de cada facultad; no se cargan
nombres supuestos.

**Stack:** Python 3.12, FastAPI, Pydantic v2, `pdfplumber`, `reportlab`,
`python-docx`, `python-pptx`; React, TypeScript, Vite, Tailwind. Base de datos
para la persistencia (§12).

---

## 4. Lectura del sílabo

La estructura completa, los campos y los casos difíciles están en
[mapeo-silabo.md](mapeo-silabo.md). Aquí solo las reglas del lector.

### 4.1 Recepción del archivo

- Formato: **PDF del sistema institucional**, comprobado por magic bytes
  (`%PDF`), máximo 50 MB.
- PDF sin capa de texto → `422` con mensaje claro. OCR fuera de alcance.
- El archivo original se elimina tras la lectura; se conserva solo el JSON
  extraído, sin datos personales (§4.4).

### 4.2 Lectura en dos rutas

1. **Ruta principal, determinista.** Se reconoce la plantilla institucional
   (portada + secciones I–VII con sus títulos fijos) y se extraen tablas y
   etiquetas con `pdfplumber`, sin IA.
2. **Ruta de respaldo, asistida por IA.** Solo si la plantilla no se reconoce
   (por ejemplo, un formato antiguo o de posgrado). Salida forzada al mismo
   esquema y **comprobación de fidelidad**: todo RA, contenido y actividad
   extraído debe aparecer en el texto del documento, o se descarta.

### 4.3 Qué se necesita para generar

| Dato | Necesario | Si falta |
|---|---|---|
| Facultad, carrera, nombre y código del proyecto formativo | Sí | `422` |
| Al menos un momento con al menos una sesión con fecha | Sí | `422` |
| RA del momento y contenidos de la sesión | Sí | La clase aparece en el menú como "sin datos suficientes" |
| Rúbrica del momento | No | Se desactiva la autoevaluación del momento |
| Competencia del PF, problema del territorio, PIS | No | Los casos se contextualizan solo con la carrera |

Un `422` describe una limitación del lector, no un juicio sobre el sílabo.

### 4.4 Datos personales

- **No se extraen ni se guardan:** teléfono, correo, ORCID y títulos del
  docente; firmas.
- **Solo para mostrar:** nombre del docente y del coordinador. **Nunca se
  envían a la IA.**
- Los sílabos reales no se versionan en git (`Silabos/` en `.gitignore`); las
  pruebas usan copias anonimizadas.

---

## 5. Nivel universitario: reglas de dificultad

### 5.1 Escala

Se usa la escala socioformativa que trae el sílabo en cada rúbrica, alineada
con Bloom revisado:

| Nivel del sílabo | Bloom afín | Qué exige |
|---|---|---|
| Receptivo | Recordar, comprender | Reconocer, describir |
| Resolutivo | Aplicar | Usar un procedimiento en una situación nueva |
| Reflexivo | Analizar | Relacionar, explicar, diagnosticar |
| Crítico | Evaluar | Juzgar con criterios, justificar decisiones |
| Cocreativo | Crear | Diseñar, proponer, integrar |

### 5.2 Nivel objetivo

1. **Ancla en la rúbrica del momento.** Los ítems apuntan a los descriptores
   **Resolutivo a Crítico** de los indicadores del momento al que pertenece la
   clase; Receptivo solo como calentamiento y Cocreativo como reto opcional.
2. **Ajuste por nivel de la malla** (el sílabo lo trae: "2DO NIVEL", "3RO
   NIVEL"…):

| Perfil | Niveles de la malla | Receptivo | Resolutivo | Reflexivo | Crítico/Cocreativo |
|---|---|---|---|---|---|
| Fundamentación | 1–3 | 20 % | 40 % | 30 % | 10 % |
| **Profesional** | 4–7 | 10 % | 30 % | 35 % | 25 % |
| Avanzado | 8 en adelante y posgrado | 0 % | 20 % | 40 % | 40 % |

   El docente puede cambiar el perfil al generar.
3. **Techo del RA:** ningún ítem supera el nivel que el verbo del RA permite
   ("comprende" no exige Cocreativo); el excedente pasa al nivel inferior.

### 5.3 Reglas de construcción

Van en el prompt y se comprueban después (§8):

- **Contexto obligatorio desde Resolutivo:** el enunciado parte de una
  situación profesional; cuando el sílabo lo aporta, el **problema del
  territorio y el PIS** dan el contexto (por ejemplo, seguridad digital en
  Ecuador).
- **Software del sílabo:** si la clase usa una herramienta (JASP, Numiqo,
  Canvas, Git…), la práctica guiada se plantea con ella.
- **Distractores plausibles** con justificación; prohibidos "todas/ninguna de
  las anteriores".
- **Dos o más pasos de razonamiento** desde Reflexivo.
- **Respuestas abiertas con respuesta modelo** y criterios en la escala de 5
  niveles.
- **Datos ficticios declarados como tales;** no se citan fuentes que no estén
  en la bibliografía del sílabo.

### 5.4 Contenido técnico

- **Fórmulas** en LaTeX: KaTeX incrustado en HTML (sin CDN); imagen generada
  en DOCX y PDF. El lector conserva los fragmentos LaTeX del sílabo
  (`$H_0/H_1$`).
- **Código** en bloques con lenguaje declarado.
- **Tablas de datos** como bloque propio.

---

## 6. Catálogo de herramientas por nivel

Cada herramienta es un esquema Pydantic + una función de renderizado.

### 6.1 Clase (sesión) — unidad base

| Herramienta | Qué recibe el estudiante | Insumos del sílabo |
|---|---|---|
| `ficha_clase` | Guía de estudio de la clase: ideas clave, ejemplo resuelto paso a paso, errores frecuentes y relación con el RA y el proyecto | Contenidos + actividades con el docente |
| `practica_guiada` | Ejercicios graduados con solución paso a paso; con el software que indica la sesión | Actividades práctico-experimentales |
| `cuestionario` | Preguntas autocorregibles con retroalimentación por opción (opción múltiple con caso, respuesta múltiple, V/F justificado, emparejamiento, ordenamiento) | Contenidos, RA, rúbrica del momento |
| `tarjetas` | Tarjetas de conceptos y procedimientos para repaso | Contenidos |

### 6.2 Momento

| Herramienta | Qué recibe el estudiante | Insumos del sílabo |
|---|---|---|
| `repaso_momento` | Síntesis de todas las clases del momento con mapa de conceptos | Sesiones del momento |
| `estudio_caso` | Caso de práctica, distinto del caso evaluado, con preguntas escalonadas | Problema del territorio, PIS, RA |
| `simulacro` | Prueba de práctica del momento con tabla de especificaciones, tiempo sugerido y solucionario | RA y rúbrica del momento |
| `autoevaluacion_rubrica` | La rúbrica del sílabo convertida en una autoevaluación: el estudiante se ubica en cada indicador y recibe qué hacer para subir de nivel | Rúbrica del momento (no se inventa) |
| `guia_evidencia` | Orientaciones para preparar la evidencia del momento: qué se pide, criterios, errores comunes. **No la resuelve** | Evidencia, rúbrica, política de IA |

### 6.3 Asignatura (proyecto formativo)

| Herramienta | Qué recibe el estudiante |
|---|---|
| `guia_producto_final` | Hoja de ruta del producto final por momento, con criterios de la rúbrica final |
| `autoevaluacion_rubrica` | Igual que la del momento, con la rúbrica de la sección V |

### 6.4 Fase 2

`mapa_conceptual` (SVG), `presentacion` (PPTX de repaso), `repaso_terminologia`
(crucigrama, relación de columnas).

### 6.5 Fuera del catálogo

- Herramientas que dependan de un texto externo (por ejemplo, preguntas sobre
  un libro de la bibliografía): el sistema solo conoce el sílabo.
- Generación de rúbricas: el sílabo ya trae las suyas.
- Sopa de letras, hojas de Educación Inicial, conversor de PDF a HTML.

---

## 7. Menú de clases y generación

### 7.1 Menú por semana y día

El menú se construye solo a partir del sílabo, sin IA.

```text
Análisis de Datos y Estadística para Ingeniería · 3.er nivel · B26

Semana 1 · 05–11 oct
  mié 07/10  Clase 1 · Momento 1: Sensibilización y Conceptualización
             Análisis de datos unidimensionales · RA1                [Generar]
  jue 08/10  Clase 2 · Momento 1                                        ✔ 3 herramientas
             Tasas de variación e indicadores · RA1
  ── Momento 1 termina → Repaso · Autoevaluación · Guía de la evidencia  [Generar]

Semana 2 · 12–18 oct
  mié 14/10  Clase 3 · Momento 2: Planeación y Diseño
             Distribuciones estadísticas (discreta y continua) · RA2   [Generar]
             Entregable: cuestionario de probabilidad (1.ª mitad)
  …
Asignatura → Guía del producto final · Autoevaluación final             [Generar]
```

| Elemento del menú | Origen |
|---|---|
| Semana y su rango de fechas | Fecha de la sesión, contada desde el lunes de inicio del **periodo** (2026-10-05 = semana 1) |
| Día y fecha | Fecha de la sesión |
| Número de clase | Orden cronológico en la asignatura (la numeración del sílabo se reinicia en cada momento; se conserva como `M1-S2`) |
| **Título de la clase** | **Título del momento** al que pertenece + **contenidos de la sesión** como subtítulo. El sílabo no trae un título por clase; no se inventa |
| RA | RA del momento |
| Entregables | Detectados en las actividades: TAREA n, PAE n, evaluación cognitiva n |
| Estado | Sin generar · Generada (n herramientas) · Publicada · Sílabo actualizado |
| Bloques de momento y asignatura | Al cerrar cada momento y al final del menú |

Filtros: semana, momento, estado. La semana actual aparece abierta por
defecto.

### 7.2 Al generar

El docente elige, para la clase, el momento o la asignatura seleccionada:

| Parámetro | Opciones |
|---|---|
| Herramientas | Una o varias del nivel correspondiente (§6) |
| Perfil de dificultad | Sugerido por el nivel de la malla; editable |
| Cantidad | Número de ítems o extensión, dentro de los límites del esquema |
| Instrucciones adicionales | Texto libre |

### 7.3 Planificador y orquestador

- **Planificador (sin IA):** arma la tabla de especificaciones (RA × nivel)
  con los RA de la clase y el perfil, y asigna contenidos a cada casilla. Si
  dos clases tienen el mismo contenido, el planificador usa **las actividades**
  de cada sesión para diferenciarlas.
- **Contexto que recibe el agente:** asignatura, carrera, nivel, la clase
  (fecha, contenidos, actividades, software), el momento (título, RA,
  evidencia, rúbrica, política de IA), el problema del territorio y el PIS, la
  tabla de especificaciones, las reglas de §5.3 y el conocimiento de la
  facultad (§3.2).
- Uso de herramienta **forzado** al esquema; lotes de hasta 10 ítems con la
  lista de lo ya generado para evitar repeticiones.
- Proveedor de IA configurable por `LLM_PROVIDER`, respetado siempre. Sin
  clave → `503`.

### 7.4 Regla de integridad académica

Sale de la "Política de gobernanza crítica y ética de la IA" de cada momento:

1. **Nunca** se genera la solución, ni un borrador, de una tarea, una PAE, una
   evaluación o la evidencia del momento. Las herramientas trabajan los
   **mismos contenidos con otros casos y otros datos**.
2. Si la política del momento excluye la IA en una evaluación (por ejemplo,
   "evaluación individual sin asistencia de IA"), en ese momento solo se
   ofrecen herramientas de repaso de los momentos anteriores.
3. Cada herramienta publicada lleva la política de IA del momento al pie.

---

## 8. Control de calidad del recurso

Se aplica solo a lo generado, nunca al sílabo.

**Deterministas (siempre):**

1. Cumple el esquema; los ítems inválidos se descartan y se regeneran una vez.
2. Opción múltiple: exactamente una clave (o las declaradas) y opciones sin
   duplicados.
3. Cada ítem referencia una clase, un RA y un contenido que existen en el
   sílabo.
4. La distribución por RA y nivel cumple la tabla de especificaciones (±1 por
   casilla).
5. Desde Resolutivo: contexto no vacío; desde Reflexivo: dos o más pasos de
   razonamiento.
6. Sin enunciados casi duplicados, ni dentro del recurso ni con las
   herramientas ya generadas para la misma clase.

**Revisión con IA (activable):**

- Un revisor resuelve cada ítem sin ver la clave; si no coincide o hay más de
  una opción defendible → "requiere revisión".
- El revisor compara cada herramienta con los entregables de la clase y del
  momento; si una herramienta resuelve un entregable (§7.4) → bloqueada hasta
  que el docente la ajuste.

El docente ve el estado de cada ítem y puede editarlo, regenerarlo o
eliminarlo. Nada se publica sin pasar por esa pantalla.

---

## 9. Contratos de datos

- **`SilaboUTI`:** salida del lector. Esquema completo en
  [mapeo-silabo.md §3](mapeo-silabo.md).
- **`MenuClases`:**

```jsonc
{
  "proyecto_formativo": { "codigo": "B26-SOFT-3-56146-1727", "nombre": "…", "nivel": 3 },
  "agente": "ingenierias",
  "semanas": [
    {
      "numero": 1, "desde": "2026-10-05", "hasta": "2026-10-11",
      "clases": [
        {
          "id": "M1-S1", "orden": 1, "fecha": "2026-10-07", "dia": "miercoles",
          "momento": { "numero": 1, "titulo": "Sensibilización y Conceptualización - …" },
          "contenidos": ["Análisis de datos unidimensionales…"],
          "ra": ["RA1"], "entregables": [],
          "estado": "sin_generar", "herramientas": []
        }
      ],
      "cierres_de_momento": [1]
    }
  ]
}
```

- **`SolicitudGeneracion`:**

```jsonc
{
  "proyecto_formativo": "B26-SOFT-3-56146-1727",
  "ambito": { "tipo": "clase", "id": "M2-S1" },       // clase | momento | asignatura
  "herramientas": ["ficha_clase", "cuestionario"],
  "perfil": "fundamentacion",
  "cantidad": { "cuestionario": 12 },
  "instrucciones": ""
}
```

- **`Recurso`:** como en v1.0 (ítems con RA, contenido, nivel, clave,
  justificaciones y estado de calidad), más `clase_id`, `momento`, `agente` y
  `politica_ia`.

---

## 10. API HTTP

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/salud` | Estado, proveedor de IA y agentes cargados |
| `POST` | `/silabos` | Sube el sílabo; devuelve el proyecto formativo, el agente asignado y el menú |
| `GET` | `/asignaturas` | Asignaturas del docente |
| `GET` | `/asignaturas/{codigo}/menu` | Menú de clases por semana y día |
| `GET` | `/herramientas?ambito=` | Catálogo para clase, momento o asignatura |
| `POST` | `/recursos/planificar` | Tabla de especificaciones sin generar |
| `POST` | `/recursos/generar` | Genera las herramientas pedidas |
| `POST` | `/recursos/{id}/items/{item}/regenerar` | Regenera un ítem |
| `PUT` | `/recursos/{id}` | Guarda las ediciones del docente |
| `POST` | `/recursos/{id}/publicar` | Marca como publicado |
| `GET` | `/recursos/{id}/exportar?formato=` | `html`, `pdf`, `docx`, `qti` (Fase 2) |
| `GET` | `/consumo/resumen` | Uso de IA (protegido) |

Errores: `415` tipo de archivo, `422` sílabo que el lector no pudo
interpretar, `503` proveedor de IA sin configurar.

---

## 11. Entrega a los estudiantes

| Formato | Uso |
|---|---|
| **HTML autónomo** | Página para Canvas (archivo único, autocorregible, sin CDN) |
| PDF | Impresión |
| DOCX | Edición en Word |
| QTI (Fase 2) | Importar cuestionarios y simulacros a Canvas como evaluaciones de práctica |

Cada herramienta lleva al pie: asignatura, clase y fecha, RA, política de IA
del momento y la leyenda "Recurso generado con asistencia de IA y revisado
por el docente".

---

## 12. Persistencia, configuración y seguridad

- **Persistencia por asignatura** (requisito de la generación bajo demanda):
  `SilaboUTI`, menú, recursos y su estado, guardados por código de proyecto
  formativo y versión del sílabo. Base de datos relacional (SQLite en
  desarrollo, PostgreSQL en producción).
- **Acceso:** **[PENDIENTE]** inicio de sesión institucional del docente. Sin
  él, cualquiera con la URL vería las asignaturas; no se publica sin resolverlo.
- **Configuración:** `LLM_PROVIDER` y su clave, `DATABASE_URL`,
  `CORS_ORIGINS`, `REVISOR_IA`, carpeta de agentes (`agentes/*.yaml`).
- **Defectos del aplicativo anterior que no se repiten:** dependencias
  completas en `requirements.txt`; escape de todo texto en HTML, DOCX y
  ReportLab; `/consumo/*` protegido; CORS limitado a los métodos usados;
  historial de consumo fuera de git.

---

## 13. Fases y criterios de aceptación

### Fase 1 — Núcleo con el agente de Ingenierías

Lector determinista, menú de clases, persistencia, orquestador con el agente
de Ingenierías y el agente general, herramientas de clase (§6.1),
`autoevaluacion_rubrica` y `simulacro`, control de calidad, exportación
HTML/PDF/DOCX.

| # | Criterio de aceptación |
|---|---|
| 1 | Los dos sílabos de referencia se leen sin IA: 4 momentos, 11 y 6 sesiones, con fechas, horas, contenidos, RA y rúbricas idénticos al documento (verificado a mano) |
| 2 | Las filas de sesión partidas entre páginas se unen correctamente (Datos, M1-S1) |
| 3 | El menú de Datos muestra 6 semanas y el de TIC 4, con el día, la fecha, el título del momento y los contenidos de cada clase |
| 4 | Un sílabo de la Facultad de Ingenierías se enruta al agente de Ingenierías; una facultad desconocida, al agente general |
| 5 | Teléfono, correo, ORCID y nombres no aparecen en ningún prompt (prueba con cliente simulado) |
| 6 | Cuestionario de 12 ítems para una clase de 3.er nivel: cumple la tabla de especificaciones del perfil Fundamentación |
| 7 | Dos clases con el mismo contenido (Datos M2-S1 y M2-S2) producen herramientas distintas, según sus actividades |
| 8 | La autoevaluación de un momento reproduce exactamente los indicadores y descriptores de su rúbrica |
| 9 | En TIC M4 (evaluación sin IA) no se ofrecen herramientas sobre el caso evaluado; una herramienta que resuelve una tarea (caso sembrado) queda bloqueada |
| 10 | Al volver al día siguiente, el docente encuentra su menú con el estado de cada clase |
| 11 | Subir una versión nueva del mismo sílabo marca solo las clases que cambiaron |
| 12 | Instalación limpia: arranca y pasa las pruebas solo con `requirements.txt` |

### Fase 2

Agentes del resto de facultades (al recibir sus sílabos), herramientas de
§6.4, exportación QTI a Canvas, `estudio_caso` y `guia_producto_final` si no
entraron antes.

### Fuera de alcance

Evaluar, corregir o editar el sílabo; subir otros documentos; OCR; acceso de
estudiantes al aplicativo (reciben las herramientas por Canvas o en archivo).

---

## 14. Decisiones pendientes

| # | Pregunta | Supuesto actual |
|---|---|---|
| 1 | Sílabos de las demás facultades (y uno presencial) | El usuario los enviará; confirman la plantilla y completan §3.4 |
| 2 | Inicio de sesión del docente: ¿cuenta institucional (Microsoft o Google), u otro? | Requerido antes de publicar el aplicativo |
| 3 | Proveedor de IA | Configurable; medir calidad y costo con los sílabos de referencia antes de fijarlo |
| 4 | Significado del código `B26-SOFT-3-56146-1727` | Periodo, carrera, nivel y dos identificadores; se usa completo como clave |
| 5 | ¿Los estudiantes entrarán algún día al aplicativo (seguimiento, repetición espaciada, como en Astra)? | No en Fase 1: reciben las herramientas por Canvas |
| 6 | ¿Se parte del código de `Unidad-Educativa`? | Repositorio nuevo ([CZurita14/Agente-GenRecursos](https://github.com/CZurita14/Agente-GenRecursos)), reutilizando por copia los renderizadores, el patrón del orquestador y los exportadores |

---

## 15. Riesgos

| Riesgo | Mitigación |
|---|---|
| Otra facultad usa una plantilla distinta | Ruta de respaldo con comprobación de fidelidad; alta de la plantilla con su primer sílabo real |
| Herramientas que hacen la tarea del estudiante | Regla de §7.4, revisor de entregables y aprobación del docente antes de publicar |
| Claves incorrectas o ítems ambiguos | Control de calidad de §8 y edición ítem por ítem |
| El modelo baja la dificultad | Tabla de especificaciones anclada en la rúbrica y comprobación 4–5 de §8 |
| Contenido técnico inexacto en áreas especializadas | Conocimiento de cada facultad, justificaciones visibles y revisión docente |
| Exposición de datos personales del sílabo | No se guardan; los nombres nunca van a la IA; sílabos fuera de git |
| Costo por generación | Generación bajo demanda, revisor activable, consumo visible |
