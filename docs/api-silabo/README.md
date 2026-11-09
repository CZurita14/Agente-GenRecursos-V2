# Contrato JSON del sílabo para la API institucional

Qué apartados del sílabo debe entregar la API para que el Generador de Recursos entrene su modelo y genere recursos. El esquema formal está en [silabo-api.schema.json](silabo-api.schema.json) (JSON Schema 2020-12).

## Regla de privacidad

La API **no** debe enviar la sección I (perfil, correo, teléfono, ORCID del docente) ni la VII (firmas). El esquema las rechaza: `additionalProperties: false` en todos los niveles.

## Apartados y para qué se usan

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

## Lo que encontró la corrida de prueba (2026-11-09)

- El esquema es válido y lo cumplen los 20 sílabos simulados y el fixture.
- En los 2 sílabos reales leídos del PDF, faltan datos en campos que sí se usan: actividad práctica (23,5 % de las sesiones vacías), autónoma (11,8 %) y entregables (64,7 %). La API debería entregarlos completos cuando existan.
- **Cambio pendiente en el sistema:** `SilaboUTI` exige hoy 9 campos que no usa: `metacompetencia`, `metodologias`, `pis`, `uoc`, `modalidad`, `creditos`, `horas` del proyecto formativo, `recursos` del momento y `horas` de cada actividad de sesión. Un JSON con solo los apartados obligatorios no entra hasta darles valores por omisión o rellenarlos al importar.
