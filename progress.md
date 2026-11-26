# Progreso — Generador de Recursos UTI · V2 (sílabos desde el SGA)

> **Para qué sirve:** es la memoria del proyecto V2. Al retomar, **se lee primero este archivo** y solo después, si hace falta, el documento puntual que enlaza.
>
> **Última actualización:** 2026-11-26 · **Bloque activo:** V3 — herramientas según el plan de evaluación del RRA (rama `V3-SilabosPesos`). Ver la sección *Bloque V3* justo abajo; el bloque V2 queda como historia.

## Cómo se actualiza

1. **Al cerrar una tarea** (aprobada por el revisor e integrada), el coordinador:
   - cambia su estado en el tablero;
   - anota fecha, commit, pruebas y desviaciones en *Bitácora*.
2. **Al tomar una decisión** que cambie el plan o el contrato, se registra en *Decisiones* con un enlace al documento modificado.
3. **Al abrirse o resolverse un bloqueo**, se actualiza *Bloqueos*.
4. Las entradas son **breves** (1–3 líneas). El detalle va en el commit o en `docs/`.
5. Nunca se borra la historia: lo resuelto se marca como resuelto, no se elimina.

Estados: `⬜ pendiente` · `🔄 en curso` · `🔁 devuelta (ronda n)` · `✅ hecha` · `⛔ bloqueada`

---

## Bloque V3 — herramientas según el plan de evaluación (RRA)

**Objetivo:** dejar de ofrecer todas las herramientas en todas las clases. Cada actividad del sílabo se clasifica (evaluable o de avance; calificación del RRA, instrumento, insumo previo) y el sistema ofrece solo lo que la prepara, con el peso que tiene en la nota. Mockup aprobado el 2026-11-26.

### Norma (decisiones del usuario)

| Modalidad | Contacto / práctico / autónomo | C5 sumativa | C4 proyecto | Bloques |
|---|---|---|---|---|
| Presencial | 45 / 30 / 25 (C1 5 · C3 20 · C5 20) | prueba acumulativa de cada parcial | todas las entregas | 2 parciales por fecha, cada uno 100 % |
| En línea y distancia | 55 / 20 / 25 (C1 5 · C3 10 · C5 40) | prueba + proyecto final | avances | un bloque |
| Semipresencial (híbrida) | 45 / 30 / 25 (C5 30) | ⏸ en espera | ⏸ | ⏸ — aviso «norma pendiente», sin pesos |

Fuentes: «3. Armonización del plan de evaluación con el RRA» y «2. Plan_de_evaluacion_PF_UTI _ Presencial». Supuesto por confirmar: nota final = promedio 50/50 de los parciales.

### Tablero V3

| # | Tarea | Estado |
|---|---|---|
| V3-0 | Commit de las cuentas locales de prueba (`a7720a6`) | ✅ hecha |
| V3-1 | Lector: filas partidas entre páginas y aviso de celdas cortadas | ✅ hecha |
| V3-2 | Norma por modalidad (tabla configurable) y parciales por fecha | ✅ hecha |
| V3-3 | Clasificador de actividades (rótulos y, sin rótulo, IA) | 🔄 en curso |
| V3-4 | Pesos sugeridos, suma por momento y parcial, auditor con alertas | ⬜ pendiente |
| V3-5 | API y pantalla de momentos del mockup (reemplaza el menú fijo por clase) | ⬜ pendiente |
| V3-6 | Herramientas nuevas: ficha de foro, guía de la práctica, guía de observación, guía de la tarea autónoma, diagnóstica, simulacro acumulativo, guía de la entrega, insumo de respaldo | ⬜ pendiente |
| V3-7 | Verificación con los 4 sílabos piloto, costo medido y documentación | ⬜ pendiente |

Sílabos piloto: Programación Estructurada (en línea), Electiva 2 (en línea), PPC (presencial), Electiva 5 (híbrida) — en `Desktop/SILABOS B26/`.

### Bitácora V3

