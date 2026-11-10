# API local: configuración y pruebas

Desde `backend`, con el PostgreSQL configurado en `.env`:

```powershell
../.venv/Scripts/python.exe -c "from app.db.conexion import conectar; from app.db.migrar import aplicar_migraciones; c=conectar(); c.autocommit=True; print(aplicar_migraciones(c)); c.close()"
../.venv/Scripts/python.exe -m app.servidor
```

La API no aplica migraciones al iniciar. `004_auth.sql` crea las sesiones; el aplicador es idempotente. Las pruebas usan un esquema temporal por prueba, sin modificar las tablas de la aplicación.

## Configuración del ingreso

Definir `AUTH_SECRETO` con al menos 32 caracteres aleatorios en `.env` o en el almacén de secretos del despliegue. Sin ese secreto, `/salud` funciona y las solicitudes de ingreso responden 503. No copiar el valor de prueba ni guardarlo en Git.

El ingreso es con el SGA. Variables: `SGA_PROVEEDOR` (`real` por omisión, o `simulado`), `SGA_SIMULADO_DIR` (carpeta de fixtures, solo con el simulado), `SGA_TIMEOUT_S` (15 s por llamada) y `SGA_SINCRONIZACION_MAX_S` (45 s por omisión, menor que los 65 s del proxy: al agotarse, las materias restantes quedan `no_disponible` con su versión anterior). Con `ENTORNO=produccion` solo vale `real` (la configuración rechaza `simulado` al arrancar) y se exige un origen HTTPS exacto, sin ruta ni barra final. El adaptador real depende de TI (B-SGA1): [sga/para-TI.md](sga/para-TI.md). No hay SMTP ni código por correo.

Desarrollo con el SGA simulado: en el `.env` de la raíz, además de la base de datos y el servidor de IA, van estas cinco variables:

```text
ENTORNO=desarrollo
API_ORIGEN=http://localhost:5173
SGA_PROVEEDOR=simulado
SGA_SIMULADO_DIR=backend/tests/fixtures/sga
AUTH_SECRETO=<al menos 32 caracteres aleatorios propios>
```

`SGA_SIMULADO_DIR` es relativa a la raíz del proyecto, no a la carpeta desde la que se arranca la API; si la carpeta no tiene `usuarios.json`, la API no arranca y lo dice. `AUTH_SECRETO` se genera una vez, por ejemplo con `python -c "import secrets; print(secrets.token_urlsafe(48))"`, y no se versiona ni se comparte. `API_ORIGEN` es el origen del servidor de Vite, que reenvía `/api/*` a la API.

`ACCESO_PRUEBA=true` (solo desarrollo; la configuración lo prohíbe en producción) habilita `POST /auth/prueba`, que abre sesión sin autenticar contra el SGA.

## Contrato de autenticación

- `POST /auth/ingresar`, JSON `{"usuario":"...","clave":"..."}`: reserva el intento, autentica contra el SGA, sincroniza las materias y los sílabos del docente y abre la sesión. Devuelve `{"correo": ..., "materias": [...]}` y la cookie de sesión. La clave solo vive como parámetro local: no se guarda, no se registra y el modelo del cuerpo no la muestra en su `repr`. Credenciales rechazadas: 401. Quinto fallo seguido por usuario: 429 con `Retry-After: 900` (bloqueo de 15 minutos). SGA caído: 503, sin contar el intento. Si la sincronización falla a medias, el docente entra igual con lo ya sincronizado.
- `GET /materias`: las materias del docente (`id_sga`, `codigo_pf`, `paralelo`, `nombre`, `carrera`, `estado_sga`, `estado` de importación `importada | sin_cambios | no_disponible | invalida`, `asignatura_id`).
- `GET /auth/yo`: correo del usuario autenticado y rol `docente` o `administrador`, según la lista explícita de configuración; no es un rol que pueda elegir el cliente.
- `POST /auth/salir`: elimina la sesión en PostgreSQL y la cookie en el cliente.

Las escrituras exigen `Origin` exactamente igual a `API_ORIGEN`, incluso antes de abrir sesión. Las cookies siempre son `Secure`, `HttpOnly`, `SameSite=Lax`, sin atributo Domain. En desarrollo basta `npm --prefix frontend run dev`: el navegador ve un solo origen, `http://localhost:5173`, y el proxy de Vite reenvía `/api/*` a la API en `http://127.0.0.1:8001`. Chrome, Edge y Firefox aceptan cookies `Secure` en `localhost` aunque sea HTTP, así que no hace falta HTTPS local. Fuera de `localhost` sí se necesita HTTPS. TestClient usa una URL HTTPS y no necesita certificados.

