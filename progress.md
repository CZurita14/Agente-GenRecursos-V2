# Progreso — Generador de Recursos UTI · V2 (sílabos desde el SGA)

> **Para qué sirve:** es la memoria del proyecto V2. Al retomar, **se lee primero este archivo** y solo después, si hace falta, el documento puntual que enlaza.
>
> **Última actualización:** 2026-11-09 · **Bloque activo:** V2 — plan [2026-11-09-v2-sga-json.md](docs/superpowers/plans/2026-11-09-v2-sga-json.md). Siguiente: Tarea 6.

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

## Estado en una línea

V2 creada desde V1 `main` (`011bd68`): misma lógica de entendimiento del sílabo (razonador MiniLM/SimCSE, planificador, verificador, revisor) y de generación. Se reemplaza la entrada por PDF por el SGA en JSON.

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
| 6 | Frontend | ⬜ pendiente |
| 7 | Ciencia de datos con JSON | ✅ (fusionada en la 5) |
| 8 | Equivalencia con V1 y herramienta de comparación | ⬜ pendiente |
| 9 | Documentación, verificación final y entrega | ⬜ pendiente |

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

---

## Siguiente paso

1. Tarea 6.
2. Pedir a TI lo del bloqueo B-SGA1.
