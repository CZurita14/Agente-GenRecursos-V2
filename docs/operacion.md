# Operación del despliegue P7

La herramienta `infra/operar.py` utiliza exclusivamente la biblioteca estándar de Python 3.12+ y Docker Compose v2. Funciona desde Windows y Linux y desde cualquier directorio de trabajo. No instala ni inicia servicios. Los servicios del despliegue son `db`, `migrar` (una ejecución), `api`, `worker`, `web` y `proxy`; el servidor de IA permanece externo.

## Interfaz y aislamiento

Desde la raíz del repositorio, usando `python` o el intérprete del entorno virtual:

```text
python infra/operar.py --entorno /ruta/operacion.env --proyecto genrecursos-app validar
python infra/operar.py --entorno /ruta/operacion.env --proyecto genrecursos-app respaldo --salida /respaldo/archivo.dump
python infra/operar.py --entorno /ruta/operacion.env --proyecto genrecursos-app restaurar --archivo /respaldo/archivo.dump --base verificacion_20261028
```

En Windows sustituir las rutas por rutas locales, entre comillas si contienen espacios. `--entorno FILE` es obligatorio; `--proyecto NAME` tiene por defecto `genrecursos-app`. Las opciones globales preceden al subcomando. No hay flags de aprobación humana. Código de salida: 0 éxito, 1 error, 130 interrupción. `--help` describe los argumentos.

La CLI rechaza los nombres de proyecto `genrecursos`, `rootdev` y `genrecursos-db`, así como nombres incompatibles con Compose. Las pruebas reales deben usar otro proyecto explícito, por ejemplo `genrecursos-p7-prueba`, con volumen, puertos y datos sintéticos propios. No usar el Compose raíz, sus volúmenes ni el contenedor `genrecursos-db`.

Todos los comandos de base de datos usan este prefijo, con argumentos separados y sin shell en el host:

```text
docker compose --env-file <archivo-absoluto> --project-name <proyecto> -f <repo>/infra/compose.yaml exec -T db ...
```

Las contraseñas no se incluyen como argumentos. El shell del contenedor ejecuta programas literales fijos que leen `POSTGRES_DB`, `POSTGRES_USER` y `POSTGRES_PASSWORD` del contenedor; `PGPASSWORD` se establece internamente. Docker/PostgreSQL no imprimen stdout ni stderr en la terminal de la CLI; solo se muestran mensajes estáticos de operación. Un fallo exige diagnóstico restringido por el operador, sin copiar credenciales ni salidas completas a incidencias.

## Archivo de entorno y validación

Partir de `infra/.env.example`, guardar la copia fuera del repositorio y restringir su acceso. La CLI admite `KEY=value`, comentarios, `export KEY=value` y valores entre comillas simples o dobles en una sola línea. No ejecuta el archivo ni admite expansión de variables. Usar valores literales entre comillas simples para secretos que contengan `$`. No usar claves duplicadas ni valores multilínea. Las variables leídas prevalecen sobre variables homónimas heredadas por el proceso de Docker. `TLS_DIR` relativo se resuelve respecto del archivo de entorno; para los comandos manuales de Compose usar siempre una ruta absoluta, evitando diferencias de resolución.

`validar` no invoca Docker ni muestra valores. Comprueba:

