# Contratos JSON con el SGA

La V2 recibe del SGA tres documentos JSON. Cada uno tiene un esquema (JSON Schema 2020-12) y un ejemplo en esta carpeta. Qué debe entregar TI para conectarlos: [../sga/para-TI.md](../sga/para-TI.md).

| Contrato | Esquema | Ejemplo | Para qué |
|---|---|---|---|
| Autenticación | [auth-sga.schema.json](auth-sga.schema.json) | [ejemplo-auth.json](ejemplo-auth.json) | Identidad del docente tras validar su usuario y clave: `usuario`, `correo` institucional y `nombre`. Nunca incluye la clave ni tokens |
| Materias | [materias-api.schema.json](materias-api.schema.json) | [ejemplo-materias.json](ejemplo-materias.json) | Lista de las materias del docente: `id_sga`, `codigo_pf`, `paralelo`, `nombre`, `carrera`, `estado` |
| Sílabo | [silabo-api.schema.json](silabo-api.schema.json) | [ejemplo-minimo.json](ejemplo-minimo.json) | El sílabo de una materia, con lo que el Generador de Recursos entrena y genera |

El código del proyecto formativo (`A99-AAAA-9-99999-9999`) identifica el sílabo: la materia lo trae en `codigo_pf` y el sílabo en `proyecto_formativo.codigo`; deben coincidir.

## Regla de privacidad

La API **no** debe enviar la sección I (perfil, correo, teléfono, ORCID del docente) ni la VII (firmas). Aunque lleguen, el sistema no las conserva: el **traductor de lista blanca** (`backend/app/sga/traductor.py`) copia solo las claves que declara `silabo-api.schema.json` y descarta todo lo demás sin mirarlo, y `SilaboUTI` rechaza cualquier campo desconocido. Una prueba exige que la lista blanca sea idéntica a la derivada del esquema. Los objetos que el esquema deja libres (`niveles`, `ra`, `contenidos`, `metodologias`, ...) pasan completos.

## Validación en dos pasos

1. **Esquema** (Pydantic, `SilaboUTI`): tipos, formatos y obligatoriedad según la tabla de abajo.
2. **Siete reglas de integridad** (`backend/app/silabo/integridad.py`), que acumulan todos los fallos:
   1. `momentos[i].numero`: no se repite.
   2. `momentos[i].ra[j]`: el resultado de aprendizaje existe en `resultados_aprendizaje`.
   3. `momentos[i].sesiones`: no está vacío.
   4. `sesiones[j].id`: tiene la forma `M<momento>-S<n>` y el momento coincide con el de su momento.
   5. `sesiones[j].id`: no se repite en el sílabo.
   6. `sesiones[j].fecha`: está dentro del periodo (`periodo.inicio` a `periodo.fin`).
   7. `sesiones[j].contenidos[k]`: no es una cadena vacía.

Los fallos se informan como `ruta: regla` (por ejemplo `momentos[0].sesiones[1].id: repetido`), nunca con el valor del sílabo. Un sílabo inválido no se importa: su materia queda como `invalida` y el docente ve el motivo; las demás materias siguen.

## Apartados del sílabo y para qué se usan

| Apartado | Entrena el modelo | Genera recursos | Obligatorio |
|---|---|---|---|
| `facultad`, `carrera` | Sí: agrupa y separa por facultad | Sí: elige el agente y el estilo | Sí |
| `proyecto_formativo.codigo` | Sí: separa entrenamiento y prueba por sílabo | Sí: identifica la asignatura | Sí |
| `proyecto_formativo.version`, `aprobado` | Sí: conserva la versión vigente | Sí: detecta cambios de versión | Sí |
| `proyecto_formativo.nombre`, `nivel` | No | Sí: título y perfil de dificultad | Sí |
| `periodo` (código, inicio, fin) | No | Sí: menú por semanas | Sí |
| `competencia_perfil` | No | Sí: prompt | Sí |
| `resultados_aprendizaje[]` (id, texto, evidencia) | Sí: texto | Sí: prompt, verificador, planificador | Sí |
| `problema` (descripción, reto, producto final) | No | Sí: prompt y guía del producto final | Sí |
| `momentos[]` (número, título, fechas, ra, evidencia, política de IA) | Sí: evidencia | Sí: contexto, entregables y regla de integridad | Sí |
| `momentos[].rubrica[]` | No | Sí: guía de evidencia y lista de verificación | Sí (puede ir vacía) |
| `momentos[].sesiones[]` (id, número, fecha, semana, contenidos) | Sí: contenidos | Sí: menú, focos y contexto de clase | Sí |
| `sesiones[].docente/practico/autonomo.texto` | Sí | Sí: actividades de la clase | Sí (pueden ir vacíos) |
| `sesiones[].entregables` | No | Sí: regla de no resolver entregables | No |
| `rubrica_producto_final[]` | No | Sí: guía del producto final | No |
| `competencia_pf`, `metacompetencia` | No | No (candidatas) | No |
| `pis`, `metodologias`, `bibliografia` | No | No: fuera del contexto hasta tener sílabos reales | No |
| `uoc`, `modalidad`, `creditos`, `horas`, `horario`, `recursos` | No | No | No |

Los apartados que hoy no se usan son **opcionales**: un JSON con solo los apartados obligatorios entra sin rellenar nada. Las `horas` de cada actividad de sesión y las `horas`, `uoc`, `modalidad`, `creditos` del proyecto formativo también son opcionales.

## Lo que encontró la corrida de prueba (2026-11-09, sobre V1)

- El esquema es válido y lo cumplen los 20 sílabos simulados y el fixture.
- En los 2 sílabos reales leídos del PDF, faltan datos en campos que sí se usan: actividad práctica (23,5 % de las sesiones vacías), autónoma (11,8 %) y entregables (64,7 %). La API debería entregarlos completos cuando existan.
