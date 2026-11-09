# Generador de Recursos Didácticos UTI — Especificación v1.0

> **Fecha:** 2026-10-13 · **Estado:** borrador para revisión
> **Origen:** adaptación del aplicativo "Plataforma Pedagógica UEI" (repositorio
> `Unidad-Educativa`, rama `Rama_de_test`) al contexto de la Universidad
> Indoamérica.
> **Supuestos sin confirmar:** están marcados con **[SUPUESTO]** y reunidos en
> la sección 14. Ninguno bloquea el diseño, pero varios cambian el alcance.

---

## 1. Visión general

### 1.1 Qué hace

Un docente universitario sube **un solo archivo**: el sílabo de su asignatura,
**en su versión final y aprobada**. El sistema lo lee, entiende su estructura
(resultados de aprendizaje, contenidos, planificación) y usa esos contenidos
para elaborar **herramientas de apoyo al aprendizaje de los estudiantes**, de
nivel universitario: bancos de reactivos, estudios de caso, talleres, exámenes
de práctica y otros recursos.

El sílabo no se evalúa, no se corrige ni se modifica: el sistema lo toma tal
como está.

### 1.2 Cambios frente al aplicativo de la Unidad Educativa

| Aspecto | Unidad Educativa (anterior) | Universidad (este spec) |
|---|---|---|
| Documentos de entrada | Dos documentos | **Solo el sílabo.** No se sube ningún otro documento |
| Juicio sobre los documentos | Veredictos y bloqueo de la generación | **Ninguno.** El sílabo llega aprobado y se usa tal cual |
| Trabajo sobre el sílabo | Extraer semanas y temas para compararlos | **Leerlo y entenderlo**: de ahí sale todo lo que se genera |
| Unidad de planificación | Semana (formato VRPA) | Resultado de aprendizaje, momento/unidad y semana |
| Fuente del contenido | Tema semanal y subtemas | RA + contenidos (conceptuales, procedimentales, actitudinales) + problema/reto |
| Nivel de las herramientas | Primaria y secundaria; recuerdo y práctica | **Educación superior; aplicación, análisis, evaluación y creación** |
| Herramientas | Crucigrama, sopa de letras, flashcards, cuestionario | Banco de reactivos con casos, estudio de caso, rúbrica, taller, examen (ver §6) |
| Conversor PDF → HTML | Sí (módulo Generador) | Fuera de alcance |
| Hojas de Educación Inicial | Planificadas (Fase 2) | Fuera de alcance |

### 1.3 Lo que se conserva

- **Principio rector:** la IA nunca escribe HTML ni JavaScript. Llena un esquema
  tipado; el código comprueba ese esquema y dibuja el recurso de forma determinista, con
  todo el texto escapado.
- Arquitectura backend/frontend, patrón de herramientas (esquema + función de
  renderizado), exportadores, registro de consumo de IA, subida segura de
  archivos.

### 1.4 Propiedades del sistema

- **Una entrada, sin cruces:** el sílabo es la única fuente de verdad.
- **El sílabo es de solo lectura:** el sistema muestra lo que entendió del
  documento (§4.4), pero no permite cambiar su contenido.
- **Trazabilidad:** cada elemento generado indica a qué RA y a qué contenido
  del sílabo responde.
- **Sin base de datos ni cuentas en v1.0:** sesiones temporales en disco
  **[SUPUESTO]**.

---

## 2. Usuarios y flujo

**Usuario:** docente de grado o posgrado de la Universidad Indoamérica.

```text
1. Cargar sílabo  →  2. Resumen del sílabo  →  3. Configurar recurso  →  4. Ajustar el recurso  →  5. Exportar
   (.docx / .pdf)      (solo lectura)          alcance + herramienta     ítem por ítem             DOCX / PDF /
                                               + nivel cognitivo         regenerar parciales       HTML / PPTX
```

Desde el paso 5 el docente puede volver al 3 y generar otro recurso con el
mismo sílabo, sin subirlo de nuevo.

---

## 3. Arquitectura lógica