- `ENTORNO`: `produccion` o `desarrollo`. Producción requiere `API_ORIGEN` HTTPS exacto, sin ruta, credenciales, query ni fragmento; desarrollo admite HTTP para integración local.
- `AUTH_SECRETO`: al menos 32 caracteres y sin marcadores de sustitución conocidos. Generarlo aleatoriamente y conservarlo en el gestor de secretos institucional.
- `POSTGRES_PASSWORD`: al menos 32 caracteres, sin marcadores y solo `[A-Za-z0-9_-]`. Generar con `secrets.token_urlsafe(32)` en una sesión privada. `POSTGRES_USER` y `POSTGRES_DB`: entre 1 y 63 caracteres, primero alfanumérico o `_`, resto alfanumérico, `_` o `-`. Compose construye `DATABASE_URL` directamente con estas variables: no admite caracteres que necesiten escape URI. No pegar una contraseña arbitraria con `@`, `:`, `/`, `%`, espacios o comillas.
- `SGA_PROVEEDOR`: en producción debe ser `real` (el simulado solo sirve en desarrollo y la API lo rechaza con `ENTORNO=produccion`). El adaptador real depende de TI (B-SGA1, [para-TI](sga/para-TI.md)); `SGA_TIMEOUT_S` (15 s por omisión) acota cada llamada al SGA. `validar` no comprueba el SGA: se verifica con un ingreso real durante la entrega.
- `ADMINISTRADORES`: lista JSON de direcciones de `uti.edu.ec` o `indoamerica.edu.ec`, no vacía en producción. En desarrollo puede estar vacía u omitirse. Se valida la sintaxis, no la autorización institucional de las personas.
- `RED_PROXY`: subred IPv4 canónica distinta de `/0`; `IP_PROXY`: dirección IPv4 exacta dentro de ella, distinta de red y broadcast. `RANGO_DINAMICO`: parte de `RED_PROXY` de la que Docker asigna direcciones a `api` y `web`; debe excluir `IP_PROXY` (por defecto la mitad alta del /28). Sin él, el servicio que se conecta primero puede tomar la IP del proxy y este no arranca. No ampliar proxies confiables a toda la institución. Revisar conflictos de red antes de arrancar.
- `LIMITE_*` y `AUDITORIA_RETENCION_DIAS` (opcionales): enteros entre 1 y 100000 (retención: 1 a 365), los mismos rangos que la API. Si faltan, se usan los valores por defecto de `app/config.py`. Con NAT institucional subir `LIMITE_IP_MINUTO`.
- `DOMINIO`: hostname sin esquema, puerto ni ruta. `TLS_DIR`: directorio con `fullchain.pem` y `privkey.pem`.

La validación local no certifica fortaleza criptográfica, vigencia de certificados, conectividad con la IA ni con el SGA, DNS ni el ingreso de un docente real. Revisarlos durante la entrega a TI.

## HTTPS y publicación

TI provee DNS, cadena de certificados y clave privada para `DOMINIO`. `API_ORIGEN` debe coincidir con el origen que verá el navegador, incluyendo puerto si no es 443. `PUERTO_HTTPS` alimenta el puerto publicado y la redirección HTTPS del proxy; coordinarlo con `PUERTO_HTTP`. Solo el proxy está en la red `publica` (no interna): Docker no publica puertos de contenedores que solo están en redes internas. `IP_PUBLICACION` queda en `127.0.0.1` por defecto: el operador debe establecer explícitamente `0.0.0.0` o la interfaz autorizada al publicar en el servidor, con el cortafuegos correspondiente.

El proxy ejecuta como UID 101 / GID 101. El montaje TLS de solo lectura debe permitirle recorrer el directorio y leer ambos archivos. En Linux una opción es directorio `root:101` con modo `0750` y certificados/clave `root:101` con modo `0640`. Un directorio propiedad de UID 101 con modo `0740` también permite acceso al propietario; `root:101` con `0740` no permite recorrerlo al grupo. Ajustar ACL en Windows/Docker Desktop y comprobar lectura desde el contenedor. No hacer la clave legible para todos.

La CLI solo comprueba presencia de los archivos. El operador verifica permisos efectivos, cadena, hostname, vigencia y renovación, y prueba HTTPS con verificación de certificado. Para integración aislada puede usar un certificado autofirmado desechable; no representa un certificado institucional. Al renovar, sustituir el par de forma coordinada y recrear/recargar el proxy para volver a abrir los archivos montados. Confirmar HTTPS, redirección y salud después.

## Instalación y actualización coordinada

Para cada comando manual usar exactamente el mismo archivo, proyecto y Compose de despliegue. El siguiente ejemplo usa rutas Linux; adaptarlas en Windows. No ejecutar `docker compose config` sin restricción: su salida puede contener secretos.

```text
python infra/operar.py --entorno /srv/genrecursos/operacion.env --proyecto genrecursos-app validar
docker compose --env-file /srv/genrecursos/operacion.env --project-name genrecursos-app -f /repo/infra/compose.yaml build
docker compose --env-file /srv/genrecursos/operacion.env --project-name genrecursos-app -f /repo/infra/compose.yaml up -d --wait db
docker compose --env-file /srv/genrecursos/operacion.env --project-name genrecursos-app -f /repo/infra/compose.yaml run --rm migrar
docker compose --env-file /srv/genrecursos/operacion.env --project-name genrecursos-app -f /repo/infra/compose.yaml up -d --wait api worker web proxy
```