- **2026-11-26 · V3-3 (parte 1, reglas):** `app/evaluacion/clasificador.py`:
  - Cada columna de cada sesión se clasifica por sus rótulos en evaluable o de avance. Las evaluables llevan su calificación del RRA, instrumento, finalidad y agente. El proyecto final va a C5 en la modalidad en línea y a C4 en la presencial.
  - Electiva 5 coincide 13/13 con su plan de evaluación aprobado (mismo instrumento y tipo); Programación Estructurada da 13 evaluables, Electiva 2 10 y PPC 26, todas con 0 columnas sin rótulo.
  - En los 60 sílabos B26 legibles (40 presenciales, 13 en línea, 7 híbridos): 386 evaluables (6,4 por sílabo, de 0 a 26) y **33 % de columnas sin rótulo**, concentradas en Salud (Adulto Mayor, Enfermería, Farmacología) y con «estudio de caso» muy usado (94).
  - ⛔ Pendiente de decisión del usuario: cómo clasificar lo que no trae rótulo (IA, el plan de evaluación del SGA o ambos).
  - Pruebas: `test_evaluacion_clasificador.py` 25 nuevas; suite estándar 1 451 pasan.
- **2026-11-26 · V3-2:** `app/evaluacion/norma.py` + `norma_rra.json`:
  - Tabla configurable con las seis calificaciones del RRA. Se valida al cargar: cada modalidad definida suma 100 y no admite calificaciones desconocidas.
  - Alias de modalidad: PRESENCIAL; EN LINEA, ONLINE y VIRTUAL; DISTANCIA (= en línea); SEMIPRESENCIAL o HIBRIDA (pendiente). Una modalidad desconocida devuelve `None`, sin pesos inventados.
  - Bloques por fecha: un solo bloque en línea; en presencial, el Parcial 1 cierra en la sesión de su prueba acumulativa («primer parcial») o, si no se reconoce, a la mitad del periodo; la norma pendiente no arma bloques.
  - Pilotos: PPC con P1 del 05/10 al 03/12 (cierra en M3-S4) y P2 del 07/12 al 11/02, 18 sesiones cada uno; los dos cursos en línea en un bloque; Electiva 5 pendiente. Pruebas: `test_evaluacion_norma.py` 21 nuevas.
- **2026-11-26 · V3-1:** lector (`ciencia_datos/lector_pdf/momentos.py`):
  - Una fila de sesión partida entre páginas ya no se pierde cuando su primera celda arrastra el final de la fecha («14/12/2026»).
  - Cada fila se lee con el mapa de columnas de su ancho, porque en la página siguiente la tabla puede llegar sin la celda combinada.
  - El traductor avisa las actividades que terminan en coma o en una palabra que exige continuación. El aviso da la ruta y nunca el texto.
  - Al subir el PDF, el docente ve esos avisos legibles («Momento 1, sesión 4 · trabajo autónomo»).
  - Recuperados: Programación Estructurada M1-S1 (diagnóstica y foro) y Electiva 5 M1-S4 (foro y ensayo) y M4-S3 (trabajo final).
  - En los 61 PDF de `SILABOS B26`, 11 celdas de otras facultades siguen cortadas, pero vienen así en el PDF del SGA (verificado en Patología Estomatológica M4-S4) y ahora generan aviso. `Silabo SIstemas de Control.pdf` sigue ilegible; queda fuera del alcance.
  - Pruebas: backend 1 430 pasan (suite estándar); frontend 35 unitarias y 42 de navegador; tipos y build sin errores. E2E en local: cuenta de prueba, subida de Programación Estructurada (sin avisos) y Patología Estomatológica (3 avisos visibles en la pantalla).
  - Push de la rama `V3-SilabosPesos` a `origin` (primera vez) con autorización del usuario.
- **2026-11-26 · V3-0:** commit `a7720a6` de las cuentas locales (admin crea cuentas @indoamerica.edu.ec / @uti.edu.ec, PBKDF2, cambio obligatorio, PDF del sílabo). Pruebas de esa entrega: 1 428 backend y 34 frontend.

---

## Estado en una línea

V2 funcionalmente completa en la rama `v2/sga`: el docente ingresa con su usuario y clave del SGA, el sistema sincroniza sus materias y sus sílabos en JSON, los valida (esquema + 7 reglas) y genera las mismas 13 herramientas que V1 (equivalencia: 59/59 huellas iguales). Documentación hecha y hallazgos de la revisión final corregidos. **Falta:** el adaptador real del SGA (B-SGA1, TI), la verificación E2E final y el push.

## Origen

