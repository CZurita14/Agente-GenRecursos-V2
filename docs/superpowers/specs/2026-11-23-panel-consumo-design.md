# Panel de consumo de tokens

Fecha: 2026-11-23 · Rama: `V3-SilabosPesos` · Estado: aprobado por el usuario

## Intención

Controlar el gasto de tokens de la IA para evaluar el sistema y el costo de generar cada recurso. No es un control por docente ni por sesión de ingreso, y no impone cuotas.

## Objetivos

1. Un botón fijo en la esquina inferior derecha de todas las pantallas (sesión iniciada) que muestra los tokens del mes y abre un panel sobre el contenido, sin mover la página.
2. El panel muestra, para un periodo (hoy, 7 días, mes o rango de hasta 31 días):
   - totales: tokens de entrada y salida, llamadas, fallos, segundos de IA y costo estimado en USD;
   - por herramienta: recursos generados, tokens totales, promedio por recurso y parte de la revisión;
   - por asignatura: tokens por proyecto formativo (nombre y código);
   - chat de ajustes aparte;
   - últimos 20 trabajos: herramienta, ámbito, estado, tokens y duración. Nunca texto del contenido.
3. Acceso: los administradores (`ADMINISTRADORES`) entran directo. Cualquier otro docente con sesión iniciada entra con la **clave del panel**.

## Clave del panel

- La clave la define el usuario. Se guarda **solo como hash** en el `.env` (`CONSUMO_CLAVE_HASH`, formato `pbkdf2_sha256$<iteraciones>$<sal>$<hash>`), nunca en el código, el frontend ni el repositorio. `python -m app.operacion hash-clave` lee la clave por la entrada estándar e imprime el hash.
- `POST /consumo/desbloquear {"clave": "..."}` exige sesión iniciada, compara en tiempo constante y responde 204 con una cookie HttpOnly `consumo` firmada con `AUTH_SECRETO`, ligada a la sesión de ingreso y válida 30 minutos. Clave errónea: 403 «Clave incorrecta».
- Límite: 5 intentos por usuario cada 15 minutos (regla persistente `consumo_clave_usuario_15min`, como las demás cuotas); al superarlo, 429 con `Retry-After`.
- Sin `CONSUMO_CLAVE_HASH` configurado, el desbloqueo responde 503 y solo entran los administradores.
- La clave nunca se registra en logs ni en la bitácora de acceso.

## API

- `GET /consumo?desde&hasta` (fechas UTC, rango máximo 31 días, por omisión 7 días): requiere administrador o cookie `consumo` válida para la sesión actual; si no, 403 «Ingresa la clave del panel».
- `GET /admin/consumo` se mantiene igual (compatibilidad).
- Costo: `LLM_PRECIO_ENTRADA_USD_MTOK` y `LLM_PRECIO_SALIDA_USD_MTOK` (opcionales). Sin ellos, `costo_usd` es `null`. Es un máximo aproximado: no se registran los aciertos de caché de DeepSeek.
- Sin cambios en la base de datos: todo sale de `llamada_llm`, `trabajo`, `chat_pedido` y `asignatura`.

## No objetivos

- Cuotas o bloqueo por consumo.
- Consumo por docente o por sesión de ingreso.
- Exportar a CSV.

## Pruebas

- Totales y desgloses con llamadas sembradas; el chat va aparte; costo con y sin precios.
- Acceso: sin sesión 401; sin clave 403; clave errónea 403; clave correcta abre; la cookie no sirve con otra sesión ni vencida; el administrador entra directo; sin hash configurado, 503.
- Sexto intento fallido en 15 minutos: 429.
- La clave no aparece en logs.
- Frontend: el botón no tapa contenido ni cambia el layout; el formulario de clave y el panel se muestran en el navegador.
