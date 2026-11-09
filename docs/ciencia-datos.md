# Razonador entrenado · Guía para el área académica y para TI

**Estado:** implementado y probado solo con la prueba de humo (2 sílabos). **Está apagado** y no cambia nada de lo que hoy hace la aplicación hasta que alguien lo encienda a propósito. Los criterios de aprobación de la sección 5 son una **propuesta, pendiente de que el usuario los confirme** antes de la corrida real.

---

## 1. Qué decide el modelo y qué sigue haciendo Qwen

Al preparar una ficha, un cuestionario u otra herramienta, la aplicación primero arma un **plan**: de qué tratará cada pregunta (el «foco») y con qué situación concreta (el «caso»). Después Qwen redacta cada pregunta siguiendo ese plan.

El modelo entrenado, llamado **razonador**, solo interviene en el plan, y solo en dos decisiones:

| Decisión | Hoy | Con el razonador |
|---|---|---|
| **Temas** | Los focos se reparten de forma fija, sin saber cuáles se parecen entre sí. | Agrupa los focos por tema y reparte las preguntas recorriendo un foco de cada tema antes de repetir. Un cuestionario cubre más temas distintos. |
| **Casos** | Se descartan los casos que comparten palabras con el entregable del momento. | Además descarta los que **significan lo mismo** aunque usen otras palabras. Nunca acepta un caso que el filtro de palabras ya había descartado. |

**Qwen sigue redactando todo**: el enunciado, las opciones, la respuesta correcta y las explicaciones. Qwen no participa en el entrenamiento ni en la evaluación del razonador.

**Por qué no corrige claves de respuesta equivocadas.** El razonador cambia *lo que Qwen recibe*, no *lo que Qwen sabe*. Si Qwen marca una opción incorrecta como correcta, el razonador no lo detecta ni lo arregla. Ese problema requiere otro trabajo (ítems con cálculo automático y verificación de las claves) y sigue pendiente; la revisión docente sigue siendo necesaria. Una mejora en las preguntas finales solo se podrá afirmar al comparar, con Qwen real y revisión docente, las mismas clases con y sin razonador (sección 8).

Sin `RAZONADOR_RUTA` la generación es exactamente la de siempre. Si el razonador está encendido y falla en un trabajo, ese trabajo termina en error y no usa otro método. Los ajustes por chat no consultan el razonador.

---

## 2. Cuántos sílabos hacen falta

El modelo se entrena con el 70 % de los sílabos y se evalúa con el 30 % restante. La separación se hace **por sílabo** (nunca por fragmento), para que la evaluación no vea nada parecido a lo que estudió.

| Uso | Sílabos | Para qué sirve |
|---|---|---|
| Prueba de humo | 2 | Solo comprueba que el programa corre. **No mide calidad.** |
| **Mínimo para entrenar** | **4 por facultad, en al menos 5 facultades (20)** | Deja 3 para entrenar y 1 para evaluar en cada facultad (25 % de evaluación). |
| Recomendado | 4 por facultad en las 8 facultades (32) | Cubre todo el catálogo. |
| Separación 70/30 exacta | 10 por facultad en las 8 (80) | Solo si la universidad los entrega. |

Con menos sílabos el programa se niega a entrenar (salvo con la opción de humo). Hoy hay 2 PDF, ambos de Ingenierías.

Los sílabos reales contienen datos personales de los docentes: se guardan en `Silabos/` en el equipo de trabajo, **no se versionan**, y ningún informe ni mensaje de consola reproduce su texto, solo cifras.

---

## 3. Cómo etiquetar

Dos archivos CSV en `datos_cd/` (carpeta fuera del repositorio). Los llenan docentes; el equipo técnico solo los lee. Se pueden abrir y guardar con Excel eligiendo el formato **CSV UTF-8**: el programa acepta `,` o `;` como separador, según lo que use Excel en cada equipo. Si Excel muestra todo en una sola columna, use *Datos > Texto en columnas* con la coma como separador. Un archivo guardado en otra codificación se rechaza con un mensaje claro y sin gastar la evaluación.

### 3.1 `pares.csv`: ¿este caso se parece al entregable?

**Este archivo todavía no se puede generar con ninguna herramienta.** El equipo técnico debe prepararlo a mano (o con un programa que aún no existe) a partir de los casos de cada carrera y de los entregables de los sílabos; la ficha de etiquetado se entrega a los docentes ya con esas columnas llenas. Hasta entonces la evaluación real no puede correr (ver sección 8).