El servidor invalida sesiones tras 8 horas sin actividad y siempre a los 7 días de creación. No basta una cookie inventada. El bloqueo se guarda con un seudónimo del usuario (HMAC con `AUTH_SECRETO`): quien teclea su clave en el campo de usuario no la deja en la base. La BD solo almacena SHA-256 de los tokens de sesión. Las esperas de lock del bloqueo se limitan a 2 segundos.

## Verificación

```powershell
../.venv/Scripts/python.exe -m pytest tests/test_auth.py tests/test_sga_proveedor.py tests/test_sga_sincronizar.py tests/test_materias_api.py tests/test_api.py -q
../.venv/Scripts/python.exe -m pytest -m "not servidor and not modelo" -q
```

Incluye bloqueo, vencimiento de sesión, revocación, TLS y que la clave no aparezca en trazas ni en columnas de texto. Las pruebas concurrentes retienen una fila y comprueban en `pg_stat_activity` que los competidores esperan un lock antes de liberarla. No activan el humo GPU salvo que se configure `LLM_REAL=1`.

## Asignaturas y sílabos

Aplicar también las migraciones `005_asignatura_acceso.sql`, `009_sga.sql` (`materia_sga`, `asignatura.activa_sga`), `010_auth_sga.sql` (`auth_bloqueo`) y `011_acceso_solo_sga.sql` con el mismo comando del inicio. `011` cierra las sesiones abiertas con V1 (el siguiente ingreso pasa por el SGA) y borra los accesos compartidos de V1 de `asignatura_acceso`. La tabla y sus roles (`editor`, `lector`) se conservan, pero ninguna ruta de la API la escribe: solo un administrador, directamente en la base de datos. El UUID identifica la asignatura, no su código PF. **No hay carga de sílabos por la API**: llegan del SGA al ingresar. Hay una asignatura por docente y código PF; dos paralelos son dos filas de `materia_sga` que apuntan a la misma. El acceso lo define solo el SGA: una asignatura cuya materia ya no aparece en la lista queda inactiva (404 y fuera del listado), nunca se borra y vuelve si la materia regresa. No hay «compartir».

- `GET /asignaturas`: lista las activas del docente, sin el cuerpo del sílabo.
- `GET /asignaturas/{UUID}/menu`: menú y versión. Una asignatura ajena devuelve 403; una inexistente o inactiva, 404.

Cada sílabo pasa por el traductor de lista blanca y por la validación de esquema y de las 7 reglas de integridad ([api-silabo/README.md](api-silabo/README.md)). Si su `version` no cambió respecto de la guardada, la materia queda `sin_cambios`; si cambió, se reemplaza la versión conservando el UUID y se informan las clases cuyo contexto cambió (cambiar solo el número de versión no marca clases). Los trabajos existentes conservan su instantánea del sílabo y los recursos previos mantienen su versión. Cada materia se procesa en su propia transacción: una falla no deshace las demás. Los mensajes de fallo nombran rutas de campo, nunca valores del sílabo.

```powershell
../.venv/Scripts/python.exe -m pytest tests/test_asignaturas_api.py tests/test_asignaturas_concurrencia.py tests/test_sga_sincronizar.py tests/test_equivalencia_v1.py -q
```

## Generación y recursos (A4)

Aplicar también `006_recurso_edicion.sql`. Todas las rutas siguientes exigen sesión y acceso a la asignatura; las escrituras admiten solo dueño/editor.

