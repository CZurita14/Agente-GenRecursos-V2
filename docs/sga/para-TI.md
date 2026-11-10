# Qué necesitamos de TI para conectar el SGA · Generador de Recursos UTI V2

**Estado:** bloqueo **B-SGA1** abierto. La V2 está terminada y probada contra un SGA simulado; falta el SGA real. Este documento lista lo que TI debe definir o entregar. Nada de esto se ha implementado del lado del SGA.

**Qué hace el sistema con el SGA:** el docente escribe su usuario y clave del SGA en nuestra pantalla de ingreso. El sistema los valida con el SGA, trae las materias del docente y el sílabo de cada una en JSON, los valida y genera recursos de estudio con una IA local. Los contratos están en [../api-silabo/](../api-silabo/README.md).

---

## 1. Qué necesitamos

| # | Necesidad | Detalle |
|---|---|---|
| a | **Autenticación** | Un mecanismo para validar usuario y clave del docente y recibir su identidad. Ver §2 |
| b | **Materias del docente** | Una consulta que, con la sesión del docente ya autenticado, devuelva sus materias. Ver §3 |
| c | **Sílabo en JSON** | Una consulta que devuelva el sílabo de una materia. Ver §4 |
| d | **Cuenta o entorno de prueba** | Al menos dos docentes de prueba con materias y sílabos variados (un sílabo completo, uno con campos vacíos, uno de una carrera distinta). Sin datos reales de personas |
| e | **Tiempos, límites y errores** | Ver §5 |
| f | **Identificación** | Cómo se identifica una materia y un sílabo. Ver §6 |

---

## 2. Autenticación

El sistema recibe usuario y clave del docente y **se los entrega al SGA** para validarlos. **No guardamos la clave** (ni en la base, ni en los registros): solo vive como parámetro durante la llamada. Por eso necesitamos saber **qué mecanismo ofrece el SGA**:

- ¿Un endpoint de API que reciba usuario y clave y devuelva un token o una sesión?
- ¿LDAP o Active Directory?
- ¿OAuth / OIDC (en ese caso, qué flujo permite que nuestra pantalla reciba la clave, o habría que redirigir al SGA)?
- ¿Otro?

Lo que el sistema necesita recibir de vuelta ([auth-sga.schema.json](../api-silabo/auth-sga.schema.json), [ejemplo](../api-silabo/ejemplo-auth.json)):

| Campo | Regla |
|---|---|
| `usuario` | Usuario del SGA, no vacío |
| `correo` | Correo institucional `@uti.edu.ec` o `@indoamerica.edu.ec`. Es la identidad del docente en nuestro sistema |
| `nombre` | Nombre del docente, no vacío |

La respuesta no debe incluir la clave ni tokens del SGA. Si el mecanismo entrega un token para las consultas siguientes, el sistema lo usa solo durante el ingreso y no lo guarda.

Para distinguir errores necesitamos que el SGA diferencie **credenciales rechazadas** (usuario o clave incorrectos) de **servicio no disponible**: las primeras cuentan para el bloqueo (5 fallos seguidos, 15 minutos); las segundas no.

**¿El usuario distingue mayúsculas?** El sistema entrega al SGA el usuario tal como se tecleó, solo sin espacios al inicio y al final; no lo pasa a minúsculas. El bloqueo por intentos y la cuota de ingresos, en cambio, no distinguen mayúsculas. Necesitamos saber si para el SGA `Docente.Uno` y `docente.uno` son el mismo usuario.

## 3. Materias del docente

Una consulta que devuelva las materias del docente autenticado según [materias-api.schema.json](../api-silabo/materias-api.schema.json) ([ejemplo](../api-silabo/ejemplo-materias.json)). Cada elemento:

| Campo | Qué es |
|---|---|
| `id_sga` | Identificador de la materia-paralelo en el SGA (único por docente) |
| `codigo_pf` | Código del proyecto formativo, `A99-AAAA-9-99999-9999` |
| `paralelo` | Número o nombre del paralelo |
| `nombre` | Nombre de la materia |
| `carrera` | Carrera |
| `estado` | Estado en el SGA (p. ej. `ACTIVA`) |

**Importante:** el acceso lo define solo el SGA. Si una materia deja de aparecer en esta lista, el docente pierde acceso a su asignatura en nuestro sistema (queda inactiva, no se borra). Por eso la lista debe contener todas las materias vigentes del docente, en el periodo que TI y la universidad decidan. Los códigos no llevan datos personales.

**Un fallo del SGA debe ser un error, nunca una lista vacía.** Una lista vacía significa «el docente no tiene materias» y le retira el acceso a todas sus asignaturas. Si el SGA no puede consultar las materias (caída, tiempo agotado, error interno), debe responder con un error, y el sistema conserva entonces todo como estaba.

## 4. Sílabo en JSON

Una consulta que devuelva el sílabo de una materia según [silabo-api.schema.json](../api-silabo/silabo-api.schema.json) ([ejemplo mínimo](../api-silabo/ejemplo-minimo.json); qué apartado se usa para qué, en el [README de contratos](../api-silabo/README.md)).