Cada fila es un par: un **caso** (la situación que se propondría en una pregunta) y una **evidencia** (el texto de un entregable del sílabo). El docente responde una sola cosa: ¿el caso es **lo mismo o casi lo mismo** que la evidencia, de modo que la pregunta le regalaría la respuesta al estudiante?

| Columna | Qué poner |
|---|---|
| `caso` | Texto del caso. Lo escribe el equipo técnico al preparar el archivo. |
| `evidencia` | Texto del entregable. Lo escribe el equipo técnico al preparar el archivo. |
| `codigo_pf` | Código del proyecto formativo de donde sale la evidencia. Lo escribe el equipo técnico. |
| `docente` | Un código o iniciales acordadas (por ejemplo `D1`, `D2`). **No escribir nombres ni correos.** |
| `parecido` | `sí` si se parecen; `no` si son situaciones distintas. También se aceptan `1`/`0`, `si`/`no`. |

Reglas:

- Se necesitan **al menos 60 positivos («sí») en el grupo de prueba, después de quitar desacuerdos**. Con 25 % de prueba y 40 % de «sí», eso suele exigir unos **600 pares** (600 × 25 % × 40 % = 60), y más si hay desacuerdos: 500 pares dan solo unos 50 positivos. El programa lo comprueba antes de gastar la evaluación y, si no alcanza, se niega a empezar.
- **Dos docentes** etiquetan por separado **al menos 100 pares en común**: con ellos se mide si los docentes coinciden entre sí (kappa).
- Si dos docentes responden distinto al mismo par, ese par no cuenta para el umbral, las métricas ni los 60 positivos (se informa cuántos fueron). Sí cuenta para el kappa, que mide justamente esos desacuerdos.
- Una celda vacía o con otra respuesta no se cuenta como «no»: se descarta y se cuenta aparte.

### 3.2 `temas.csv`: ¿este grupo de fragmentos tiene sentido como tema?

El programa agrupa los fragmentos del grupo de evaluación en unos 8 temas (`temas-para-revisar`) y escribe dos archivos por candidato: la lista `temas-revision-<versión>.csv`, con los fragmentos de cada grupo, y la plantilla `temas-plantilla-<versión>.csv`, con una fila por grupo y `docente` y `tiene_sentido` vacíos. El docente lee cada grupo en la lista y responde en la plantilla si todos sus fragmentos tratan de un mismo asunto reconocible.

| Columna | Qué poner |
|---|---|
| `huella_temas` | Identificador de esa agrupación. Ya viene escrito: no tocar. |
| `grupo` | Número del grupo. Ya viene escrito. |
| `docente` | Código del docente, como en `pares.csv`. |
| `tiene_sentido` | `sí` o `no`. |

**Importante:** hasta evaluar no se sabe si gana el modelo ajustado o el modelo base. Por eso los docentes deben juzgar los temas de **ambos candidatos** (se ejecuta `temas-para-revisar` sobre cada uno). Si falta algún grupo de cualquiera de los dos, la evaluación **no empieza**.

**Cómo armar `temas.csv`:**

1. Cada docente llena su copia de las dos plantillas, una por candidato, sin tocar `huella_temas` ni `grupo`.
2. Abra un archivo nuevo, deje una sola vez la primera línea (`huella_temas,grupo,docente,tiene_sentido`) y pegue debajo las filas llenas de todas las copias, de ambos candidatos y de todos los docentes.
3. Guárdelo como `datos_cd/temas.csv`, en formato CSV UTF-8.

Una fila con `docente` o `tiene_sentido` vacíos es un error, aunque sea de otra agrupación: la evaluación no empieza hasta completarla o borrarla.

---

## 4. Cómo se entrena y se evalúa (para el equipo técnico)

Se usa el entorno de entrenamiento `.venv-ciencia` (con PyTorch, solo CPU) y el modelo base ya descargado en la caché local. La consola puede ser Windows: no hace falta configurar nada especial.

Para crear el entorno, desde la raíz del repositorio (`.venv-ciencia/` no se versiona):

```text
python -m venv .venv-ciencia
.venv-ciencia/Scripts/python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv-ciencia/Scripts/python.exe -m pip install -e "backend[ciencia,dev]"
```

Las versiones no están fijadas. Cada modelo guarda en `metadatos.json`, bajo `versiones`, las de `torch` y `onnxruntime` y el opset con que se exportó; para repetir una exportación, instale esas mismas.