- `GET /asignaturas/{UUID}/herramientas?ambito=clase`: catálogo de workers disponibles, con recomendadas primero y perfil sugerido. Actualmente cuestionario y ficha; momento/asignatura dan catálogo vacío hasta P3.
- `POST /asignaturas/{UUID}/generar`: encola un trabajo por herramienta y devuelve 202 con IDs. No llama directamente al modelo ni arranca workers desde la API.
- `GET /asignaturas/{UUID}/trabajos`: avance, estado del trabajo y vínculo al recurso. Los activos y pendientes aparecen antes que el historial cerrado. No incluye sílabo, instrucciones, mensajes ni identificación interna del worker.
- `GET /asignaturas/{UUID}/recursos`: listado de metadatos. Ambos listados aceptan `limite` (predeterminado 50, máximo 200) y `desde` (offset).
- `GET /asignaturas/{UUID}/recursos/{recurso_UUID}`: contenido, evidencia original, revisión y marca de cambio del sílabo; un recurso de otra asignatura bajo un UUID de asignatura propia da 404.
- `PUT /asignaturas/{UUID}/recursos/{recurso_UUID}`: guarda edición docente con JSON `{"revision":0,"contenido":...}`. Una revisión obsoleta devuelve 409; recargar antes de volver a guardar.

Ejemplo de solicitud de generación:

```json
{"ambito":{"tipo":"clase","id":"M2-S1"},"herramientas":["cuestionario"],"cantidad":12,"perfil_dificultad":"fundamentacion","instrucciones":""}
```

Cantidad entera 1–40, instrucciones hasta 4000 caracteres y perfil opcional (`fundamentacion`, `profesional`, `avanzado`). Se valida toda la selección antes de confirmar la transacción. El perfil elegido y el sílabo se conservan en el trabajo aunque el docente suba una nueva versión antes de ejecutarlo. El worker existente consume esa cola mediante `python worker.py` desde `backend`.

Las modificaciones reales se guardan junto al historial y a sus verificaciones deterministas en una misma transacción; el cliente no puede elegir autor, estado, evidencia ni uso para mejora. Quedan `requiere_revision`, con `evidencia_vigente=false`; los veredictos originales se mantienen como trazabilidad de generación, sin atribuirlos al contenido editado. `verificacion_edicion` corresponde al nuevo texto. Guardar contenido idéntico no crea una revisión ni invalida la evidencia. Que la evidencia esté vigente solo significa que corresponde al contenido; no implica aprobación académica, y los cuestionarios conservan la marca de borrador H8.

El trabajo conserva su estado de cierre original; los campos `recurso_estado` y `recurso_revision` del polling reflejan posteriores ediciones del recurso. Las preguntas admiten texto y cambios de nivel, reordenación y eliminación de ítems existentes (sin quedar vacío), pero no nuevos IDs. Se rechazan RA/contenidos de otra clase, campos extra y opciones/clave mal formadas. El editor admite la misma alternativa de título de momento que P1 cuando no hay contenidos explícitos y conserva las advertencias del verificador. Para fichas exige las secciones conceptual/aplicacion. La pertenencia se comprueba contra la instantánea original; si falta, no se permite editar sustituyéndola por el sílabo vigente.

El cuerpo JSON tiene máximo 1 MiB y recepción de 30 s, antes de su decodificación. Las preguntas editadas tienen 25–1000 caracteres para acotar la comparación de duplicados; la validación no compara textos gigantes. El historial operativo tiene `uso_mejora=false`: no alimenta automáticamente reglas ni entrenamiento.

```powershell
../.venv/Scripts/python.exe -m pytest tests/test_generacion_api.py tests/test_edicion_validacion.py tests/test_cuerpo_json.py -q
```

## Cuotas, acceso administrativo y privacidad (A5)

Aplicar también `007_control_acceso.sql`. `AUTH_SECRETO` habilita tanto autenticación como control; no se admite inyectar una autoridad de autenticación sin configurar la clave del control. Sin esa clave solo quedan operativas las rutas públicas y el ingreso responde 503.

Las cuotas persisten en PostgreSQL y se suman entre instancias y sesiones. Usan ventanas fijas UTC y reloj de PostgreSQL, no del host API. Al exceder una se devuelve 429 con Retry-After; se cuentan intentos, no únicamente operaciones exitosas. Reiniciar con la misma clave no reinicia los contadores. Rotar la clave cambia los seudónimos y requiere una decisión operativa, no un reinicio rutinario.

| Configuración | Predeterminado | Unidad |
|---|---:|---|
| `LIMITE_IP_MINUTO` | 600 | solicitudes por IP/minuto |
| `LIMITE_USUARIO_MINUTO` | 120 | solicitudes por correo autenticado/minuto |
| `LIMITE_INGRESAR_IP_MINUTO` | 60 | intentos de ingreso por IP/minuto |
| `LIMITE_INGRESAR_USUARIO_MINUTO` | 20 | intentos de ingreso por usuario (seudónimo)/minuto |
| `LIMITE_GENERAR_CORREO_HORA` | 30 | peticiones de generación por correo/hora, antes de encolar |
| `LIMITE_EDITAR_CORREO_MINUTO` | 30 | guardados de recurso por correo/minuto |