```text
┌──────────────┐  multipart   ┌───────────────────────────────────────────────┐
│  FRONTEND    │  1 archivo   │  BACKEND (FastAPI)                             │
│  React+Vite  │ ───────────► │  A. Recepción del archivo (tipo y tamaño)      │
│              │              │  B. Extracción de texto y tablas (docx / pdf)  │
│  5 pasos     │              │  C. Lector de sílabo                           │
│              │              │     C1. Plantilla conocida (determinista)      │
│              │ ◄─────────── │     C2. Extracción asistida por IA (respaldo)  │
│              │    JSON      │  D. Planificador de recurso (tabla de espec.)  │
│              │              │  E. Orquestador de generación (IA → esquema)   │
│              │              │  F. Control de calidad del recurso             │
│              │              │  G. Renderizadores deterministas               │
│              │              │  H. Exportadores (DOCX, PDF, HTML, PPTX)       │
└──────────────┘              └───────────────────────────────────────────────┘
```

D, F y G son lógica pura y se prueban sin red. C2 y E reciben el cliente de IA
por inyección para poder simularlo en las pruebas.

**Stack:** el mismo del aplicativo anterior (Python 3.12, FastAPI, Pydantic v2,
`python-docx`, `pdfplumber`, `reportlab`, `python-pptx`; React, TypeScript,
Vite, Tailwind). Se añade `python-docx` también para **escribir** DOCX.

---

## 4. Lectura del sílabo

### 4.1 Recepción del archivo

Comprobaciones técnicas para poder abrir el archivo; no dicen nada sobre el
contenido del sílabo.

- Formatos: `.docx` y `.pdf`, comprobados por magic bytes (`PK\x03\x04`,
  `%PDF`), no por extensión. Máximo 50 MB.
- PDF escaneado (menos de 50 caracteres de texto en la primera página) →
  rechazo `422` con mensaje claro. OCR fuera de alcance.
- El archivo se guarda con nombre aleatorio y se elimina al expirar la sesión.

### 4.2 Formatos de sílabo soportados

No existe todavía un sílabo universitario real lleno para calibrar el lector.
La referencia disponible es la plantilla de la "Propuesta técnica para el nuevo
sílabo de Proyecto Formativo" (UTI, agosto 2026), cuya estructura es:

| Sección de la plantilla | Qué aporta a la generación |
|---|---|
| 7.1 Información general | Nombre y código del proyecto formativo, carrera, nivel de la malla, modalidad, créditos, horas |
| 7.2 Anclaje curricular | Competencia específica del perfil, desempeño profesional central, metacompetencia |
| 7.3 Problema, reto y producto | Problema del territorio, pregunta reto, producto integrador, escenario |
| 7.4 Resultados de aprendizaje | RA1–RA4, evidencia por RA, momento en que se evalúa |
| 7.5 Contenidos | Mínimos oficiales; conceptuales, procedimentales y actitudinales |
| 7.6 Planeación por momentos | Por momento: semanas, RA asociados, propósito, actividades, evidencia, contenidos, política de IA |
| 7.7 Evaluación socioformativa | Escala institucional de 5 niveles; criterios, pesos e instrumentos por RA |
| 7.8 Recursos y bibliografía | Bibliografía básica y complementaria |

**Estrategia de lectura en dos rutas:**

1. **C1 — Plantilla conocida (determinista).** Si el documento contiene las
   etiquetas de la plantilla 2026 (por ejemplo "Nombre del Proyecto Formativo",
   "Resultado de aprendizaje", "Momento N."), se extrae por tablas y etiquetas,
   sin IA. Las celdas fusionadas de Word se deduplican por identidad del
   elemento XML, igual que en el lector anterior.
2. **C2 — Extracción asistida por IA (respaldo).** Si no se reconoce la
   plantilla, o si C1 deja vacíos los campos obligatorios, se envía el texto y
   las tablas del documento a la IA con salida forzada al esquema
   `SilaboUniversitario`. Cubre sílabos del formato anterior, de posgrado o de
   otras facultades **[SUPUESTO: hay más de un formato en circulación]**.

