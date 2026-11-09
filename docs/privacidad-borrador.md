# Borrador técnico para revisión institucional

Versión técnica: 2026-10-27. Este texto describe la implementación; requiere revisión institucional y del responsable de protección de datos antes de presentarlo como aviso definitivo. No atribuye una base jurídica aprobada ni sustituye los canales oficiales de la universidad.

## Para qué funciona la herramienta

Permite a docentes ingresar con su correo institucional, leer su sílabo, compartir asignaturas y preparar materiales de aprendizaje. El docente revisa los recursos antes de utilizarlos. No está diseñada para recibir trabajos ni datos de estudiantes.

## Datos utilizados

- Correo institucional: enviar códigos, identificar sesiones y aplicar permisos sobre asignaturas. Los códigos se guardan como HMAC; los tokens de sesión se guardan como hash, no en claro.
- Sílabo: el PDF se usa temporalmente para extraer información académica. El lector excluye las secciones de datos del docente y firmas. El original y la salida temporal del proceso se eliminan al terminar la lectura, incluso cuando falla.
- Información académica estructurada, instrucciones y recursos: permiten generar y consultar materiales. Evitar nombres, contactos o datos de estudiantes en indicaciones y textos editados.
- Ediciones docentes: se registra quién modificó un recurso, cuándo y su contenido antes y después, para trazabilidad operativa. Ese historial no se usa automáticamente para reglas, mejora de modelos ni entrenamiento; `uso_mejora` permanece desactivado.
- Chat de ajustes: conserva pedidos, respuestas, estado y contexto académico para seguir el trabajo y evitar duplicados. El historial se consulta exclusivamente por asignatura y usuario solicitante con permiso de edición vigente; no se comparte con otros docentes de la asignatura. El correo de sesión no se incluye en prompts y se filtran correos escritos en las instrucciones antes de enviarlas al modelo. No introducir datos personales en mensajes. `uso_mejora` permanece desactivado; el plazo de conservación sigue pendiente de definición institucional.
- Seguridad: se cuentan solicitudes por IP y correo mediante claves HMAC. El registro de acceso guarda operación, estado y duración con identificadores seudonimizados. No guarda el cuerpo, la URL completa, parámetros, cookies, códigos, prompts, PDF ni IP/correo en claro.

Los hashes HMAC son seudónimos, no una promesa de anonimato. Otros componentes de infraestructura, como correo y proxy, necesitan su propia configuración y revisión institucional.

## Procesamiento y acceso

El material académico necesario se envía al servidor Qwen local configurado por la institución; no se remite el PDF original al modelo. La aplicación utiliza el servidor configurado, no un servicio externo de IA por defecto. El envío de códigos utiliza el transporte de correo que configure TI.

Cada docente accede a sus asignaturas y a las compartidas con él. Los lectores consultan; dueños y editores generan y modifican materiales. Solo el dueño comparte o retira acceso. Los administradores configurados consultan consumo agregado, sin obtener por ese rol el contenido de asignaturas ajenas.

## Caducidad y conservación técnica propuesta

- Código: válido durante 10 minutos, de un solo uso; cinco errores bloquean temporalmente nuevos intentos.
- Sesión: invalida a las 8 horas de inactividad y siempre a los 7 días de creación.
- PDF recibido: temporal, eliminado al finalizar su procesamiento; no se archiva como documento original.
- Bitácora de accesos: propuesta técnica predeterminada de 30 días, configurable y sujeta a revisión institucional. La eliminación física requiere ejecutar el mantenimiento configurado; caducar un acceso no equivale a borrar inmediatamente todas sus filas.
- Cuotas vencidas y sesiones/retos caducados: el mantenimiento elimina los registros vencidos según las reglas técnicas documentadas.
- Asignaturas, recursos, accesos compartidos e historial: se conservan para operar la herramienta. Su plazo institucional, procedimientos de retiro y tratamiento de copias de respaldo requieren definición antes del despliegue.

## Revisión necesaria antes del uso institucional

La institución debe completar e informar el responsable del tratamiento, finalidad y base jurídica aplicable, canales oficiales para consultas y ejercicio de derechos, plazos de conservación y respaldos, y condiciones del servicio de correo y alojamiento. Estas decisiones no se infieren de la configuración técnica.

El frontend de P6 deberá presentar el aviso institucional aprobado antes de solicitar el ingreso. La ruta actual `/privacidad` es únicamente una vista autenticada del borrador para revisión; no representa aceptación ni aprobación del texto.