Son valores técnicos iniciales para ajustar al piloto, la IP compartida institucional y la capacidad que confirme TI. No sustituyen los cinco intentos/15 minutos de A2 ni los límites de recepción de A3/A4.

Cerrar sesión no consume la cuota general del usuario: agotarla no debe impedir que el titular revoque una sesión utilizada por terceros. Sigue exigiendo sesión y origen válidos, y conserva el límite general de IP.

`ADMINISTRADORES` y `PROXIES_CONFIABLES` usan listas JSON en el entorno. Ambas están vacías por defecto. Por ejemplo, el formato de administradores es `["correo-institucional-designado@uti.edu.ec"]`; sustituirlo por los correos que autorice la institución. La membresía se comprueba en el servidor a partir de la sesión verificada. No confiar en cabeceras de rol. Un administrador no obtiene por ese rol permisos sobre asignaturas ajenas.

`GET /admin/consumo?desde=2026-10-01&hasta=2026-10-07` exige administrador; devuelve llamadas, tokens, segundos y fallos por rol y total. Rango inclusivo UTC de máximo 31 días, predeterminado siete; no devuelve prompts, correos ni IDs de asignatura/recurso.

El arranque recomendado `python -m app.servidor` desactiva `proxy_headers` y `access_log` de Uvicorn. Si TI usa su CLI directamente, debe conservar `--no-proxy-headers --no-access-log`. La aplicación también deshabilita `uvicorn.access` al iniciar. Configurar por separado los registros del proxy para no guardar URLs con destinatarios o parámetros privados.

La IP procede del transporte. X-Forwarded-For solo se procesa si el salto directo pertenece a `PROXIES_CONFIABLES`, definido con IP/CIDR concretos de los proxies; no se permite confiar en todo Internet. Se recorre desde la derecha hasta el primer cliente no confiable y no se usa su prefijo aportado por terceros. Una cadena inválida se rechaza con 400 y un bucket separado, sin consumir la cuota de la IP del proxy; repeticiones pueden recibir 429. El proxy de entrada debe sanear o reconstruir esa cabecera.

`acceso_api` guarda solo operación abstracta, método, estado, milisegundos e identificadores HMAC de IP/actor. No guarda cuerpo, query, ruta dinámica, cookie, IP ni correo en claro. Los rechazos 429 se muestrean como máximo uno por IP y ventana de minuto; no es un contador completo de todos los rechazos. Un fallo de bitácora emite solo el tipo de excepción y no convierte una operación ya confirmada en un error reintentable. Si falla el control previo de cuotas/BD, la operación responde 503.

La retención técnica de accesos es de 30 días (`AUDITORIA_RETENCION_DIAS`), propuesta configurable pendiente de revisión institucional. Este comando elimina accesos antiguos, cuotas vencidas, sesiones inválidas y retos caducados; no elimina asignaturas, recursos ni historial de ediciones:

```powershell
../.venv/Scripts/python.exe -m app.control.mantenimiento
```

No se ejecuta automáticamente al iniciar. TI debe programarlo y supervisarlo en P7; sin ejecutarlo no se garantiza el borrado físico al vencer la retención. La caducidad de sesiones sigue aplicándose al acceso aunque todavía no se hayan purgado sus filas.

`GET /privacidad`, con sesión, devuelve únicamente una vista del [borrador técnico](privacidad-borrador.md), con `estado=borrador`. La institución debe completar responsable, base aplicable, canales y conservación del material académico antes de aprobarlo. P6 deberá presentar el texto institucional aprobado antes del ingreso; esta ruta no representa aceptación ni amplía las rutas API públicas.

```powershell
../.venv/Scripts/python.exe -m pytest tests/test_control_api.py tests/test_control_identidad.py tests/test_limites.py tests/test_mantenimiento_control.py -q
```

P4 queda implementado; siguen pendientes el SGA real (B-SGA1), administradores institucionales, aprobación del aviso, y despliegue P7 con HTTPS, proxy y mantenimiento. Las migraciones de desarrollo se prueban en esquemas temporales: aplicar explícitamente a la BD de aplicación al preparar el entorno.