**Fidelidad de la lectura:** en la ruta C2 el modelo solo puede transcribir.
El código comprueba que cada RA y cada contenido leído aparezca en el texto del
documento (comparación normalizada, sin tildes ni mayúsculas); lo que no
aparezca se descarta, para que nada de lo que se use en la generación sea
ajeno al sílabo.

### 4.3 Qué se necesita del sílabo para generar

| Dato | Necesario | Si el lector no lo encuentra |
|---|---|---|
| Nombre de la asignatura o proyecto formativo | Sí | Se reintenta con la ruta C2 |
| Al menos 1 resultado de aprendizaje | Sí | Se reintenta con la ruta C2 |
| Al menos 1 contenido o tema | Sí | Se reintenta con la ruta C2 |
| Carrera, nivel, modalidad | No | Se generan recursos sin ese ajuste |
| Planeación por momentos o semanas | No | El alcance se elige solo por RA o por contenido |
| Evaluación, problema/reto | No | Se desactivan las herramientas que dependen de ello |

Si tras las dos rutas no se obtiene ningún RA ni ningún contenido → `422`
("No se pudo leer la estructura de este sílabo"). Es una limitación del lector,
no un juicio sobre el documento; el caso se registra para ampliar los formatos
soportados.

### 4.4 Resumen del sílabo (solo lectura)

Tras la carga, el docente ve lo que el sistema entendió: datos generales,
resultados de aprendizaje, contenidos por tipo y momentos o unidades con sus
semanas. Sirve para dos cosas: confirmar de un vistazo que se cargó el sílabo
correcto y **elegir desde ahí el alcance** del recurso (§7.1).

El contenido no se puede editar. Si el resumen no refleja el documento, el
docente puede pedir una nueva lectura con la ruta C2; no hay ingreso manual de
datos.

### 4.5 Datos personales

- El nombre del docente, de coordinadores y las firmas se extraen solo para
  mostrarlos en pantalla y en los encabezados de exportación. **No se envían a
  la IA.**
- Si el sílabo incluye una sección de necesidades educativas específicas con
  nombres de estudiantes, esos nombres se reemplazan por seudónimos antes de
  cualquier uso, como en el aplicativo anterior.

---

## 5. Nivel universitario: reglas de dificultad

Este es el cambio de fondo frente al aplicativo anterior. La dificultad no se
deja a criterio del modelo: se **especifica, se planifica y se verifica**.

### 5.1 Niveles cognitivos

Se usa la taxonomía de Bloom revisada, alineada con la escala socioformativa
institucional del sílabo UTI:

| Nivel cognitivo | Qué exige al estudiante | Nivel socioformativo UTI afín |
|---|---|---|
| Recordar | Reconocer o definir | 1. Receptivo |
| Comprender | Explicar, interpretar | 1. Receptivo |
| Aplicar | Usar un procedimiento en una situación nueva | 2. Resolutivo |
| Analizar | Descomponer, relacionar, diagnosticar causas | 3. Reflexivo |
| Evaluar | Juzgar con criterios, decidir entre alternativas | 4. Crítico |
| Crear | Diseñar, proponer una solución original | 5. Cocreativo |

### 5.2 Nivel objetivo

1. **Punto de partida: el verbo del RA.** Cada RA se clasifica por su verbo
   principal ("identifica" → Recordar; "diseña" → Crear). Esa clasificación es
   el **techo esperado** del RA y se muestra al docente, que puede cambiarla.
2. **Piso universitario.** Por defecto ningún recurso tiene más del **20 %** de
   sus ítems en Recordar/Comprender, y al menos el **50 %** está en Analizar o
   superior. El docente puede mover la distribución con tres perfiles:

| Perfil | Recordar/Comprender | Aplicar | Analizar | Evaluar/Crear |
|---|---|---|---|---|
| Fundamentación (primeros niveles de la malla) | 20 % | 40 % | 30 % | 10 % |
| **Profesional (por defecto)** | 10 % | 30 % | 35 % | 25 % |
| Avanzado (últimos niveles, posgrado) | 0 % | 20 % | 40 % | 40 % |