- **V1:** https://github.com/CZurita14/Agente-GenRecursos (`main` = `011bd68`). Su historia (P1–P10) y sus planes quedan allí.
- **Contrato del sílabo:** [docs/api-silabo/](docs/api-silabo/). Pasadas en V1: 23/23 prompts idénticos, 31/32 campos consumidos.

## Tablero

| # | Tarea | Estado |
|---|---|---|
| 0 | Copia limpia y `progress.md` | ✅ hecha |
| 1 | Contrato en el código e integridad | ✅ hecha |
| 2 | Proveedor SGA, traductor, SGA simulado y esquemas de materias y autenticación | ✅ hecha |
| 3 | Sincronización de materias y sílabos | ✅ hecha |
| 4 | Ingreso con el SGA | ✅ hecha |
| 5 | API de materias y eliminación del PDF | ✅ (incluye la 7) |
| 6 | Frontend | ✅ hecha |
| 7 | Ciencia de datos con JSON | ✅ (fusionada en la 5) |
| 8 | Equivalencia con V1 y herramienta de comparación | ✅ hecha |
| 9 | Documentación, verificación final y entrega | ✅ documentación (la verificación E2E final y el push los hace el coordinador) |

## Bloqueos

- **B-SGA1 (abierto):** TI debe definir el mecanismo de autenticación del SGA, las consultas de materias y sílabo y una cuenta o entorno de prueba. Hasta entonces se valida contra el SGA simulado.

## Decisiones

- **2026-11-09:**
  - La autenticación es la del SGA, para que el docente tenga las mismas materias que en el SGA.
  - Se elimina por completo la entrada por PDF.
  - El sistema no aprueba sílabos: consume y genera.
  - La V2 parte de una copia limpia, sin el historial de V1.
- **2026-11-09:**
  - La clave del SGA no se guarda: se sincroniza todo al ingresar.
  - El acceso lo define solo el SGA, así que se quita «compartir».
  - Un sílabo por código PF, compartido entre paralelos.
- **2026-11-09:**
  - Se elimina «compartir» (servicio, endpoints, ruta de auditoría y modelo); la tabla `asignatura_acceso` y los roles se conservan.
  - `asignatura.activa_sga` (migración `009_sga.sql`): al sincronizar, una asignatura cuya materia el SGA ya no lista queda inactiva (404 y fuera del listado); nunca se borra y vuelve si la materia regresa.
  - Una asignatura por `(docente, codigo_pf)`: dos paralelos son dos filas de `materia_sga` apuntando a la misma.
- **2026-11-09:**
  - Se elimina el SMTP por completo (`app/auth/correo.py`, campos `smtp_*`, variables en `.env.example`, `infra/`) y con él `/auth/codigo` y `/auth/verificar`; el ingreso es `POST /auth/ingresar` contra el SGA.
  - El bloqueo sigue la convención de V1: 5 claves erróneas seguidas por usuario → **429** «Demasiados intentos» con `Retry-After: 900` (no 423). Tabla `auth_bloqueo` (`010_auth_sga.sql`, con una columna `actualizado` para limpiar contadores viejos); `auth_reto` se elimina.
  - Cuotas: `limite_ingresar_usuario_minuto` (20) y `limite_ingresar_ip_minuto` (60) reemplazan las cuatro de código/verificar.
- **2026-11-09:** El contrato también define los JSON de la lista de materias y de la autenticación (Tarea 2).
- **2026-11-10 (revisión final):**
  - La migración `011_acceso_solo_sga.sql` borra las sesiones de V1 (`auth_sesion`) para forzar un ingreso por el SGA, y los accesos compartidos de V1 (`asignatura_acceso`): el acceso lo define solo el SGA. La tabla y los roles se conservan; solo la escribe un administrador en la base.
  - Presupuesto de sincronización `SGA_SINCRONIZACION_MAX_S` (45 s por omisión, menor que los 65 s del proxy): al agotarse no se piden más sílabos y las materias restantes quedan `no_disponible`, con su versión anterior y sus asignaturas activas.
  - `SGA_PROVEEDOR` pasa a `real` por omisión: el validador de `Ajustes` rechaza `simulado` en producción y, con el simulado, exige una carpeta con `usuarios.json` (relativa a la raíz).
  - El usuario llega al SGA sin pasar a minúsculas; solo el bloqueo y la cuota lo normalizan. El correo del SGA se normaliza antes de escribir nada (otro dominio → 403).

