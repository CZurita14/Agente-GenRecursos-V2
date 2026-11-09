# API local: configuración y pruebas

Desde `backend`, con el PostgreSQL configurado en `.env`:

```powershell
../.venv/Scripts/python.exe -c "from app.db.conexion import conectar; from app.db.migrar import aplicar_migraciones; c=conectar(); c.autocommit=True; print(aplicar_migraciones(c)); c.close()"
../.venv/Scripts/python.exe -m app.servidor
```

La API no aplica migraciones al iniciar. `004_auth.sql` crea retos y sesiones; el aplicador es idempotente. Las pruebas usan un esquema temporal por prueba, sin modificar las tablas de la aplicación.

## Configuración del ingreso

Definir `AUTH_SECRETO` con al menos 32 caracteres aleatorios en `.env` o en el almacén de secretos del despliegue. Sin ese secreto, `/salud` funciona y las solicitudes de ingreso responden 503. No copiar el valor de prueba ni guardarlo en Git.

El modo predeterminado es `ENTORNO=produccion`, `SMTP_MODO=deshabilitado` y `API_ORIGEN=https://localhost:5173`. Para consola de desarrollo definir explícitamente `ENTORNO=desarrollo` y `SMTP_MODO=consola`. Este modo imprime el correo y código en la terminal local: solo usarlo en desarrollo. En producción exige SMTP y un origen HTTPS exacto, sin ruta ni barra final. El SMTP de esta implementación usa STARTTLS (normalmente puerto 587), validación del certificado y timeout de 10 segundos. No admite conexión SMTP sin TLS ni TLS implícito de puerto 465.

Para SMTP definir `SMTP_HOST`, `SMTP_PORT`, `SMTP_REMITENTE`, `SMTP_USUARIO` y `SMTP_CLAVE`. La cuenta institucional sigue pendiente de TI (B4); las pruebas capturan los mensajes o simulan SMTP y no envían correos reales.

## Contrato de autenticación

- `POST /auth/codigo`, JSON `{"correo":"docente@uti.edu.ec"}`: respuesta uniforme para buzones aceptados o rechazados por SMTP. Solo admite exactamente `uti.edu.ec` e `indoamerica.edu.ec`. Intervalo mínimo de reenvío: 60 segundos.
- `POST /auth/verificar`, JSON con `correo` y `codigo`: código de seis dígitos, 10 minutos, un solo uso. Quinto fallo: 429 y bloqueo de 15 minutos; pedir otro código no borra los intentos ni el bloqueo. Un código expirado no abre sesión.
- `GET /auth/yo`: correo del usuario autenticado y rol `docente` o `administrador`, según la lista explícita de configuración; no es un rol que pueda elegir el cliente.
- `POST /auth/salir`: elimina la sesión en PostgreSQL y la cookie en el cliente.

Las escrituras exigen `Origin` exactamente igual a `API_ORIGEN`, incluso antes de abrir sesión. Las cookies siempre son `Secure`, `HttpOnly`, `SameSite=Lax`, sin atributo Domain. Para probar el flujo en navegador se necesita servir API y frontend por HTTPS; habilitar HTTP para el origen en desarrollo no desactiva Secure. TestClient usa una URL HTTPS y no necesita certificados.

El servidor invalida sesiones tras 8 horas sin actividad y siempre a los 7 días de creación. No basta una cookie inventada. La BD solo almacena HMAC de códigos y SHA-256 de tokens de sesión; el secreto de HMAC permanece en configuración.

El reto se confirma antes de enviar correo: no hay locks SQL ni conexiones retenidas mientras SMTP responde. Si SMTP acepta un mensaje pero se pierde la confirmación, el código sigue siendo utilizable y se conserva el intervalo de reenvío. Un rechazo del buzón no cambia la respuesta pública. Otros fallos de infraestructura dan 503 sin información interna. Las esperas de lock de emisión y verificación se limitan a 2 segundos.

## Verificación

```powershell
../.venv/Scripts/python.exe -m pytest tests/test_auth.py tests/test_correo_auth.py tests/test_api.py -q
../.venv/Scripts/python.exe -m pytest -q
```

Incluye vencimiento, bloqueo, consumo único, revocación, TLS y no enumeración de buzones. Las pruebas concurrentes retienen una fila y comprueban en `pg_stat_activity` que los competidores esperan un lock antes de liberarla. No activan el humo GPU salvo que se configure `LLM_REAL=1`.

## Asignaturas y sílabos (A3)

Aplicar también la migración `005_asignatura_acceso.sql` con el mismo comando del inicio. El UUID identifica la asignatura, no su código PF: dos docentes pueden subir un mismo PF y conservan asignaturas independientes.