Para actualizar, acordar ventana de mantenimiento y bloquear nuevas escrituras en el borde. Construir las imágenes antes de la ventana cuando sea posible. Detener `proxy`, `api` y `worker`, dejando tiempo al worker para terminar su trabajo legítimo; el Compose concede hasta 600 segundos. Comprobar que no quedan consumidores antiguos. Crear y verificar un respaldo antes de ejecutar `migrar`. Ejecutar el migrador una vez, sin workers activos; si falla, mantener el mantenimiento y diagnosticar. Arrancar API y worker con la misma imagen y luego web/proxy; las dependencias de Compose vuelven a exigir un migrador exitoso. La exclusión mutua de migraciones protege frente a ejecuciones concurrentes, pero no sustituye detener código antiguo.

Comprobar preparación interna de API (`/salud/listo`), latido de worker, disponibilidad web/HTTPS y una operación sintética autorizada. `/salud` diagnostica IA; una caída de Qwen debe dejar utilizable la consulta y los trabajos en espera. No publicar rutas internas de salud. Confirmar que API, web, worker y BD no publican puertos al host. Aumentar réplicas de workers multiplica solicitudes al modelo: la concurrencia configurada por proceso no es un límite global.

Una imagen anterior no garantiza rollback tras cambiar el esquema. Si hay incompatibilidad, mantener detenidas las escrituras y preparar recuperación desde un respaldo probado en una base nueva, con procedimiento institucional de cambio de destino. Esta CLI no cambia el destino de producción ni elimina bases.

## Razonador entrenado (opcional)

Apagado por omisión: `RAZONADOR_RUTA` vacía en el archivo de entorno. El Compose solo se la entrega al servicio `worker`, junto con el volumen `modelos` en `/modelos` de solo lectura; la API y los demás servicios no la reciben. Guía completa, criterios y etiquetado en [ciencia-datos.md](ciencia-datos.md).

El nombre del volumen `genrecursos-app_modelos` del comando siguiente supone el nombre de proyecto por omisión (`genrecursos-app`); con otro proyecto es `<proyecto>_modelos`. Para instalar un modelo aprobado (solo con la decisión del usuario), copiar al volumen la carpeta elegida por el informe (`modelo_elegido`, que puede ser la del base; `v1` es solo un ejemplo), con todo su contenido, con un contenedor auxiliar, porque dentro del `worker` el volumen es de solo lectura (usar una imagen mínima ya aprobada por TI en lugar de `alpine` si corresponde):

```text
docker run --rm -v genrecursos-app_modelos:/modelos -v /ruta/del/modelo/v1:/origen:ro alpine cp -r /origen /modelos/v1
```

Después escribir `RAZONADOR_RUTA=/modelos/v1` en el archivo de entorno, ejecutar `validar` y recrear el `worker` (`up -d worker`). `validar` no comprueba el modelo: revisa el archivo de entorno, sin abrir el volumen. El modelo se comprueba con el arranque del `worker`: al cargar registra `razonador cargado: version=…` y hace una inferencia de prueba. Con `ENTORNO=produccion` el `worker` no arranca si el modelo falta, está dañado, es de humo, no está aprobado o sus pesos no coinciden con los aprobados; el motivo se lee en su bitácora (`docker compose … logs worker`) y no incluye textos. Para apagarlo, dejar la variable vacía y recrear el `worker`. Un trabajo en curso que se reanude conserva el plan que ya había decidido.

Reversión: antes de volver a una imagen sin `PlanRazonado`, drenar los trabajos que empezaron con razonador, porque esa imagen no sabe leer su plan guardado.

## Respaldo e integridad

`respaldo --salida PATH` requiere la BD activa y genera `pg_dump --format=custom`. Transmite stdout a un temporal en el directorio de salida, sincroniza el archivo y calcula SHA-256 por bloques. Publica `<PATH>.sha256` y después `PATH` mediante enlaces duros exclusivos; el dump aparece completo y no se sobrescribe ningún destino, incluso ante una creación concurrente. El directorio debe existir y el sistema de archivos admitir enlaces duros (por ejemplo NTFS o ext4); no hay fallback que sobrescriba. Un fallo ordinario limpia sus temporales y publicaciones parciales. Una interrupción abrupta del sistema puede dejar un manifiesto sin dump o temporales: revisar antes de reintentar con un nombre nuevo.