- **Sin la sección I** (perfil, correo, teléfono, ORCID del docente) **ni la VII** (firmas), y sin ningún dato personal. Si llegan, se descartan en cuanto entran (lista blanca) y no se guardan; aun así, preferimos que no se envíen.
- **Claves extra:** cualquier clave que el esquema no declara se descarta sin mirarla. No hace falta limpiarlas del lado del SGA, pero tampoco se aprovechan.
- **Completitud:** los apartados obligatorios deben venir. El sistema valida el esquema y 7 reglas de integridad (números de momento sin repetir, resultados de aprendizaje existentes, sesiones por momento, id de sesión `M<momento>-S<n>` sin repetir, fecha dentro del periodo, contenidos sin vacíos). Un sílabo que no cumple no se importa y el docente ve la ruta del campo que falla, nunca su valor.
- **Calidad de los datos:** en los dos sílabos reales analizados (PDF), la actividad práctica de un 23 % de las sesiones, la autónoma de un 12 % y los entregables de un 65 % venían vacíos. Si el SGA los tiene completos, deben llegar completos.
- **Versión:** `proyecto_formativo.version` debe cambiar cuando cambia el sílabo. Es lo que usamos para saber si hay que volver a importarlo.

## 5. Tiempos, límites y errores

Necesitamos saber:

| Tema | Qué necesitamos |
|---|---|
| Tiempo de respuesta | Tiempo típico y máximo de cada consulta. Hoy esperamos hasta `SGA_TIMEOUT_S` = 15 s por llamada (configurable) |
| Cuántas llamadas | Al ingresar se hace 1 autenticación, 1 consulta de materias y **1 consulta de sílabo por materia** (las materias de un docente, en serie). ¿Hay límite de llamadas por minuto o por IP? |
| Presupuesto del ingreso | El proxy corta la petición de ingreso a los 65 s. Por eso la sincronización tiene un presupuesto, `SGA_SINCRONIZACION_MAX_S` = 45 s por omisión (siempre menor que 65): al agotarse, no se piden más sílabos; las materias restantes quedan `no_disponible`, conservan su versión anterior y siguen accesibles. Se completan en el siguiente ingreso |
| Origen de las llamadas | IP del servidor del Generador, para que TI la autorice |
| Códigos de error | Cómo distingue el SGA: credenciales inválidas, usuario bloqueado o inactivo, sin materias, sílabo no existente o no publicado, servicio caído |
| Cuenta bloqueada por el SGA | Si el SGA bloquea tras N fallos, cuántos; nuestro sistema bloquea por su cuenta tras 5 |

## 6. Cómo se identifica una materia y un sílabo

- **Materia:** `id_sga` (único por docente) más `codigo_pf` y `paralelo`.
- **Sílabo:** por el código del proyecto formativo, `A99-AAAA-9-99999-9999` (una letra, dos dígitos, guion, cuatro letras, guion, un dígito, guion, cinco dígitos, guion, cuatro dígitos). Es el mismo `codigo_pf` de la materia y `proyecto_formativo.codigo` del sílabo; si no coinciden, el sílabo se rechaza.
- **Paralelos:** hay un sílabo por código PF, compartido entre sus paralelos. Si el SGA entrega sílabos distintos por paralelo, hay que decirlo: hoy no está soportado.
- **Cómo se pide el sílabo:** necesitamos saber qué dato usa el SGA para pedirlo (¿`id_sga`, `codigo_pf`, ambos?). El adaptador recibe la materia completa, así que cualquiera sirve.

---

## 7. Dónde se conecta (para el equipo técnico)

La interfaz es `ProveedorSGA` en `backend/app/sga/proveedor.py`:

```python
class ProveedorSGA(Protocol):
    def autenticar(self, usuario: str, clave: str) -> tuple[IdentidadSGA, object]: ...
    def listar_materias(self, permiso: object) -> list[MateriaSGA]: ...
    def obtener_silabo(self, permiso: object, materia: MateriaSGA) -> dict: ...
```

- `autenticar` devuelve la identidad y un **permiso opaco** (token o sesión) que solo vive durante la sincronización y nunca contiene la clave.
- Errores: `CredencialesInvalidas`, `SGANoDisponible` y `SilaboNoDisponible` (de `app.sga`). Los mensajes nunca llevan usuario, clave ni datos del sílabo.
- `obtener_silabo` devuelve el JSON **crudo**; el traductor y la validación los aplica el sistema.

El adaptador real se implementa en **`backend/app/sga/real.py`** (hoy `crear_proveedor_real` responde «adaptador real pendiente de TI») y se activa con `SGA_PROVEEDOR=real`. Referencia: `backend/app/sga/simulado.py`, que implementa la misma interfaz con fixtures de `backend/tests/fixtures/sga/`. No hace falta tocar nada más del sistema.

## 8. Cómo validarlo cuando haya acceso

1. Con una cuenta de prueba, exportar a una carpeta los sílabos crudos del SGA (un JSON por sílabo).
2. Preparar la carpeta de referencia con los mismos sílabos en JSON de otra fuente conocida (p. ej. exportados una vez de la V1).
3. Comparar:

```bash
cd backend && python -m app.sga.comparar <carpeta_sga> <carpeta_referencia>
```

Empareja por `proyecto_formativo.codigo`, aplica la lista blanca a ambos lados y escribe, por sílabo, el porcentaje de coincidencia y las **rutas** de los campos distintos (nunca valores). Termina con código 0 solo si todo coincide y no hay sílabos sueltos de un lado. Si una carpeta trae varios archivos con el mismo código (p. ej. uno por paralelo), se toma uno cuando son idénticos en los campos del contrato; si difieren, la herramienta se detiene con un error que nombra el código.

4. Ingresar con la cuenta de prueba, comprobar que aparecen sus materias y que cada sílabo se importa (`importada`) o muestra el motivo (`invalida`, con rutas de campo).
5. Generar un cuestionario de una clase.

Para el despliegue (servidor, DNS, TLS, servidor de IA) ver [../entrega-ti.md](../entrega-ti.md).
