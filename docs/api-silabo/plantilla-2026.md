# Plantilla de sílabo 2026 → contrato JSON 2.0

Mapa de la plantilla que usan los sílabos B26 nuevos de Ingeniería (15 PDF, `SILABOS B26/Ingenieria`, revisados el 2026-11-23) contra el contrato 2.0 (`silabo-api.v2.schema.json`) y la Escala general de evaluación de sílabos (UTI, 23/10/2026).

La estructura se obtuvo solo de las líneas que se repiten en al menos el 80 % de los PDF (texto fijo de la plantilla) y de los encabezados de tabla. No se registró contenido de ningún sílabo.

## Resumen del lote

| Dato | Valor |
|---|---|
| PDF de sílabo | 15 (más 6 guías prácticas en `Guias practica/`, que no son sílabos) |
| Plantilla | Nueva: apartados I a VII, los mismos de la escala |
| Leídos por el lector de la V1 | 13; 2 ilegibles (`SilaboIlegible`) |
| Nuevos para el corpus | 7; 6 ya estaban (misma versión; 1 con momentos distintos) |
| Carreras | Software 6, Tecnologías de la Información 6, Inteligencia de Negocios 1 (FACEAN) |
| Momentos / sesiones | 45 / 208 (16 sesiones por sílabo en promedio) |

## Mapa por apartado

| Apartado de la plantilla | Forma en el PDF | Clave del contrato 2.0 | Escala | Estado |
|---|---|---|---|---|
| Encabezado | Facultad, carrera, periodo, proyecto formativo, versión, docente | `facultad`, `carrera`, `periodo`, `proyecto_formativo.{nombre,codigo,version}` | II.1 | Coincide. El docente queda fuera |
| I. Perfil del docente | Nombres, títulos, nivel de formación, experiencia, teléfono, email, ORCID | — (fuera de la API) | I.1 | Coincide: lo valora el evaluador fuera del sistema |
| II. Presentación | Tabla: créditos, horas, periodo, nivel, modalidad; unidad de organización curricular | `proyecto_formativo.{creditos,horas,nivel,modalidad,uoc}` | II.1 | Coincide |
| III. Horas por componente | Contacto con el docente, práctico-experimental, autónomo | `proyecto_formativo.horas` | II.1 | Coincide |
| III. Horarios | Contacto y práctico-experimental; a menudo «Sin horario registrado» | `proyecto_formativo.horario[]` | II.1 | «Sin horario registrado» = lista vacía |
| III. Prerrequisitos / correquisitos | Prerrequisitos: «Ninguno» en 14 de 15. Correquisitos: lista de proyectos formativos en los 15 | `proyecto_formativo.prerrequisitos[]`, `correquisitos[]` | II.1 | «Ninguno» = lista vacía (válido) |
| III. Competencia del perfil de egreso | Texto | `competencia_perfil` | III.1 | Coincide |
| III. Competencia del proyecto formativo | Texto | `competencia_pf` | III.2 | Coincide |
| III. Metacompetencia transversal | **Casillas**: 5 opciones fijas, la elegida con `(X)` | `metacompetencia` (texto) | III.3 | **Ajuste:** conviene un `enum` con las 5 opciones |
| III. Habilidades blandas | Viñetas | `habilidades_blandas[]` | III.4 | Coincide |
| III. Ejes transversales | Tabla «Eje · Cómo se evidencia en las actividades del PF», una fila por eje | `ejes_transversales.<eje>.descripcion` | III.5–III.10 | **Brecha:** la plantilla no pide justificación de NA ni ODS numerados ni tipo de internacionalización. Un eje sin fila no dice si es ND o NA |
| III. Inclusión | Texto único | `inclusion.{barreras,apoyos}` | III.11 | **Ajuste:** la plantilla no separa barreras y apoyos |
| III. RA y evidencias | Tabla «RA · Resultado de aprendizaje · Evidencia de desempeño» | `resultados_aprendizaje[]` | III.12–III.14 | Coincide |
| III. Contribución al perfil | Texto | `contribucion_perfil` | III.15 | Coincide |
| III. Problema del territorio | Tabla «Problema, necesidad u oportunidad» | `problema` | III.16–III.18 | Coincide |
| III. Proyecto interdisciplinario socioformativo | Nombre y «Aporte del proyecto formativo…» | `pis.{nombre,descripcion,aporte}` | III.19–III.20 | **Ajuste:** se llama «interdisciplinario socioformativo», no «integrador de saberes»; no tiene casilla de NA |
| III. Metodología activa | Viñetas: Clase invertida (15), ABP (13), Estudio de caso (9)… | `metodologias.clase_invertida`, `complementarias[]` | III.21–III.29 | **Brecha:** sin antes, durante y después de la clase invertida; sin justificación ni sesiones donde se aplica cada metodología |
| IV. Momentos | Por momento: título, fechas, RA, evidencia, política de IA, recursos | `momentos[]` | IV.1–IV.15 | Coincide |
| IV. Sesiones | Tabla «Sesión-fecha · Actividades con el docente · Horas · Práctico-experimentales · Horas · Trabajo autónomo · Horas · Contenidos» | `momentos[].sesiones[]` | IV.* | Coincide |
| IV. Rúbrica del momento | «Indicador · Receptivo · Resolutivo · Reflexivo · Crítico · Cocreativo» | `momentos[].rubrica[]` | IV.* | Coincide |
| V. Evaluación | **Solo** la rúbrica del producto final | `rubrica_producto_final[]` | V.1–V.4 | Coincide |
| V. Evaluación (resto) | No existe en la plantilla | `evaluacion.*` | V.5–V.12 | **Brecha:** proceso, agentes, retroalimentación, metacompetencia, gobernanza de IA, calificación, mejora y credencial no tienen dónde escribirse |
| VI. Bibliografía | Básica y complementaria | `bibliografia.{basica,complementaria}` | VI.1 | Coincide |
| VII. Firmas | Docente y coordinador(a) de carrera | — (fuera de la API) | VII.1 | Coincide |