3. **Sugerencia automática del perfil** según el nivel de la malla del sílabo:
   niveles 1–3 → Fundamentación; 4–7 → Profesional; 8 en adelante y posgrado →
   Avanzado. El docente siempre puede cambiarlo.

### 5.3 Reglas de construcción por nivel

Estas reglas van en el prompt **y** se comprueban después (§8):

- **Contexto obligatorio desde Aplicar:** el enunciado parte de una situación
  profesional (caso, conjunto de datos, fragmento de código, estado financiero,
  viñeta clínica, expediente), no de una pregunta directa de definición.
- **Distractores plausibles:** cada opción incorrecta responde a un error
  conceptual o de procedimiento real y lleva su justificación ("por qué alguien
  la elegiría y por qué es incorrecta"). Se prohíben "todas las anteriores",
  "ninguna de las anteriores" y las opciones absurdas.
- **Varios pasos:** un ítem de Analizar o superior requiere al menos dos pasos
  de razonamiento; el campo `razonamiento` del esquema los enumera.
- **Preguntas abiertas con criterio:** todo ítem abierto incluye respuesta
  modelo y criterios de calificación en la escala de 5 niveles.
- **Vocabulario disciplinar:** se usa la terminología técnica de la carrera y,
  cuando el sílabo lo aporta, el problema del territorio y el producto
  integrador como contexto de los casos.
- **Sin dependencia de memoria trivial:** no se preguntan fechas, autores o
  numerales salvo que el RA lo exija.

### 5.4 Contenido técnico

- **Fórmulas:** el esquema admite LaTeX delimitado. En HTML se dibuja con KaTeX
  incrustado en el archivo (sin CDN); en DOCX y PDF, como imagen generada en el
  servidor. Texto alternativo con la expresión en LaTeX.
- **Código:** bloques con lenguaje declarado, fuente monoespaciada, sin
  ejecución.
- **Tablas de datos:** tipo de bloque propio (encabezados + filas), para casos
  con cifras.

---

## 6. Catálogo de herramientas

Cada herramienta es un esquema Pydantic + una función de renderizado. Todas
reciben el mismo contexto (§7.1) y devuelven ítems con trazabilidad al RA.

### 6.1 Fase 1 — núcleo

| Herramienta | Qué produce | Límites del esquema |
|---|---|---|
| `banco_reactivos` | Preguntas de opción múltiple con caso, respuesta múltiple, verdadero/falso con justificación, emparejamiento, ordenamiento de procesos y pregunta abierta corta. Cada ítem: RA, contenido, nivel cognitivo, clave, justificación de la clave y de cada distractor | 5–40 ítems; 4–5 opciones |
| `estudio_caso` | Caso con contexto, actores, datos (tablas), dilema; 4–8 preguntas escalonadas de Analizar a Crear; **notas para el docente** con respuestas esperadas y puntos de discusión | 400–900 palabras de caso |
| `rubrica` | Rúbrica socioformativa para una evidencia del sílabo: 3–6 criterios × 5 niveles institucionales (Receptivo → Cocreativo), con puntaje sobre 10 y pesos | Pesos suman 100 % |
| `taller_practico` | Taller o práctica de laboratorio: objetivo, materiales, procedimiento, problemas graduados, entregable, criterios de evaluación | 3–10 problemas |
| `examen` | Examen armado desde una tabla de especificaciones (RA × nivel cognitivo), con puntajes, tiempo estimado, **clave de respuestas aparte** y versiones A/B con el orden permutado | 10–50 ítems |

### 6.2 Fase 2 — ampliación

| Herramienta | Qué produce |
|---|---|
| `reto_abp` | Reto de aprendizaje basado en problemas a partir del problema del territorio: escenario, entregables por momento, hitos, rúbrica asociada |
| `seminario_debate` | Pauta de debate o seminario: tesis enfrentadas, preguntas detonantes, roles, criterios de participación |
| `presentacion` | Diapositivas de clase (PPTX) con notas del orador y preguntas de comprobación intercaladas |
| `mapa_conceptual` | Diagrama SVG de conceptos y relaciones (reutiliza `render_diagram`) |
| `repaso_terminologia` | Crucigrama, tarjetas y relación de columnas con terminología técnica (reutiliza `build_crossword`, `build_flashcards`, `build_logic_puzzle`). Se etiqueta como repaso y queda fuera del piso de §5.2 |

### 6.3 Eliminado respecto al aplicativo anterior

Sopa de letras, hojas de Educación Inicial, conversor de PDF a HTML y generador
de tareas Canvas con plantillas escolares.

Tampoco hay herramientas que dependan de un texto externo (por ejemplo,
preguntas de lectura sobre un libro de la bibliografía): el sistema solo conoce
lo que dice el sílabo y no inventa el contenido de las fuentes.

---

## 7. Generación

### 7.1 Configuración que elige el docente

| Parámetro | Opciones |
|---|---|
| Alcance | Uno o varios RA · un momento/unidad · un rango de semanas · contenidos seleccionados |
| Herramienta | Una del catálogo (§6), elegida de forma explícita |
| Perfil de dificultad | Fundamentación · Profesional · Avanzado · distribución personalizada |
| Cantidad | Número de ítems o extensión, dentro de los límites del esquema |
| Instrucciones adicionales | Texto libre (contexto de la carrera, énfasis, restricciones) |

### 7.2 Planificador (componente D)

Antes de llamar a la IA, el código arma una **tabla de especificaciones**:
reparte la cantidad pedida entre los RA del alcance y los niveles cognitivos
del perfil, y asigna a cada casilla contenidos concretos del sílabo. La tabla
se muestra al docente y es el contrato que el resultado debe cumplir.

```text
Ejemplo: 20 ítems, perfil Profesional, alcance RA1 y RA2
            Rec/Comp   Aplicar   Analizar   Eval/Crear   Total
   RA1          1         3          4           2         10
   RA2          1         3          3           3         10
```

Ningún nivel puede superar el techo del RA (§5.2); el excedente se reasigna al
nivel inmediato inferior y se avisa al docente.

### 7.3 Orquestador (componente E)

- Prompt con: datos de la asignatura, carrera y nivel; RA del alcance;
  contenidos asignados; problema/reto si existe; tabla de especificaciones;
  reglas de §5.3; instrucciones del docente.
- Uso de herramienta **forzado** al esquema elegido. No hay selección por
  palabras clave.
- Recursos grandes se generan por lotes de hasta 10 ítems, cada lote con la
  lista de enunciados ya generados para evitar repeticiones.
- Proveedor de IA: interfaz única con un proveedor activo definido por
  `LLM_PROVIDER`, **respetado siempre** (en el aplicativo anterior DeepSeek se
  imponía aunque se configurara otro). Sin clave configurada → `503` con
  mensaje claro; no hay generación degradada.
- Cada llamada se registra en el historial de consumo con función, tokens y
  costo estimado.

---

## 8. Control de calidad del recurso (componente F)

Se aplica únicamente a **lo que el sistema acaba de generar**, nunca al sílabo. Subir la
dificultad aumenta el riesgo de claves erróneas y enunciados ambiguos, así que
esta etapa es obligatoria.

**Comprobaciones deterministas (siempre):**

1. El resultado cumple el esquema; los ítems inválidos se descartan y se
   regeneran una vez.
2. Cada ítem de opción múltiple tiene exactamente una clave (o el número
   declarado, en respuesta múltiple) y opciones sin duplicados.
3. Cada ítem referencia un RA y un contenido que existen en el sílabo.
4. La distribución por RA y nivel cumple la tabla de especificaciones (±1 ítem
   por casilla).
5. Los ítems de Aplicar o superior tienen contexto (longitud mínima del
   enunciado y campo `contexto` no vacío) y `razonamiento` con dos pasos o más.
6. No hay enunciados casi duplicados (similitud de tokens ≥ 0,8).
7. En rúbricas: pesos que suman 100 % y los cinco niveles descritos por cada
   criterio.

**Revisión con IA (segunda llamada, activable):** un revisor independiente
resuelve cada ítem sin ver la clave. Si su respuesta no coincide con la clave,
o detecta más de una opción defendible, el ítem se marca **"requiere
revisión"** con el motivo. El sistema no corrige en silencio: lo decide el
docente.

**En pantalla:** cada ítem muestra su RA, nivel cognitivo, estado de calidad y
botones para editar, regenerar solo ese ítem o eliminarlo.

---

## 9. Contratos de datos

Nombres en español y `snake_case`.

```jsonc
// SilaboUniversitario — salida del lector (solo lectura)
{
  "asignatura": "Estructuras de Datos",
  "codigo": "SOF-304",
  "carrera": "Software",
  "facultad": "Ingenierías",
  "nivel": 3,
  "modalidad": "Presencial",
  "periodo": "B26",
  "creditos": 4,
  "horas": { "contacto": 64, "practico": 32, "autonomo": 96 },
  "docente": "…",                                  // nunca se envía a la IA
  "competencia_especifica": "…",
  "problema": { "descripcion": "…", "pregunta_reto": "…", "producto": "…" },
  "resultados_aprendizaje": [
    { "id": "RA1", "texto": "Implementa estructuras lineales…",
      "verbo": "implementa", "nivel_cognitivo": "aplicar",
      "evidencia": "…" }
  ],
  "contenidos": [
    { "id": "C1", "tipo": "conceptual", "texto": "Listas enlazadas" }
  ],
  "momentos": [
    { "numero": 1, "titulo": "Sensibilización…", "semanas": [1, 2, 3, 4],
      "ra": ["RA1"], "contenidos": ["C1", "C2"], "evidencia": "…", "actividades": "…" }
  ],
  "evaluacion": [ { "ra": "RA1", "evidencia": "…", "criterios": ["…"], "peso": 25 } ],
  "bibliografia": { "basica": ["…"], "complementaria": ["…"] },
  "ruta_lectura": "plantilla",                     // plantilla | ia
  "no_encontrado": ["planeacion_por_momentos"]     // secciones que el lector no halló
}
```

```jsonc
// SolicitudGeneracion — POST /recursos/generar
{
  "sesion_id": "…",
  "herramienta": "banco_reactivos",
  "alcance": { "ra": ["RA1", "RA2"], "momentos": [], "semanas": [], "contenidos": [] },
  "perfil": "profesional",                         // o "distribucion": {...}
  "cantidad": 20,
  "instrucciones": "Contextualizar en empresas de Ambato."
}
```

```jsonc
// Recurso — respuesta de generación (ejemplo: banco de reactivos)
{
  "id": "…",
  "herramienta": "banco_reactivos",
  "titulo": "Banco de reactivos — RA1 y RA2",
  "tabla_especificaciones": [ { "ra": "RA1", "nivel": "analizar", "planificado": 4, "generado": 4 } ],
  "items": [
    {
      "id": "i1", "tipo": "opcion_multiple",
      "ra": "RA1", "contenido": "C1", "nivel_cognitivo": "analizar",
      "contexto": "Una aplicación de inventario…",
      "enunciado": "¿Qué cambio reduce el costo de…?",
      "opciones": [
        { "texto": "…", "correcta": true,  "justificacion": "…" },
        { "texto": "…", "correcta": false, "justificacion": "Confunde O(n) con…" }
      ],
      "razonamiento": ["Identificar la operación dominante", "Comparar costos…"],
      "calidad": { "estado": "ok", "motivo": null }  // ok | requiere_revision
    }
  ],
  "resumen_calidad": { "total": 20, "ok": 18, "requiere_revision": 2, "descartados": 0 },
  "consumo": { "llamadas": 3, "tokens": 14200, "costo_usd": 0.004 }
}
```

---

## 10. API HTTP

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/salud` | Estado y proveedor de IA activo |
| `POST` | `/silabos` | Sube el sílabo; devuelve `sesion_id` y `SilaboUniversitario` |
| `POST` | `/silabos/{sesion_id}/releer` | Vuelve a leer el mismo archivo con la ruta C2 |
| `GET` | `/herramientas` | Catálogo con límites y requisitos de cada herramienta |
| `POST` | `/recursos/planificar` | Devuelve la tabla de especificaciones sin generar |
| `POST` | `/recursos/generar` | Genera el recurso completo |
| `POST` | `/recursos/{id}/items/{item_id}/regenerar` | Regenera un solo ítem |
| `PUT` | `/recursos/{id}` | Guarda las ediciones del docente |
| `GET` | `/recursos/{id}/exportar?formato=` | `docx`, `pdf`, `html`, `pptx`; parámetro `con_clave` |
| `GET` | `/consumo/resumen` | Totales de uso de IA |

Errores: `415` tipo de archivo, `422` sílabo escaneado o que el lector no pudo interpretar, `503`
proveedor de IA sin configurar, `500` genérico.

---

## 11. Exportación

| Formato | Uso | Notas |
|---|---|---|
| **DOCX** | Formato principal: el docente lo edita en Word | Encabezado institucional, versión del estudiante y versión del docente (con clave y justificaciones) |
| PDF | Impresión | Mismo contenido, tamaño A4 |
| HTML | Práctica en línea | Archivo único, autocorregible en ítems cerrados, sin CDN |
| PPTX | Solo `presentacion` | Construido desde los datos, no desde el HTML |
| Banco para aula virtual (Fase 2) | Importar reactivos al LMS | Formato según el LMS institucional **[SUPUESTO sin confirmar: Moodle XML/GIFT o QTI]** |

Todo recurso exportado lleva al pie la asignatura, el RA al que responde y la
leyenda "Recurso generado con asistencia de IA y revisado por el docente".

---

## 12. Almacenamiento, configuración y seguridad

- **Sesiones en disco** con identificador aleatorio y vida de 6 horas
  (`SESSION_TTL_SECONDS`): archivo subido, `silabo.json`, recursos generados.
  Limpieza al arrancar y cada hora.
- **Variables de entorno:** `LLM_PROVIDER`, clave y modelo del proveedor,
  `WORK_DIR`, `SESSION_TTL_SECONDS`, `CORS_ORIGINS`, `REVISOR_IA` (activa la
  segunda llamada de §8).
- **Defectos del aplicativo anterior que este spec obliga a no repetir:**
  - Todas las dependencias usadas constan en `requirements.txt` (antes faltaba
    `reportlab` y el backend no arrancaba en limpio).
  - Todo texto del documento o de la IA se escapa antes de insertarlo en HTML,
    DOCX y en el marcado de ReportLab.
  - `/consumo/*` no queda expuesto sin protección: requiere una clave de
    administración por cabecera.
  - CORS permite exactamente los métodos que la API usa.
  - El historial de consumo no se versiona en git.

---

## 13. Fases y criterios de aceptación

### Fase 0 — Descubrimiento del sílabo (previa a programar el lector)

Reunir de 3 a 5 sílabos universitarios reales, llenos, de carreras distintas.
Con ellos se calibra la ruta C1 y se arman los archivos de prueba. Sin esto, el
lector se construye solo contra la plantilla vacía.

### Fase 1 — Núcleo

Lector (C1 + C2), resumen del sílabo, planificador, las 5 herramientas de
§6.1, control de calidad, exportación DOCX/PDF/HTML.

| # | Criterio de aceptación |
|---|---|
| 1 | Un sílabo en la plantilla 2026 se lee sin IA: todos los RA, contenidos y momentos coinciden con el documento (verificado a mano en los archivos de prueba) |
| 2 | Un sílabo en otro formato se lee por la ruta C2 y ningún RA o contenido extraído falta en el texto original |
| 3 | PDF escaneado → `422`; `.docx` renombrado a `.pdf` → detectado por magic bytes |
| 4 | Sin clave de IA → `503` al generar; la lectura por plantilla y el resumen funcionan igual |
| 5 | Banco de 20 ítems, perfil Profesional: la distribución real cumple la tabla de especificaciones (±1 por casilla) y como máximo el 20 % está en Recordar/Comprender |
| 6 | Ningún ítem contiene "todas/ninguna de las anteriores"; todo distractor tiene justificación |
| 7 | Un ítem con dos opciones defendibles (caso sembrado en las pruebas con IA simulada) queda marcado "requiere revisión" |
| 8 | La rúbrica generada tiene los 5 niveles institucionales por criterio y pesos que suman 100 % |
| 9 | El examen exporta versión A, versión B y clave; las tres son coherentes entre sí |
| 10 | El nombre del docente no aparece en ningún prompt enviado a la IA (prueba sobre el cliente simulado) |
| 11 | Regenerar un ítem no altera los demás ni rompe la tabla de especificaciones |
| 12 | Una instalación limpia arranca y pasa todas las pruebas solo con `requirements.txt` |

### Fase 2 — Ampliación

Herramientas de §6.2, PPTX, exportación de bancos al aula virtual, fórmulas en
DOCX/PDF si no entraron en Fase 1.

### Fuera de alcance

Cualquier evaluación, corrección o edición del sílabo; subida de documentos
distintos del sílabo
(guías, lecturas, material de apoyo), conversor PDF → HTML, OCR, cuentas de
usuario e historial persistente, integración directa con el SGA.

---

## 14. Decisiones pendientes

| # | Pregunta | Supuesto adoptado en este spec | Qué cambia si es distinto |
|---|---|---|---|
| 1 | ¿Qué formato de sílabo subirán los docentes: el vigente, la plantilla 2026 de Proyecto Formativo, o ambos? | Ambos, con la plantilla 2026 como ruta determinista | Si solo circula el formato vigente, la ruta C1 se calibra contra ese y hacen falta ejemplos reales |
| 2 | ¿Qué herramientas son prioritarias para la universidad? | Las 5 de §6.1 | Reordena las fases |
| 3 | ¿Proveedor de IA? | Configurable; sin valor por defecto impuesto | Costo y calidad de los ítems de nivel alto; conviene medir con un banco de prueba antes de fijarlo |
| 4 | ¿Aula virtual institucional (Moodle, Canvas, otra)? | Sin confirmar; exportación de bancos en Fase 2 | Define el formato de importación |
| 5 | ¿Se requiere inicio de sesión institucional e historial de recursos? | No en v1.0 | Añade base de datos y autenticación |
| 6 | ¿Se parte del código de `Unidad-Educativa` o se escribe desde cero en este repositorio? | Repositorio nuevo, reutilizando por copia: subida de archivos, patrón del orquestador, exportadores, registro de consumo y renderizadores de crucigrama, tarjetas, diagrama y rompecabezas | Si se bifurca el repositorio anterior, hay que retirar primero los módulos que no se usan |

---

## 15. Riesgos

| Riesgo | Mitigación |
|---|---|
| Sílabos con formatos muy distintos entre facultades | Ruta C2 con comprobación de fidelidad contra el texto, resumen visible antes de generar y registro de los formatos que no se pudieron leer |
| Claves incorrectas o ítems ambiguos al subir la dificultad | Control de calidad de §8 y edición ítem por ítem; nada se exporta sin pasar por la pantalla de ajuste del recurso (paso 4) |
| El modelo "baja" la dificultad y devuelve preguntas de definición | Tabla de especificaciones como contrato y comprobación 5 de §8; los ítems que no cumplen se regeneran |
| Contenido técnico inexacto en áreas especializadas (salud, derecho, ingeniería) | Leyenda de revisión docente, justificaciones visibles para facilitar la verificación, y casos anclados en los contenidos del sílabo |
| Casos que citan normas, cifras o autores inventados | Regla en el prompt: los datos de un caso son ficticios y se declaran como tales; no se citan fuentes que no estén en la bibliografía del sílabo |
| Costo por recurso mayor que en el aplicativo anterior (lotes + revisor) | Revisor activable, lotes de 10, consumo visible por recurso |