```text
cd backend
# 1. Candidato ajustado y candidato base (sin ajuste), con los sílabos reales
HF_HUB_OFFLINE=1 ../.venv-ciencia/Scripts/python.exe -m ciencia_datos.entrenar --silabos ../Silabos --salida ../modelos/v1
HF_HUB_OFFLINE=1 ../.venv-ciencia/Scripts/python.exe -m ciencia_datos.entrenar --silabos ../Silabos --salida ../modelos/base --sin-ajuste
# 2. Listas de temas para los docentes: una por candidato, con el mismo --k (8 por omisión)
... -m ciencia_datos.evaluar temas-para-revisar --modelo ../modelos/v1 --silabos ../Silabos --salida ../datos_cd/temas-revision-v1.csv
... -m ciencia_datos.evaluar temas-para-revisar --modelo ../modelos/base --silabos ../Silabos --salida ../datos_cd/temas-revision-base.csv
# 3. Con pares.csv y temas.csv completos, una sola evaluación
... -m ciencia_datos.evaluar --modelo ../modelos/v1 --base-modelo ../modelos/base --silabos ../Silabos
```

El valor de `--k` debe ser **el mismo** en `temas-para-revisar` y en `evaluar` (si se cambia en uno, se indica igual en el otro): la huella de los temas depende de él, y las filas de `temas.csv` solo valen para la agrupación con la que se juzgaron. Los sílabos pueden estar en subcarpetas de `Silabos/`; se conserva una versión por código de proyecto formativo. `entrenar` imprime cuántos sílabos usó de cada carpeta de primer nivel (`por_carpeta: …`), sin nombres de archivo: revise esa línea, porque un PDF ajeno en una subcarpeta entraría al corpus.

`entrenar` no sobrescribe: rechaza una `--salida` que ya tenga `metadatos.json` o `evaluacion.candado`.

Los informes de la prueba de humo (`pruebas/ciencia_datos/*-humo.json`) no se versionan: están en `.gitignore`.

La evaluación se hace **una sola vez por versión**: deja un candado en la carpeta de cada candidato y una segunda corrida se rechaza, igual que otra carpeta con el mismo nombre de versión si ya existe `pruebas/ciencia_datos/<versión>.json`. Si todo aprueba, marca como aprobada la carpeta elegida, fija su umbral y guarda en `huella_pesos` la huella de su grafo y sus pesos; si no, queda sin aprobar y no se puede cargar en producción.

Antes de tomar el candado, y sin calcular ninguna métrica, `evaluar` abre ambos modelos, lee los sílabos, comprueba la separación y su huella, los mínimos de muestra (60 positivos de prueba tras quitar desacuerdos y 100 pares comunes entre dos docentes) y que `temas.csv` traiga todos los grupos de ambos candidatos. Cualquier fallo sale con código 2 y un mensaje, sin gastar la evaluación: se corrige y se vuelve a ejecutar.

Cada candidato usa un base nuevo si el anterior ya se evaluó: el candado también queda en la carpeta del base. Para evaluar un segundo ajustado (`v2`), exporte otro base con otro nombre (`--salida ../modelos/base-v2 --sin-ajuste`). `--base-modelo` debe venir del mismo modelo de Hugging Face que el ajustado (`base` en `metadatos.json`) y tener la misma separación.

Nota: el modelo ajustado compite contra el base y puede perder. Con 20 a 32 sílabos hay pocos miles de fragmentos, que pueden no alcanzar para que el ajuste supere al modelo base. Si pierde, se usa el base: al terminar, la consola imprime `modelo_elegido` y su carpeta, y esa es la carpeta que se instala, aunque el informe lleve el nombre del ajustado.

---

## 5. Criterios de aprobación (PROPUESTOS, pendientes de confirmación del usuario)

El modelo se aprueba solo si **cumple todos**. Una medida que falte nunca cuenta como cumplida.