## Bitácora (lo ya hecho)

### 2026-11-09
- **Tarea 0:**
  - Se exportó V1 `011bd68` con `git archive`, sin `docs/propuestas/`, `Silabos/` ni `.env`.
  - Los planes P1–P10 quedan en V1. `progress.md` es nuevo.
  - Pruebas (`-m "not servidor and not modelo"`): 1216 pasan y 23 se saltan solo porque piden un PDF de `Silabos/`, que no se versiona (1216 + 23 = 1239, igual que V1). 14 deseleccionadas.
  - Con `.venv-ciencia`, `-m modelo` en `test_razonador.py` + `test_cd_*.py`: 10 pasan. Frontend: 25 pasan.
- **Tarea 1:** `SilaboUTI` acepta el contrato JSON (9 campos pasan a opcionales) y `app/silabo/integridad.py` añade `cargar_silabo` y `SilaboInvalido` con fallos `ruta: regla` sin valores. Pruebas: `test_contrato.py` 11 nuevas; suite estándar 1227 pasan, 23 se saltan (1216 + 11 nuevas).
- **Tarea 2:** `app/sga/` (interfaz `ProveedorSGA`, traductor de lista blanca, SGA simulado con fixtures `S91-SIMU-…`, real pendiente de TI), esquemas `materias-api` y `auth-sga` con ejemplos, y 3 campos en la configuración. Sin `jsonschema`: las pruebas leen las claves de los esquemas. Pruebas: `test_sga_proveedor.py` 22 nuevas; suite estándar 1249 pasan, 23 se saltan (1227 + 22 nuevas).
- **Tarea 3:** `app/sga/sincronizar.py` y migración `009_sga.sql` (`materia_sga`, `asignatura.activa_sga`); una transacción por materia, estados `importada/sin_cambios/no_disponible/invalida`. Se quita «compartir». Pruebas: `test_sga_sincronizar.py` 10 nuevas, 3 nuevas y 4 borradas de «compartir» en `test_asignaturas_api.py`; suite estándar 1259 pasan, 23 se saltan (1249 + 10).
- **Tarea 4:** `POST /auth/ingresar` (bloqueo → SGA → sincronización → sesión con la misma cookie de V1); la clave solo es un parámetro local (pruebas con `caplog` y búsqueda en todas las columnas de texto). Si la sincronización falla se entra igual y solo se registra el nombre de la excepción. SGA caído → 503 sin contar fallo. Se borra `test_correo_auth.py` y se reescribe `test_auth.py` (32 casos); `test_control_api.py` cambia las cuotas de código por las de ingreso. Suite estándar 1247 pasan, 23 se saltan (1259 + las nuevas − las del código por correo; la base citada era 1261).
- **Tareas 5 y 7 (fusionadas):** `GET /materias` (solo las del docente, por `codigo_pf` y `paralelo`); se borra la entrada por PDF (`POST /silabos`, `app/silabo/lector/`, `aislado.py`, `pdf_*`, `limite_pdf_correo_hora`, `lector_pdf`, `SilaboIlegible`) y `pdfplumber` sale de las dependencias de la API (queda solo en `dev` y en la etapa de pruebas de la imagen, porque las pruebas de exportación leen el PDF generado). La 7 se fusiona porque borrar el lector rompía `ciencia_datos/corpus.py`: ahora solo lee `.json` (`a_contrato` + `cargar_silabo`), ignora los `.pdf` con un aviso y su conteo. `compose.yaml` pasa `SGA_*`; nginx `client_max_body_size 1m`. Pruebas borradas: `tests/lector/` y 2 archivos de PDF más casos sueltos; nuevas: `test_materias_api.py` (4), 3 en `test_cd_corpus.py` y 1 en `test_infra_config.py`. Suite estándar: 1173 pasan, 0 se saltan, 13 deseleccionadas (eran 14: se borró `test_prompt_de_momento_cabe`, marcada `servidor`, que leía PDFs reales). Ronda de corrección 1: se rehace esa prueba con los JSON del SGA (+ variante sin servidor), se convierte `test_criterio_2_reales` y `test_materias_api.py` pasa por `sincronizar`; suite estándar 1177 pasan, 14 deseleccionadas; `modelo`: 10 pasan; `test_materias_api.py`: 4.
- **Tarea 6:** frontend con el SGA: `Ingreso` pide usuario y clave (`type=password`, la clave se borra del estado tras cada respuesta, 401/429/503 con mensajes propios en `utils/materias.ts`); `Generar` lista `GET /materias` («CODIGO PARALELO n»), abre `importada`/`sin_cambios` en su menú y muestra desactivadas `no_disponible`/`invalida` con su motivo. Se quitan `subirSilabo`, `/auth/codigo`, `/auth/verificar` y `DropZone`. Pruebas: 28 unitarias (25 − 3 retiradas + 6 nuevas), 42 de navegador (Playwright, API simulada), typecheck y build sin errores.
- **Tarea 8:** oráculo de huellas generado con el código de V1 `011bd68` (`tests/fixtures/v1/generar_oraculo.py` + `huellas_silabo_datos.json`); `test_equivalencia_v1.py`: las 59 entradas (contexto, prompt, plan, requisitos, sin IA, menú, entrenamiento, agente) del fixture pasado por `a_contrato` + `cargar_silabo` son idénticas a V1, y los 3 sílabos del SGA simulado no cambian al quitar campos privados. `app/sga/comparar.py` (`python -m app.sga.comparar <sga> <ref>`: rutas y % de coincidencia, nunca valores) con `test_sga_comparar.py` (4).
- **Tarea 9 (documentación):** `README.md` reescrito para la V2 (flujo con el SGA, modelo matemático, SGA simulado, pruebas, equivalencia y lista de documentos de V1 como historia); `docs/sga/para-TI.md` (nuevo: qué debe entregar TI y dónde se conecta el adaptador); `docs/api-silabo/README.md` con los 3 contratos, las 7 reglas y el traductor; `ciencia-datos.md`, `operacion.md`, `entrega-ti.md` y `desarrollo-api.md` sin PDF, SMTP ni código por correo; `tests/fixtures/v1/README.md` con las dos aclaraciones de la Tarea 8. Solo documentación. Suite estándar: 1185 pasan, 14 deseleccionadas. Pendientes del coordinador: verificación E2E final y push.

