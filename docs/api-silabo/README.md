# Contratos JSON con el SGA · v1.0

La V2 recibe del SGA tres documentos JSON. Cada uno tiene un esquema (JSON Schema 2020-12) y un ejemplo en esta carpeta. Qué debe entregar TI para conectarlos: [../sga/para-TI.md](../sga/para-TI.md).

| Contrato | Esquema | Ejemplo | Para qué |
|---|---|---|---|
| Autenticación | [auth-sga.schema.json](auth-sga.schema.json) | [ejemplo-auth.json](ejemplo-auth.json) | Identidad del docente tras validar su usuario y clave: `usuario`, `correo` institucional y `nombre`. Nunca incluye la clave ni tokens |
| Materias | [materias-api.schema.json](materias-api.schema.json) | [ejemplo-materias.json](ejemplo-materias.json) | Lista de las materias del docente: `id_sga`, `codigo_pf`, `paralelo`, `nombre`, `carrera`, `estado` |
| Sílabo | [silabo-api.schema.json](silabo-api.schema.json) | [mínimo](ejemplo-minimo.json) y [completo](ejemplo-completo.json) | El sílabo de una materia: con él se generan los recursos y se entrena el modelo |
| Sílabo v2.0 | [silabo-api.v2.schema.json](silabo-api.v2.schema.json) | [mínimo](ejemplo-v2-minimo.json) y [completo](ejemplo-v2-completo.json) | El sílabo con todos los apartados que valora la escala de evaluación. Ver [Contrato v2.0](#contrato-v20-y-escala-de-evaluación) |
| Evaluación del sílabo | [evaluacion-silabo.schema.json](evaluacion-silabo.schema.json) | [ejemplo-evaluacion.json](ejemplo-evaluacion.json) | Resultado de la escala: nivel por pregunta, apartados y total. Catálogo de la escala: [escala-silabo.json](escala-silabo.json) |

El código del proyecto formativo identifica el sílabo: la materia lo trae en `codigo_pf` y el sílabo en `proyecto_formativo.codigo`; deben coincidir.

> **Contrato definitivo (24/11/2026): el JSON del Validador de Sílabos, `silabo-api/0.1.0`, tal cual.** El Generador y el Validador serán un solo sistema, así que el Generador consume el mismo JSON que el validador, sin cambiarle nada: esquema `silabo-api-0.1.0.schema.json` (derivado del documento del validador; reemplazar por el oficial de `specs/001-validador-silabo/contracts/` cuando se reciba) y ejemplo `silabo-api-0.1.0.ejemplo.json`. El adaptador `backend/app/sga/contrato_validador.py` lo lleva a la forma interna: con los 98 sílabos reales que entran, el sílabo interno y los avisos son idénticos a los del contrato 2.0, y las 480 410 entradas de huellas de herramientas (contexto, prompts, plan, menú y herramientas sin IA) también. Un sílabo sin `"contrato": "silabo-api/0.1.0"` queda `invalida`. Requisitos para generar (además del esquema): código y nombre del PF, carrera, periodo con fechas, nivel, al menos un RA (sin repetir id), un momento y una sesión. El contrato 2.0 se conserva solo como forma interna de la escala de evaluación (`contrato_validador.a_v2`). Detalle: [validador/cruce-contratos.md](validador/cruce-contratos.md).

> **Antes (18/11/2026):** el sistema aceptaba solo el sílabo **v2.0**; desde el 24/11 lo reemplaza el contrato del validador. Un sílabo sin `"contrato": "2.0"` queda como `invalida` con el fallo `contrato: se requiere la versión 2.0` y no reemplaza la versión guardada. El v1.0 se documenta como referencia; para convertir sílabos 1.0 de prueba: `python herramientas/migrar_a_v2.py <archivo.json>...`.

**Estado del contrato del sílabo:** v1.0, definido el 2026-11-16 con 51 sílabos reales del periodo B26 (9 carreras, 4 facultades). Los 51 cumplen el esquema y entran al sistema. Falta que TI confirme los puntos de [Preguntas para TI](#preguntas-para-ti).

## Principio: el SGA envía lo que guarda

El SGA no tiene que calcular nada. Tres campos de cada sesión los completa el sistema cuando no vienen (si vienen, se respetan):

| Campo | Cómo lo completa el sistema |
|---|---|
| `sesiones[].id` | `M<número del momento>-S<número de la sesión>`, p. ej. `M2-S7` |
| `sesiones[].semana_periodo` | Semana 1 = la que empieza el lunes de la semana de `periodo.inicio` |
| `sesiones[].entregables` | Los que nombran las actividades de la sesión: `TAREA n`, `PAE n`, `EVALUACIÓN COGNITIVA n` |

En los 51 sílabos reales, lo que el sistema deriva coincide con lo que traía el sílabo en las 1.550 sesiones.

## Formato del sílabo

Obligatoria = la clave debe venir. «Puede ir vacío» = la clave viene, pero su texto o su lista pueden estar vacíos.

### Raíz

| Clave | Tipo | Obligatoria | Notas |
|---|---|---|---|
| `facultad` | texto | Sí | Nombre oficial. Elige el agente y el estilo |
| `carrera` | texto | Sí | Carrera o programa de posgrado |
| `periodo` | objeto | Sí | `codigo` (p. ej. `B26`), `inicio` y `fin` en `AAAA-MM-DD` |
| `proyecto_formativo` | objeto | Sí | Ver abajo |
| `competencia_perfil` | texto | Sí | Competencia del perfil de egreso |
| `resultados_aprendizaje[]` | lista | Sí, al menos 1 | `id` (`RA1`, `RA2`, ...), `texto`, `evidencia` (puede ir vacía) |
| `problema` | objeto | Sí | `descripcion`, `reto`, `producto_final`; los textos pueden ir vacíos |
| `momentos[]` | lista | Sí, al menos 1 | Ver abajo |
| `rubrica_producto_final[]` | lista | No | Filas de rúbrica |
| `pis` | objeto | No | `nombre`, `aporte`; los textos pueden ir vacíos |
| `competencia_pf`, `metacompetencia` | texto | No | |
| `metodologias[]` | lista de textos | No | |
| `bibliografia` | objeto | No | `basica[]`, `complementaria[]` |

### `proyecto_formativo`

| Clave | Tipo | Obligatoria | Notas |
|---|---|---|---|
| `codigo` | texto | Sí | P. ej. `B26-SOFT-3-56157-1727`. Igual al `codigo_pf` de la materia |
| `nombre` | texto | Sí | Nombre de la asignatura |
| `version` | texto | Sí | P. ej. `1.0`. **Debe cambiar cada vez que cambia el sílabo** |
| `aprobado` | fecha | Sí | Fecha de aprobación |
| `nivel` | entero | Sí | Nivel de la malla, desde 1 |
| `uoc`, `modalidad`, `creditos` | texto, texto, número | No | |
| `horas` | objeto | No | Si viene: `total`, `contacto`, `autonomo`, `practico` |
| `horario[]` | lista | No | `dia`, `inicio`, `fin` (`HH:MM`) |

### `momentos[]`

| Clave | Tipo | Obligatoria | Notas |
|---|---|---|---|
| `numero` | entero | Sí | No se repite |
| `titulo` | texto | Sí | |
| `fecha_inicio`, `fecha_fin` | fecha | Sí | |
| `ra[]` | lista de textos | Sí | Ids de `resultados_aprendizaje`; puede ir vacía |
| `evidencia` | texto | Sí | Evidencia de desempeño; puede ir vacía. Es un entregable: el sistema no la resuelve |
| `politica_ia` | texto | Sí | Política de gobernanza de IA; puede ir vacía |
| `rubrica[]` | lista | Sí | Filas de rúbrica; puede ir vacía |
| `sesiones[]` | lista | Sí, al menos 1 | Ver abajo |
| `recursos` | texto | No | |

### `momentos[].sesiones[]`

| Clave | Tipo | Obligatoria | Notas |
|---|---|---|---|
| `numero` | entero | Sí | Número de la sesión en el sílabo; no se repite dentro del sílabo |
| `fecha` | fecha o `null` | Sí | Dentro del periodo. `null` si no tiene fecha programada (ver abajo) |
| `contenidos[]` | lista de textos | Sí | Un elemento por contenido; puede ir vacía, pero sin textos vacíos dentro |
| `docente` | objeto | Sí | `texto` (puede ir vacío), `horas` opcional, `asincronica` opcional: `{texto, horas}` o `null` |
| `practico`, `autonomo` | objeto | Sí | `texto` (puede ir vacío), `horas` opcional |
| `id`, `semana_periodo`, `entregables[]` | | No | Los completa el sistema |

### Fila de rúbrica (`momentos[].rubrica[]` y `rubrica_producto_final[]`)

`indicador` (texto) y `niveles` (objeto) con las cinco claves `receptivo`, `resolutivo`, `reflexivo`, `critico`, `cocreativo`, cada una con su descriptor. Las 1.074 filas de los sílabos reales traen exactamente esas cinco.

### Sesiones sin fecha

En 7 de los 55 PDF del primer lote (13 %), una sesión no tiene fecha. El sistema organiza las clases por fecha, así que esa sesión **no se importa**: el SGA la envía con `fecha: null`, el resto del sílabo entra normal y el docente ve un aviso con la ruta de la sesión. Si todas las sesiones de un momento van sin fecha, el sílabo es inválido.

## Regla de privacidad

La API **no** debe enviar la sección I (perfil, correo, teléfono, ORCID del docente) ni la VII (firmas). Aunque lleguen, el sistema no las conserva: el **traductor de lista blanca** (`backend/app/sga/traductor.py`) copia solo las claves que declara `silabo-api.schema.json` y descarta todo lo demás sin mirarlo, y `SilaboUTI` rechaza cualquier campo desconocido. Una prueba exige que la lista blanca sea idéntica a la derivada del esquema.

## Validación

Al recibir un sílabo, el sistema hace tres pasos:

1. **Traduce:** aplica la lista blanca, completa los campos derivados y aparta las sesiones sin fecha.
2. **Valida el esquema** (Pydantic, `SilaboUTI`): tipos, formatos y obligatoriedad.
3. **Valida siete reglas de integridad** (`backend/app/silabo/integridad.py`), acumulando todos los fallos:
   1. `momentos[i].numero`: no se repite.
   2. `momentos[i].ra[j]`: el resultado de aprendizaje existe en `resultados_aprendizaje`.
   3. `momentos[i].sesiones`: no queda vacío.
   4. `sesiones[j].id`: tiene la forma `M<momento>-S<n>` y el momento coincide con el suyo.
   5. `sesiones[j].id`: no se repite en el sílabo.
   6. `sesiones[j].fecha`: está dentro del periodo (`periodo.inicio` a `periodo.fin`).
   7. `sesiones[j].contenidos[k]`: no es una cadena vacía.

Los fallos y los avisos se informan como `ruta: regla` (por ejemplo `momentos[0].sesiones[1].id: repetido`), nunca con el valor del sílabo. Un sílabo inválido no se importa: su materia queda como `invalida` y el docente ve el motivo; las demás materias siguen.

## Para qué se usa cada apartado

| Apartado | Genera recursos | Entrena el modelo |
|---|---|---|
| `facultad`, `carrera` | Sí: elige el agente y el estilo | Sí: agrupa y separa por facultad |
| `proyecto_formativo.codigo`, `version`, `aprobado` | Sí: identifica la asignatura y detecta cambios | Sí: separa por sílabo y conserva la versión vigente |
| `proyecto_formativo.nombre`, `nivel` | Sí: título y dificultad | No |
| `periodo` | Sí: menú por semanas | No |
| `competencia_perfil` | Sí: contexto | No |
| `resultados_aprendizaje[]` | Sí: contexto, verificador y planificador | Sí: texto |
| `problema` | Sí: contexto y guía del producto final | No |
| `pis` | Sí: contexto de todas las herramientas | No |
| `momentos[]` (título, RA, evidencia, política de IA) | Sí: contexto, entregables y regla de integridad | Sí: evidencia |
| `momentos[].rubrica[]`, `rubrica_producto_final[]` | Sí: guías y listas de verificación | No |
| `sesiones[]` (fecha, contenidos, actividades) | Sí: menú, focos y actividades de la clase | Sí: contenidos y actividades |
| `sesiones[].entregables` | Sí: regla de no resolver entregables | No |
| `competencia_pf`, `metacompetencia`, `metodologias`, `bibliografia` | No (candidatos) | No |
| `uoc`, `modalidad`, `creditos`, `horas`, `horario`, `recursos` | No | No |

## Qué mostraron los 51 sílabos reales

Corrida del 2026-11-16 sobre 51 sílabos únicos del periodo B26: 201 momentos y 1.550 sesiones.

| Campo | Con dato |
|---|---|
| Todas las claves obligatorias | 100 % de los sílabos |
| `sesiones[].contenidos` | 94 % de las sesiones |
| `sesiones[].docente.texto` | 93 % |
| `sesiones[].autonomo.texto` | 74 % |
| `sesiones[].practico.texto` | 69 % |
| `sesiones[].docente.asincronica` | 21 % |
| `problema.descripcion` / `reto` / `producto_final` | 90 % / 98 % / 86 % de los sílabos |
| `pis.nombre` / `pis.aporte` | 65 % / 94 % |
| `rubrica_producto_final` | 88 % |
| `metodologias` | 94 % |
| Entregables nombrados en las actividades | 1 % de las sesiones |

- Los sílabos tienen 4 momentos (49 de 51), de 1 a 4 resultados de aprendizaje y `nivel` entre 1 y 9.
- El código del proyecto formativo tiene la forma `B26-<sigla>-<nivel>-<5 dígitos>-<4 dígitos>`. La sigla lleva de 2 a 4 letras, y en el posgrado leído lleva un prefijo (`B26-M-<sigla>-...`). Por eso el esquema no fija un patrón.
- Un sílabo de maestría usa otra plantilla en PDF y no se pudo leer. Hay que comprobar con TI que la API entrega los posgrados con este mismo formato.

## Contrato v2.0 y escala de evaluación

El v2.0 (2026-11-18) agrega al sílabo todo lo que valora la *Escala general de evaluación de sílabos* (UTI, 23/10/2026). Lleva `"contrato": "2.0"` en la raíz. En la rama `V3-SilabosPesos` es el único contrato que entra; `backend/app/sga/contrato_v2.py` lo lleva a la forma interna con que se generan los recursos.

**Regla general:** toda clave obligatoria debe venir. Un texto o una lista vacíos, o `null` en `creditos` y `horas`, significan **ND** (no documentado) para la escala. Un componente que no aplica al PF va con `"aplica": false` y su `justificacion_na` no vacía (**NA**). Solo admiten NA los puntos que admite la escala.

### Qué agrega el v2.0

| Clave nueva | Punto de la escala | Forma |
|---|---|---|
| `proyecto_formativo.formacion`, `prerrequisitos[]`, `correquisitos[]` | II.1 | Texto y listas. Lista vacía de requisitos = «no requiere según la malla» (válido). `uoc`, `modalidad`, `creditos`, `horas` y `horario` pasan a obligatorias |
| `competencia_pf`, `metacompetencia` | III.2, III.3 | Pasan a obligatorias. `metacompetencia` es una de las 5 del catálogo institucional (regla 4) |
| `habilidades_blandas[]` | III.4 | Una por elemento |
| `ejes_transversales` | III.5 a III.10 | Seis objetos fijos: `sostenibilidad_ods` (con `ods[]`, números 1 a 17), `interculturalidad`, `internacionalizacion` (con `tipo`: `clase_espejo`, `coil`, `movilidad`, `colaboracion`, `contraste_casos_fuentes`, `otra` o `null`, y `actores`, `actividad`, `producto`), `interdisciplinariedad` (con `disciplinas[]`), `emprendimiento`, `educacion_financiera`. Cada uno con `aplica`, `descripcion`, `justificacion_na` |
| `inclusion` | III.11 | Un solo texto con barreras y apoyos, como en la plantilla. No admite NA |
| `contribucion_perfil` | III.15 | Texto |
| `resultados_aprendizaje[]` | III.12 a III.14 | De 1 a 4, con ids `RA1`, `RA2`, ... en orden y sin saltos |
| `pis` | III.19, III.20 | Pasa a obligatorio: `aplica`, `nombre`, `descripcion`, `aporte`, `justificacion_na` |
| `metodologias` | III.21 a III.29 | Deja de ser una lista de textos. `clase_invertida` (`antes`, `durante`, `despues`; no admite NA) y `complementarias[]` con `tipo` (`aprendizaje_basado_problemas`, `aprendizaje_basado_retos`, `aprendizaje_servicio`, `aprendizaje_cooperativo`, `estudio_caso`, `cocreacion_dialogo_saberes`, `rutinas_destrezas_pensamiento`, `otra`), `nombre`, `justificacion` y `aplicada_en[]` (ids de sesión `M<m>-S<n>` donde se aplica). Los ocho nombres coinciden con los que traen los 51 sílabos reales |
| `momentos[].recursos` | IV.11 | Pasa a obligatoria |
| `sesiones[].docente.horas`, `practico.horas`, `autonomo.horas` | IV.7 | Pasan a obligatorias (las 1.550 sesiones reales las traen) |
| `rubrica_producto_final[]` | V.1 a V.4 | Pasa a obligatoria. En toda rúbrica, `niveles` exige exactamente las cinco claves |
| `evaluacion` | V.5 a V.12 | `proceso` (`inicial`, `seguimiento`, `final`), `agentes` (`autoevaluacion`, `coevaluacion`, `heteroevaluacion`), `retroalimentacion`, `metacompetencia`, `gobernanza_ia`, `calificacion` (`componentes[]` con `nombre`, `porcentaje`, `momento`; y `reglas`), `mejora`, `credencial` (`aplica`, `nombre`, `desempeno`, `evidencias`, `criterios`, `justificacion_na`) |
| `bibliografia` | VI.1 | Pasa a obligatoria: `basica[]`, `complementaria[]` |

Los apartados **I (perfil del docente)** y **VII (firmas)** siguen fuera de la API por privacidad: el evaluador los valora fuera del sistema (`"fuente": "evaluador"`).

Reglas del v2.0 que se suman a las siete de integridad (`contrato_v2.reglas`): claves obligatorias de la raíz presentes, RA numerados sin saltos, cada tipo de metodología una sola vez (salvo `otra`) y la metacompetencia, si viene, una de las 5 del catálogo institucional (sin importar mayúsculas ni tildes; el sistema guarda la forma oficial). Un sílabo que no las cumple queda `invalida`.

### Resultado de la evaluación

[escala-silabo.json](escala-silabo.json) es la escala en JSON: 60 preguntas con su apartado, referentes, las rutas del contrato que valoran, si admiten NA y si se repiten por RA o por momento. [evaluacion-silabo.schema.json](evaluacion-silabo.schema.json) es el formato del resultado:

- Un punto por pregunta. III.12 y III.13 van una vez por RA (RA1 a RA4; los no declarados, NA). IV.1 a IV.15 van una vez por momento.
- `valor`: 1 a 5, `"ND"` (vale 0), `"NA"` (sale del máximo, exige `justificacion`) o `null` (por valorar).
- `fuente`: `automatica` (ND o NA deducidos del JSON), `ia` (nivel propuesto por un modelo) o `evaluador` (confirmado por una persona).
- Por apartado: `puntos`, `maximo` (aplicables × 5), `aplicables`, `na`, `nd`, `por_valorar`, `pendientes` y `resultado` = puntos ÷ máximo × peso. En IV, 75 puntos por momento. `total` es la suma de I a VII; vale `null` mientras quede algo por valorar.

`backend/app/silabo/escala.py` hace la parte que no necesita interpretar texto:

- `revision_automatica` marca ND y NA y deja en `null` lo que necesita juicio. También marca como pendiente:
  - una metodología sin justificación, sin sesiones o con sesiones que no existen;
  - porcentajes de calificación que no suman 100;
  - sesiones fuera de las fechas de su momento.
- `calcular` aplica la fórmula.
- `validar_evaluacion` comprueba que no falte ni sobre ningún punto y que las cifras cuadren.

### Evaluación del diseño (2026-11-18)

`python -X utf8 docs/api-silabo/herramientas/validar_v2.py .` (desde la raíz del repo; necesita `jsonschema`) hace 131 comprobaciones y todas pasan. `gen_escala.py` regenera el catálogo y el esquema de evaluación desde el docx de la escala (texto extraído con `leer_docx.py`), y `gen_ejemplos_v2.py` regenera los ejemplos.

- Los dos esquemas son JSON Schema 2020-12 válidos. Los ejemplos v2.0 los cumplen, cumplen las reglas y entran al sistema. Los ejemplos v1.0 son rechazados por el v2.0.
- Cada una de las rutas de las 60 preguntas existe en el esquema, y cada campo del esquema lo valora alguna pregunta o lo usa el sistema.
- El esquema rechaza los 21 errores de prueba del sílabo, entre ellos:
  - NA sin justificación;
  - ODS 18;
  - cinco RA;
  - metodología desconocida;
  - rúbrica sin nivel crítico;
  - sesión sin horas;
  - hora mal escrita;
  - campos de las secciones I y VII.
- El formato de evaluación rechaza 11 errores de prueba, como NA donde no se admite, nivel 0 o 6, o I.1 valorado por IA. `validar_evaluacion` detecta los 4 restantes: punto repetido o faltante, total alterado y momento inexistente.
- **Los 51 sílabos reales llevados al v2.0** cumplen el esquema y las reglas y dan el mismo sílabo interno que por la vía v1.0. Su revisión automática cumple el formato.

Lo que les falta a los sílabos actuales, según la revisión automática: III.4, III.5 a III.11, III.15, III.21 y V.5 a V.12 salen ND en los 51, porque la plantilla anterior no tenía esos apartados. Además, ninguna metodología elegida indica en qué sesión se aplica.

**Erratas de la escala (versión del 23/10/2026):** las instrucciones citan una numeración anterior a la de las tablas:

- el NA del PIS figura como III.25 y III.26, y en la tabla es III.19 y III.20;
- las metodologías figuran como «III.28 a III.35», y en la tabla son III.22 a III.29;
- figura «RA2 (III.14 y III.15) ... RA4 (III.18 y III.19)», cuando la tabla repite III.12 y III.13 por RA.

El catálogo usa la numeración de las tablas.

## Preguntas para TI

1. ¿El SGA puede enviar `fecha: null` en las sesiones sin fecha programada, o las omite?
2. ¿`proyecto_formativo.version` cambia siempre que se edita el sílabo?
3. ¿Los sílabos de posgrado tienen los mismos apartados que los de grado?
4. ¿Los contenidos de una sesión se guardan como lista o como un solo texto? Si es un texto, se necesita la regla para separarlos.
5. ¿Puede haber una consulta que entregue todos los sílabos de un periodo ([../sga/para-TI.md](../sga/para-TI.md) §4.1)?