## Consecuencias

1. **La plantilla no pide todo lo que la escala valora.** Con esta plantilla, V.5 a V.12 (30 % del apartado V) y el detalle de metodologías (III.21–III.29) salen siempre ND. Hay que decidir con la UTI si la plantilla se amplía o si la escala se ajusta a la plantilla.
2. **Tres ajustes al contrato 2.0** para calzar con la plantilla: `metacompetencia` como una de 5 opciones fijas, `inclusion` como texto único (o barreras y apoyos opcionales), y el PIS como «proyecto interdisciplinario socioformativo».
3. **Lector de PDF ampliado (2026-11-23).** `backend/ciencia_datos/lector_pdf/` (traído de la V1, fuera de la aplicación) lee ahora prerrequisitos, correquisitos, nivel de formación, habilidades blandas, ejes (con ODS e internacionalización), inclusión y contribución al perfil, y entrega el JSON 2.0 directo: `python -m ciencia_datos.lector_pdf.lote <carpeta PDF> <salida>`. Una sesión o momento sin fecha legible ya no rechaza el PDF: la fecha queda nula y la validación lo informa.
4. **TI:** si el SGA guarda los mismos campos que la plantilla, su API llevará estas mismas brechas.

## Cumplimiento de los apartados que el lector aún no lee

Medido en los 15 PDF (incluidos los 2 que el lector no abre), contando caracteres entre cada encabezado y el siguiente, sin leer el contenido.

| Apartado | Escala | Cumplen | Dónde no cumplen |
|---|---|---|---|
| Prerrequisitos | II.1 | 15 | — (14 dicen «Ninguno», válido) |
| Correquisitos | II.1 | 15 | — |
| Habilidades blandas | III.4 | 15 | — (de 36 a 137 caracteres: listas cortas) |
| Ejes transversales | III.5–III.10 | 15 con al menos 1 eje | 3 declaran los 6 ejes; 12 declaran de 1 a 3 sin decir por qué los demás no aplican |
| Inclusión | III.11 | 13 | 1 vacío (7 caracteres) y 1 muy breve (92 caracteres) |
| Contribución al perfil | III.15 | 15 | — |
| Clase invertida (antes, durante, después) | III.21 | 0 | Los 15 solo la nombran en la lista de metodologías |
| Metodologías complementarias (justificación y sesiones) | III.22–III.29 | 0 | Los 15 solo las listan (de 1 a 4 además de la clase invertida) |
| Evaluación V.5–V.12 | V.5–V.12 | 0 | La plantilla no tiene el apartado |

Además, entre los apartados que el lector sí lee, 1 sílabo no trae competencia del proyecto formativo (III.2) y 1 no trae rúbrica del producto final (V.1–V.4).

## Resultado con el lector ampliado

Los 15 PDF se convierten a JSON 2.0 y los 15 cumplen las reglas del contrato. 14 cumplen el esquema y entran al sistema; uno no, porque 2 de sus momentos dicen «por definir» en lugar de fechas y no tienen sesiones. Otro entra con 2 sesiones sin fecha, que no se importan (aviso).

ND que quedan, por causa:

| Causa | Puntos (sílabos con ND) |
|---|---|
| El sílabo no declara el eje y no justifica | III.5 ODS (5), III.6 interculturalidad (9), III.7 internacionalización (12), III.8 interdisciplinariedad (1), III.9 emprendimiento (7), III.10 educación financiera (12) |
| El sílabo deja vacío el campo | III.2 competencia del PF (1), III.19 nombre del PIS (2), IV.11 recursos de un momento (3), V.1–V.4 rúbrica final (1) |
| La plantilla no tiene el apartado | III.21 clase invertida (14), V.5–V.12 (14) |