Para `/respaldo/archivo.dump`, el manifiesto es `/respaldo/archivo.dump.sha256`: contiene únicamente el digest hexadecimal SHA-256 de 64 caracteres y un salto de línea. Puede verificarse con `hashlib.sha256` o herramientas externas comparando ese digest; no tiene el formato con nombre de archivo que espera `sha256sum -c`. Conservar siempre ambos archivos. Un hash detecta corrupción; no autentica el respaldo frente a una alteración de ambos archivos.

Dump y manifiesto usan modo `0600` en POSIX. En Windows el operador debe restringir la ACL del directorio y de los archivos: `chmod` no sustituye las ACL. El respaldo contiene datos sensibles y no se cifra en esta herramienta. **Se requiere cifrado mediante el mecanismo institucional externo**, control de acceso, copia externa y política de retención/rotación aprobada. No guardar dumps, claves o archivos de entorno en Git. El volcado cubre la base de la aplicación, no roles globales, certificados, configuraciones ni el servidor de IA: conservar esos elementos mediante su propia política de recuperación.

## Prueba de restauración: siempre en base nueva

`restaurar --archivo PATH --base NUEVA` primero verifica el manifiesto del mismo nombre. Solo admite nombres `[a-z_][a-z0-9_]{0,62}`, excluyendo prefijo `pg_`, la base de `POSTGRES_DB`, `postgres`, `template0` y `template1`. Consulta el catálogo y rechaza cualquier destino existente, luego crea la base con propietario `POSTGRES_USER`. PostgreSQL también impide la creación si otro proceso usa el nombre entre comprobación y creación. Ejecuta `pg_restore --exit-on-error`, sin `--clean`, transmitiendo el mismo descriptor ya verificado por stdin. No restaura sobre una base operativa.

Ante fallo de restauración la base nueva queda conservada, posiblemente parcial, para diagnóstico. No se borra automáticamente ni debe reutilizarse como destino de otro intento. Una interrupción durante creación puede dejar una base creada: inspeccionar el proyecto identificado antes de decidir su eliminación manual. La herramienta no conecta API ni worker a la base restaurada.

Para la aceptación local, el proceso padre ejecuta Docker real exclusivamente en un proyecto aislado y con datos sintéticos: instalar desde volumen vacío, migrar dos veces, sembrar datos sintéticos, respaldar, restaurar a un nombre nuevo y comparar tablas, historial de migraciones y datos. Conservar evidencia del resultado. El éxito de `pg_restore` por sí solo no demuestra consistencia funcional. Eliminar después solo los artefactos del proyecto de prueba explícitamente identificado; no usar limpiezas globales. Esta prueba local no equivale a desplegar ni verificar el servidor institucional.

## Vigilancia y rotación

Supervisar disco/volumen y espacio para temporales y respaldos, salud de servicios, antigüedad de trabajos en espera, latido del worker y caducidad TLS. Mantener logs con acceso restringido, sin cuerpos, credenciales, cookies, claves del SGA ni direcciones de correo. Revisar diagnósticos saneados antes de compartirlos.

Rotar secretos y credenciales con ventana coordinada. Cambiar `AUTH_SECRETO` exige recrear API y worker y prever que no haya ingresos en curso; la caducidad/revocación de sesiones debe seguir el mecanismo de autenticación vigente, sin asumir que cambiar este secreto las revoca automáticamente. Cambiar `POSTGRES_PASSWORD` en el archivo no cambia el rol en un volumen ya inicializado: rotar primero de forma coordinada la credencial real y recrear consumidores. Si TI rota la cuenta de servicio del SGA (si el adaptador real la usa), coordinar el cambio con la ventana. Aplicar retención/purga de auditoría según política; no borrar historial académico sin una política aprobada.

Las pruebas unitarias `backend/tests/test_operar_infra.py` sustituyen subprocess y no requieren Docker ni BD. La integración real y la puesta en marcha institucional se verifican por separado.