### 2026-11-10

- **Revisión final, ronda única de correcciones** (hallazgos en `.superpowers/sdd/2026-11-09-v2-sga-json/revision-final-hallazgos.md`): correo del SGA normalizado antes de escribir (otro dominio → 403); migración `011_acceso_solo_sga.sql` (borra `auth_sesion` y `asignatura_acceso`); materias `no_disponible`/`invalida` con asignatura se abren con la última versión importada y `estadoMateria` usa lista blanca; `SGA_SIMULADO_DIR` relativa a la raíz y arranque que falla sin `usuarios.json`; `SGA_PROVEEDOR` `real` por omisión y `simulado` rechazado en producción por `Ajustes`; presupuesto `SGA_SINCRONIZACION_MAX_S` (45 s) con reloj inyectable; usuario sin minúsculas hacia el SGA; una sola consulta de materias (`ServicioAuth.materias` eliminado); `comparar` acepta paralelos idénticos y nombra el código si difieren; `horas` del esquema con sus 4 campos obligatorios; aviso de privacidad, README, `desarrollo-api.md`, `operacion.md`, `para-TI.md`, `.env.example` y comentario de `compose` al día; `onSubir` → `onGenerar`. Pruebas: suite estándar 1202 pasan, 14 deseleccionadas (1185 + 17 nuevas); frontend 30 unitarias (28 + 2), 42 de navegador, typecheck y build sin errores. Desviación: el default de `SGA_PROVEEDOR` cambia a `real` (con `simulado` por omisión, el validador de producción rechazaría toda configuración sin la variable). Informe: `.superpowers/sdd/2026-11-09-v2-sga-json/revision-final-correcciones.md`.

---

## Siguiente paso

1. Pedir a TI lo del bloqueo B-SGA1 con [docs/sga/para-TI.md](docs/sga/para-TI.md) y escribir `app/sga/real.py` cuando respondan.
2. Verificación E2E final (Qwen real, docker compose con el SGA simulado), revisión de toda la rama y push a `Agente-GenRecursos-V2` solo con aprobación del usuario.
