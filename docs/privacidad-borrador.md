# Borrador técnico para revisión institucional

Versión técnica: 2026-11-10 (V2, ingreso con el SGA). Este texto describe la implementación; requiere revisión institucional y del responsable de protección de datos antes de presentarlo como aviso definitivo. No atribuye una base jurídica aprobada ni sustituye los canales oficiales de la universidad.

## Para qué funciona la herramienta

Permite a docentes ingresar con su usuario y clave del SGA, recibir del SGA el sílabo de las materias que tienen asignadas y preparar materiales de aprendizaje. El docente revisa los recursos antes de utilizarlos. No está diseñada para recibir trabajos ni datos de estudiantes.

## Datos utilizados

- Credenciales del SGA: el usuario y la clave solo se usan para autenticar contra el SGA en el momento del ingreso. La clave nunca se guarda: ni en la base de datos, ni en los registros, ni en la sesión.
- Correo institucional: lo entrega el SGA al autenticar. Identifica la sesión y define de quién son las asignaturas. Los tokens de sesión se guardan como hash, no en claro.
- Materias del SGA (`materia_sga`): por cada materia asignada se guarda su nombre, carrera, código del Proyecto Formativo, paralelo y estado en el SGA, junto con el resultado de importar su sílabo. Cuando el SGA deja de listar una materia, su fila se elimina y la asignatura queda inactiva.
- Sílabo: llega del SGA en formato estructurado. Antes de validarlo se descartan los datos personales (secciones I y VII: datos del docente y firmas); solo se guarda la información académica.
- Información académica estructurada, instrucciones y recursos: permiten generar y consultar materiales. Evitar nombres, contactos o datos de estudiantes en indicaciones y textos editados.
- Ediciones docentes: se registra quién modificó un recurso, cuándo y su contenido antes y después, para trazabilidad operativa. Ese historial no se usa automáticamente para reglas, mejora de modelos ni entrenamiento; `uso_mejora` permanece desactivado.
- Chat de ajustes: conserva pedidos, respuestas, estado y contexto académico para seguir el trabajo y evitar duplicados. El historial se consulta exclusivamente por asignatura y usuario solicitante con permiso de edición vigente. El correo de sesión no se incluye en prompts y se filtran correos escritos en las instrucciones antes de enviarlas al modelo. No introducir datos personales en mensajes. `uso_mejora` permanece desactivado; el plazo de conservación sigue pendiente de definición institucional.
- Registro de ingresos (`auth_registro`): fecha, evento (ingreso, fallido, bloqueado, SGA no disponible, dominio no permitido, salida) e IP. El correo se guarda solo cuando el SGA confirmó la identidad; en un fallo se guarda el seudónimo HMAC del usuario tecleado. Nunca la clave.
- Bloqueo por intentos: los fallos de clave se cuentan por usuario con un seudónimo HMAC del usuario tecleado, nunca con el texto (a veces se teclea la clave en ese campo).
- Seguridad: se cuentan solicitudes por IP y usuario o correo mediante claves HMAC. El registro de acceso guarda operación, estado y duración con identificadores seudonimizados. No guarda el cuerpo, la URL completa, parámetros, cookies, credenciales, prompts ni IP/correo en claro.

Los hashes HMAC son seudónimos, no una promesa de anonimato. Otros componentes de infraestructura, como el SGA y el proxy, necesitan su propia configuración y revisión institucional.

## Procesamiento y acceso

El material académico necesario se envía al servidor Qwen local configurado por la institución. La aplicación utiliza el servidor configurado, no un servicio externo de IA por defecto.

El acceso lo define el SGA: cada docente accede a las asignaturas de las materias que el SGA le lista; las demás quedan inactivas, sin borrarse, y vuelven si la materia regresa. Los administradores configurados consultan consumo agregado, sin obtener por ese rol el contenido de asignaturas ajenas.

## Caducidad y conservación técnica propuesta

- Bloqueo por intentos: cinco fallos seguidos bloquean al usuario 15 minutos.
- Sesión: invalida a las 8 horas de inactividad y siempre a los 7 días de creación.
- Registro de ingresos: 90 días; lo borra el mantenimiento configurado.
- Bitácora de accesos: propuesta técnica predeterminada de 30 días, configurable y sujeta a revisión institucional. La eliminación física requiere ejecutar el mantenimiento configurado; caducar un acceso no equivale a borrar inmediatamente todas sus filas.
- Cuotas vencidas, sesiones caducadas y contadores de intentos viejos: el mantenimiento elimina los registros vencidos según las reglas técnicas documentadas.
- Asignaturas, recursos, materias del SGA e historial: se conservan para operar la herramienta. Su plazo institucional, procedimientos de retiro y tratamiento de copias de respaldo requieren definición antes del despliegue.

## Revisión necesaria antes del uso institucional

La institución debe completar e informar el responsable del tratamiento, finalidad y base jurídica aplicable, canales oficiales para consultas y ejercicio de derechos, plazos de conservación y respaldos, y condiciones del SGA y del alojamiento. Estas decisiones no se infieren de la configuración técnica.

El frontend deberá presentar el aviso institucional aprobado antes de solicitar el ingreso. La ruta actual `/privacidad` es únicamente una vista autenticada del borrador para revisión; no representa aceptación ni aprobación del texto.
