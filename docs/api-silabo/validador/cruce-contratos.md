# Validación cruzada: contrato 2.0 del Generador y `silabo-api/0.1.0` del Validador

Fecha: 24/11/2026. Fuente del validador: documento «Estructura JSON para el Validador de Sílabos y PIS» (24/11/2026). Su esquema oficial (`specs/001-validador-silabo/contracts/`) no está en este equipo: se derivó campo por campo de las tablas 2.2 en `silabo-api-0.1.0.derivado.schema.json` y se comprobó que acepta el ejemplo 6.1 del propio documento. Herramienta: `cruce_contratos.py`.

## Veredicto

**No tienen la misma estructura.** Describen el mismo sílabo y casi todo dato del uno tiene su lugar en el otro, pero cambian los nombres, el agrupamiento y varios tipos, y cada uno tiene campos que el otro no guarda. Un JSON de uno **no** pasa el esquema del otro sin un adaptador. Con adaptador, la conversión funciona en ambos sentidos para los sílabos reales; lo que no se puede convertir son 9 campos del validador sin fuente en el 2.0 y los campos de la escala del 2.0 que el validador no tiene.

## 1. Diferencias de forma (mismo dato, distinta estructura)

| Validador `silabo-api/0.1.0` | Generador 2.0 | Diferencia |
|---|---|---|
| `contrato: "silabo-api/0.1.0"` | `contrato: "2.0"` | Distinto identificador |
| Agrupado por sección: `documento`, `portada`, `presentacion`, `mapa`, `momentos`, `rubrica_producto_final`, `bibliografia` | Plano en la raíz: `facultad`, `carrera`, `periodo`, `proyecto_formativo`, `competencia_*`, … | Distinto agrupamiento |
| `portada.periodo_codigo`, `periodo_inicio`, `periodo_fin` | `periodo.codigo`, `inicio`, `fin` | Nombres y anidamiento |
| `portada.pf_nombre`, `pf_codigo` (+ `presentacion.nombre`, `presentacion.periodo` repetidos) | `proyecto_formativo.nombre`, `codigo` (una vez) | El validador repite nombre y periodo (portada y sección II) |
| `portada.version` (opc.) y `documento.version` | `proyecto_formativo.version` | — |
| `portada.fecha_aprobacion` (opc.) | `proyecto_formativo.aprobado` (**obligatorio**) | Obligatoriedad |
| `portada.facultad` (opc.) | `facultad` (**obligatorio, no vacío**) | Obligatoriedad |
| `presentacion.horas_total`, `horas_contacto`, `horas_practico`, `horas_autonomo` (cada una puede ser `null`) | `proyecto_formativo.horas{total,contacto,practico,autonomo}` (objeto completo o `null`) | Plano vs. objeto; vacío por campo vs. por bloque |
| `presentacion.nivel` entero 1–12 | `proyecto_formativo.nivel` entero ≥ 1 | El validador limita a 12 |
| `presentacion.nivel_formacion` | `proyecto_formativo.formacion` | Nombre |
| `presentacion.horario_contacto` lista de textos («Viernes 15:30 a 16:29») | `proyecto_formativo.horario` lista de objetos `{dia, inicio, fin}` | Texto vs. objeto |
| `mapa.metacompetencias` lista de las 5 opciones con `marcada` | `metacompetencia` texto de la opción marcada (regla: una del catálogo) | Lista de 5 vs. una |
| `mapa.ejes_transversales` lista `{eje, como_se_evidencia}`, ejes libres | `ejes_transversales` objeto de 6 ejes fijos `{aplica, descripcion, justificacion_na}` (+ `ods`, `tipo`, `disciplinas`) | Lista libre vs. 6 fijos con NA |
| `mapa.problema`, `pregunta_reto`, `evidencia_central` | `problema.descripcion`, `reto`, `producto_final` | Plano vs. objeto |
| `mapa.pis_nombre`, `pis_aporte` | `pis.nombre`, `aporte` (+ `aplica`, `descripcion`, `justificacion_na`) | Plano vs. objeto con NA |
| `mapa.metodologias` lista de textos | `metodologias{clase_invertida{antes,durante,despues}, complementarias[]}` | Lista vs. estructura detallada |
| `momentos[].ra_referidos` | `momentos[].ra` | Nombre |
| `momentos[].rubrica{evidencia, ra_citados[], filas[]}` | `momentos[].rubrica` = lista de filas | Objeto vs. lista |
| `momentos[].recursos` (opc.) | `momentos[].recursos` (**obligatorio**) | Obligatoriedad |
| `sesiones[].fecha_inicio`, `fecha_fin` (rango) | `sesiones[].fecha` (un día) | Rango vs. fecha única |
| `sesiones[].docente.actividad` (y `practico`, `autonomo`) | `sesiones[].docente.texto` | Nombre |
| `sesiones[].docente_asincronica{actividad,horas}` | `sesiones[].docente.asincronica{texto,horas}` | Ubicación y nombre |
| `rubrica_producto_final{evidencia, filas[]}` | `rubrica_producto_final` = lista de filas | Objeto vs. lista |
| `bibliografia` (opc.) | `bibliografia` (**obligatorio**) | Obligatoriedad |
| Filas de rúbrica `{indicador, niveles{5}}` | Igual | **Idéntico** |
| `resultados_aprendizaje[]{id, texto, evidencia}` | Igual | Mismos campos; distintas reglas (ver 3) |
| `habilidades_blandas`, `inclusion`, `competencia_perfil`, `competencia_pf`, `contribucion_perfil`, `prerrequisitos`, `correquisitos`, `uoc`, `modalidad`, `creditos`, `politica_ia`, `evidencia`, `titulo`, `contenidos` | Igual | **Idénticos** (con distinto agrupamiento) |