- `POST /silabos`: cuerpo **binario PDF** con `Content-Type: application/pdf`, cookie de sesión y `Origin`. No usa multipart ni acepta un dueño elegido por el cliente. Devuelve 201 con `id`, `agente`, `menu` por semanas y `clases_cambiadas`.
- `GET /asignaturas`: lista las propias y compartidas; incluye el rol efectivo, sin el cuerpo del sílabo.
- `GET /asignaturas/{UUID}/menu`: menú y versión, solo para dueño/editor/lector. Una asignatura ajena devuelve 403; una inexistente, 404.
- `POST /asignaturas/{UUID}/compartir`: JSON `{"correo":"colega@uti.edu.ec","rol":"lector"}` o `editor`. Solo el dueño puede crear o cambiar este acceso. El destinatario no necesita haber ingresado todavía; al verificar su correo verá la asignatura.
- `DELETE /asignaturas/{UUID}/compartir/{correo}`: retira acceso, solo el dueño. Codificar el correo al construir la URL.

El frontend puede enviar un `File` directamente como `body` de `fetch`, con `credentials: 'include'` y Content-Type PDF. El navegador añade Origin. Los clientes de pruebas deben enviarlo explícitamente.

El tamaño máximo predeterminado es 10 MB, contando bytes recibidos aunque no haya Content-Length o sea incorrecto. Se permiten dos cargas/lecturas simultáneas por proceso API; si están ocupadas, 503. Recepción limitada a 30 s (408 al vencer), lectura a 20 s en un subproceso con 512 MB de memoria. El subproceso usa JobObject en Windows y RLIMIT_AS en POSIX; son límites de recursos, no una cuenta de sistema separada. La comprobación de Windows se ejecuta en las pruebas locales; POSIX necesita validación en el despliegue Linux.

El PDF y la salida JSON son temporales y se eliminan en éxito, error, timeout o desconexión. No se guarda el original en PostgreSQL ni se envía a IA. El texto de errores del lector y las salidas del hijo no se imprimen ni se devuelven al cliente. Un archivo no PDF da 415, un PDF vacío/ilegible da 422 y el exceso de tamaño da 413.

Repetir la subida para el mismo dueño y PF reemplaza la versión conservando UUID y accesos compartidos. La respuesta identifica las clases cuyo contexto cambió; cambiar solo el número de versión no marca clases. Las primeras subidas concurrentes se serializan por dueño y código para comparar con la versión realmente anterior. Los trabajos existentes conservan su instantánea del sílabo y los recursos previos mantienen su versión; A4 conectará su consulta HTTP.

Las operaciones retienen un bloqueo sobre la asignatura y **después** consultan el permiso en una nueva sentencia, para no usar un acceso que se retiró durante la espera. La comprobación `editar=True` permite dueño/editor y rechaza lector; A4 la utilizará al generar y editar recursos. Las pruebas fuerzan tanto retirada como degradación mientras otra conexión espera.

```powershell
../.venv/Scripts/python.exe -m pytest tests/test_asignaturas_api.py tests/test_asignaturas_concurrencia.py tests/test_pdf_recepcion.py tests/test_lector_aislado.py -q
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

El cuerpo JSON tiene máximo 1 MiB y recepción de 30 s, antes de su decodificación. Las preguntas editadas tienen 25–1000 caracteres para acotar la comparación de duplicados; la validación no compara textos gigantes. La subida binaria PDF conserva su límite de 10 MB. El historial operativo tiene `uso_mejora=false`: no alimenta automáticamente reglas ni entrenamiento.

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
| `LIMITE_CODIGO_IP_HORA` | 120 | solicitudes de código por IP/hora |
| `LIMITE_CODIGO_CORREO_HORA` | 6 | solicitudes de código por correo/hora |
| `LIMITE_VERIFICAR_IP_MINUTO` | 60 | verificaciones por IP/minuto |
| `LIMITE_VERIFICAR_CORREO_MINUTO` | 20 | verificaciones por correo/minuto |
| `LIMITE_GENERAR_CORREO_HORA` | 30 | peticiones de generación por correo/hora, antes de encolar |
| `LIMITE_PDF_CORREO_HORA` | 10 | subidas por correo/hora, antes de leer el PDF |
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

No se ejecuta automáticamente al iniciar. TI debe programarlo y supervisarlo en P7; sin ejecutarlo no se garantiza el borrado físico al vencer la retención. La caducidad de códigos y sesiones sigue aplicándose al acceso aunque todavía no se hayan purgado sus filas.

`GET /privacidad`, con sesión, devuelve únicamente una vista del [borrador técnico](privacidad-borrador.md), con `estado=borrador`. La institución debe completar responsable, base aplicable, canales y conservación del material académico antes de aprobarlo. P6 deberá presentar el texto institucional aprobado antes del ingreso; esta ruta no representa aceptación ni amplía las rutas API públicas.

```powershell
../.venv/Scripts/python.exe -m pytest tests/test_control_api.py tests/test_control_identidad.py tests/test_limites.py tests/test_mantenimiento_control.py -q
```

P4 queda implementado; siguen pendientes SMTP real, administradores institucionales, aprobación del aviso, y despliegue P7 con HTTPS, proxy y mantenimiento. Las migraciones de desarrollo se prueban en esquemas temporales: aplicar explícitamente a la BD de aplicación al preparar el entorno.