| Medida | Criterio propuesto |
|---|---|
| Umbral de parecido | Se elige solo con el 70 % de entrenamiento: el de mayor precisión con exhaustividad de al menos 0,90. |
| Casos en el 30 % de evaluación | Exhaustividad de al menos 0,85 (de cada 100 casos que los docentes dicen parecidos, el modelo descarta 85 o más). |
| Mejor que el filtro actual | Prueba de McNemar con p < 0,05 **y** más aciertos propios que el filtro de palabras actual (no basta con ser distinto: debe ser mejor). |
| Temas, separación | Silueta mayor que el percentil 95 de agrupar al azar. |
| Temas, estabilidad | ARI entre semillas de al menos 0,80 (la agrupación no cambia al repetirla). |
| Temas, juicio docente | Al menos 80 % de los grupos «tienen sentido». |
| Acuerdo entre docentes | Kappa de Cohen de al menos 0,60, con al menos 100 pares comunes. |
| Muestra de evaluación | Al menos 60 casos parecidos en el 30 % de evaluación. |
| Ajuste fino | Se conserva solo si supera al modelo base en F1 de evaluación; si no, se usa el base. |
| Generalización | Se repite dejando fuera cada facultad, y se informa la peor. |

---

## 6. Cómo leer el informe

Los informes quedan en `pruebas/ciencia_datos/` y **solo contienen cifras y huellas, nunca textos** de sílabos. Se leen así:

- **`aprobado`**: `true` solo si cumplió todos los criterios de la sección 5. Con `humo: true` es siempre `false`.
- **`criterios`**: una línea por criterio, `true` o `false`. El que dice `false` es el motivo del rechazo.
- **`medidas`**: las cifras detrás de cada criterio (exhaustividad, valor p de McNemar, silueta frente al azar, ARI, kappa, conteos).
- **`conteos`**: filas de etiquetas descartadas (fuera de grupo, con valor inválido, en desacuerdo). Se informan, pero no impiden decidir.
- **`modelo_elegido`**, **`version_elegida`** y **`nota_modelo`**: si ganó el ajustado o el base, y por qué. La carpeta aprobada es la de `version_elegida`, que puede ser la del base.

Los datos que impiden decidir no llegan al informe: un sílabo de prueba ausente, una huella de separación que no coincide o una muestra insuficiente detienen `evaluar` antes del candado. Si falta `pares.csv` o `temas.csv`, se escribe `<versión>-incompleta.json` con el `motivo`, sin candado y sin aprobar.
- Un valor `null` significa «no se pudo calcular» y **nunca** cumple un criterio.

### Resultado de la prueba de humo (2 sílabos)

Con los 2 PDF de Ingenierías (1 para entrenamiento, 1 para evaluación, 27 fragmentos) el entrenamiento y la evaluación corrieron de principio a fin: se generó el modelo, se exportó y el informe se escribió con `humo: true` y `aprobado: false`. **Este resultado no es una evaluación de calidad**: demuestra que el programa funciona, no que el modelo sea bueno. Con un solo sílabo de evaluación no hay etiquetas docentes ni conclusiones posibles.

---

## 7. Cómo encenderlo y apagarlo

| Acción | Cómo |
|---|---|
| **Apagado (por omisión)** | `RAZONADOR_RUTA` vacía o ausente. La generación es idéntica a la de siempre. |
| **Encender** | Solo TI y solo con un modelo **aprobado**: copiar la carpeta elegida por el informe (`modelo_elegido`, que puede ser la del base) al volumen `modelos` (montado de solo lectura en el contenedor `worker`), poner en el archivo de entorno `RAZONADOR_RUTA=/modelos/<versión>` y recrear el `worker`. Ver [entrega a TI](entrega-ti.md) y [operación](operacion.md). |
| **Apagar de nuevo** | Dejar `RAZONADOR_RUTA=` vacía y recrear el `worker`. |

Garantías:

- Solo el `worker` recibe `RAZONADOR_RUTA`; la API y los demás servicios no la ven.
- En producción el `worker` **no arranca** con un modelo ausente, dañado, de humo, sin aprobar o cuyos pesos no coincidan con los aprobados, y registra la causa en su bitácora. Nunca sigue en silencio sin el razonador.
- Un trabajo que se reanuda tras una caída conserva el plan que ya había decidido, aunque entretanto se haya instalado otro modelo.
- La imagen de producción no incluye PyTorch: solo `numpy`, `scikit-learn`, `onnxruntime` y `tokenizers`.

---

## 7 bis. Simulación y modelo preliminar

Mientras no haya sílabos reales suficientes, se puede entrenar un modelo **preliminar** con sílabos simulados (códigos `SIM-`) que Qwen redacta fuera de línea a partir de la carrera. Los 2 sílabos reales no entrenan: quedan como `control_real`.

Pasos, desde `backend/` (requieren el servidor de IA para el primero; los sílabos simulados quedan en `datos_cd/`, sin versionar):