## 2. Campos sin equivalente

**Del validador que el 2.0 no tiene (9):** `documento.id`, `documento.estado`, `documento.generado`, `momentos[].totales` (fila «Total» del sílabo), `momentos[].rubrica.ra_citados` (RA de la cabecera de la rúbrica), `momentos[].rubrica.evidencia`, `rubrica_producto_final.evidencia`, `sesiones[].fecha_fin` (rango de fechas) y `presentacion.horario_practico`. El validador usa varios en sus reglas: `totales` en NUM-07 y NUM-08, `ra_citados` en RA-03 y RA-11, `documento.id` en el puente con el PIS.

**Del 2.0 que el validador no tiene (los que pide la Escala general de evaluación de la UTI):** `aplica` y `justificacion_na` de los 6 ejes, del PIS y de la credencial (NA de la escala); `ods`, tipo de internacionalización y disciplinas; `pis.descripcion`; clase invertida (antes, durante y después) y, por metodología, `tipo`, `justificacion` y `aplicada_en`; todo el bloque `evaluacion` (V.5 a V.12: proceso, agentes, retroalimentación, metacompetencia, gobernanza de IA, calificación con porcentajes, mejora y credencial).

## 3. Reglas que deciden distinto (mismo JSON)

| Caso | Validador | Generador 2.0 |
|---|---|---|
| 5 resultados de aprendizaje | Acepta | Rechaza (máximo 4, `RA1` a `RA4`) |
| RA numerados RA1, RA3 | Acepta | Rechaza (regla: en orden, sin saltos) |
| Tabla de RA vacía | Acepta (lo marca como faltante) | Rechaza (mínimo 1) |
| Sin momentos / momento sin sesiones | Acepta | Rechaza (mínimo 1) |
| Nivel 13 | Rechaza (1–12) | Acepta |
| Metacompetencia fuera del catálogo | Acepta | Rechaza (regla 4) |
| Clave no prevista | Rechaza (contrato cerrado) | Rechaza también en su propio formato (contrato cerrado) |
| Horas de una sesión vacías (`null`) | Acepta: «el documento no tiene el dato» | **No admite `null`**: exige número; el adaptador pone 0, lo que el validador prohíbe (regla 5: nunca rellenar con 0) |
| Dos metacompetencias marcadas | Acepta | Solo guarda una (se pierde la segunda) |
| Eje fuera de los 6 | Acepta | No tiene dónde guardarlo (se pierde) |
| Créditos, horas totales, fecha de sesión o política de IA vacías | Acepta | Acepta |

La causa de fondo es distinta en cada sistema. El validador debe **aceptar sílabos incompletos o defectuosos** para diagnosticarlos; el Generador **exige un mínimo para poder generar** (al menos un RA, un momento, una sesión). Las dos posturas son correctas para su función, pero con un solo contrato tienen que separarse: el esquema común debe aceptar lo que el validador acepta, y los mínimos del Generador deben ser reglas aparte, «requisitos para generar».

## 4. Pruebas empíricas

| Prueba | Resultado |
|---|---|
| Ejemplo 6.1 del validador contra el esquema derivado | Válido |
| 15 sílabos de Ingeniería 2026 (PDF → 2.0) convertidos al validador | 15/15 válidos |
| Corpus B26 anterior (82 archivos, 1.0 → 2.0) convertidos al validador | 82/82 válidos |
| Ejemplos 2.0 (completo y mínimo) convertidos al validador | 2/2 válidos |
| Ejemplo del validador convertido al 2.0 | Cumple esquema y reglas 2.0 y entra al sistema sin avisos |
| Mismo ejemplo sin `facultad` o sin `fecha_aprobacion` (opcionales en el validador) | El 2.0 lo rechaza |
| Ida y vuelta 2.0 → validador → 2.0 | Se pierden todos los campos de la escala de la sección 2; la metacompetencia vuelve normalizada a su forma oficial |

Los «válidos» del Generador hacia el validador se logran rellenando lo que el 2.0 no tiene: `documento` con valores provisionales, `totales` y evidencias de rúbrica en `null`, `ra_citados` vacío. El esquema los acepta, pero varias reglas del validador (NUM-07, NUM-08, RA-03, RA-11) quedarían sin dato.

## 5. Propuesta para un solo contrato

1. **Un solo esquema**, `silabo-api/0.2.0`, con la estructura por secciones del validador (más cercana al PDF y ya presentada a Sistemas), y sus 9 campos.
2. **Agregar al 0.2.0 lo que pide la escala**, desde el 2.0: NA con justificación en ejes, PIS y credencial; ODS, tipo de internacionalización y disciplinas; descripción del PIS; detalle de metodologías y clase invertida; bloque de evaluación V.5 a V.12.
3. **Decidir juntos la forma de los campos que hoy chocan:**
   - metacompetencias como lista de 5 con `marcada` (validador) o una del catálogo (2.0): la lista del validador conserva más información;
   - ejes como lista libre o 6 fijos con NA (la escala valora los 6 y su NA);
   - horario como texto u objeto;
   - sesión con rango de fechas o una sola;
   - horas `null` permitidas o no.
4. **Reglas aparte para cada sistema sobre el mismo esquema:** el validador acepta todo lo que cumple el esquema y diagnostica; el Generador agrega sus «requisitos para generar» (1 a 4 RA en orden, al menos un momento y una sesión con fecha, metacompetencia del catálogo).
5. **El Generador consume el 0.2.0 con un adaptador** hacia su formato interno, como ya hace con el 2.0. La generación de recursos no cambia.