```text
# 1. Piloto de 20 sílabos con Qwen
PYTHONUTF8=1 ../.venv/Scripts/python.exe -m ciencia_datos.simular --salida ../datos_cd --limite 20
# 2. Medidas del lote y muestra para revisión humana
HF_HUB_OFFLINE=1 PYTHONUTF8=1 ../.venv-ciencia/Scripts/python.exe -m ciencia_datos.revisar_lote --silabos ../datos_cd/silabos_simulados --salida ../datos_cd
```

Una persona revisa `simulacion/muestra-revision.csv` y marca `parece_real`; solo si el piloto pasa se sigue. Entonces se corre `simular` sin `--limite` (se puede repetir si se corta), se vuelve a ejecutar `revisar_lote` sobre el lote completo y, si no incumple criterios, se entrena:

```text
# 3. Candidato ajustado y candidato base, con la misma separación
HF_HUB_OFFLINE=1 PYTHONUTF8=1 ../.venv-ciencia/Scripts/python.exe -m ciencia_datos.entrenar --silabos ../Silabos ../datos_cd/silabos_simulados --salida ../modelos/preliminar-1
HF_HUB_OFFLINE=1 PYTHONUTF8=1 ../.venv-ciencia/Scripts/python.exe -m ciencia_datos.entrenar --silabos ../Silabos ../datos_cd/silabos_simulados --sin-ajuste --salida ../modelos/preliminar-1-base
# 4. Informe que compara ambos, sobre los mismos sílabos
HF_HUB_OFFLINE=1 PYTHONUTF8=1 ../.venv-ciencia/Scripts/python.exe -m ciencia_datos.preliminar --modelo ../modelos/preliminar-1 --base-modelo ../modelos/preliminar-1-base --silabos ../Silabos ../datos_cd/silabos_simulados --salida ../pruebas/ciencia_datos
```

`preliminar` escribe `<version>-preliminar.json` (no se versiona) y se puede repetir: no toma candado, no ajusta, no fija umbral y nunca escribe `aprobado`. Antes de medir comprueba que ambos modelos sean preliminares, que el base sea `--sin-ajuste`, que compartan la huella de separación y que los códigos de prueba y control estén entre los sílabos; si no, sale con código 2 sin escribir nada. Las cifras globales, por facultad y la silueta se miden solo sobre los fragmentos de los sílabos de prueba simulados; los reales solo se usan en `control_real`. Nunca se miden los de entrenamiento:

- `precision_5_carrera` y `precision_5_facultad`: de los 5 vecinos más cercanos (coseno) de otros sílabos, la parte con la misma carrera o facultad; globales y por facultad.
- `silueta_facultad` y la misma silueta con etiquetas barajadas (semilla 42): la primera debe superar claramente a la segunda.
- `control_real`: cada fragmento real busca sus 5 vecinos entre los simulados de prueba y se mide la parte de su misma facultad; es `null` si la facultad no tiene simulados. `n_control_real` recuerda que son solo 2 sílabos.

**Qué demuestra:** que el codificador ajustado agrupa por carrera y facultad mejor o peor que el base, sobre textos simulados de prueba con estructura coherente; los 2 sílabos reales solo dan una comprobación aparte (`control_real`) y no entran en las cifras globales. **Qué no demuestra:** calidad ni utilidad docente. Los textos los redactó Qwen, así que el informe lleva `apto_produccion: false` y su advertencia; la aprobación exige sílabos reales y etiquetas docentes (secciones 2 y 3).

---

## 8. Lo que falta y lo que no se sabe

Corrida real (depende de personas, no de código):

1. El área académica entrega al menos 20 sílabos según la sección 2.
2. El usuario confirma los criterios de la sección 5.
3. Docentes etiquetan los pares necesarios (unos 600, sección 3.1) y los temas de ambos candidatos. La lista de pares (caso, evidencia) todavía debe prepararla el equipo técnico a partir de los casos de cada carrera y los entregables de los sílabos; no hay una herramienta que la genere.
4. Se entrena, se evalúa **una sola vez** y se presenta el informe al usuario.
5. Solo si aprueba y el usuario lo decide, TI instala la carpeta elegida por el informe y define `RAZONADOR_RUTA`.
6. Se compara con y sin razonador en las mismas clases, con Qwen real y revisión docente. Una regresión logística multinivel se añadirá cuando existan esas 240 preguntas revisadas.

Límites conocidos: con 20 a 32 sílabos el ajuste fino puede no superar al modelo base; el razonador no corrige claves incorrectas; y cambia lo que Qwen recibe, no lo que Qwen sabe.
