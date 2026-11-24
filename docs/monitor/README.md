# Conexión con el Monitor de Agentes UTI

El Generador implementa la API **UTI v1** (contrato `monitor-api-v1.json`, versión 1.1.0) del Monitor de Agentes de la UTI, solo para observarlo: no tiene pesos ni entrenamiento controlables.

| Ruta | Respuesta |
|---|---|
| `GET /v1/capabilities` | `agentId` `generador-recursos-uti`, `configuration: false`, `training: false`, sin pesos |
| `GET /v1/health` | `ready`, `degraded` (más de la mitad de al menos 3 llamadas a la IA fallaron en 15 minutos) o `not_ready` (sin base de datos), con `cpuPercent`, `memoryMb` y `errorRate` cuando se conocen |
| `GET /v1/events` | Actividad paginada por cursor: inicio del servicio, recursos solicitados, generados, con observaciones o fallidos, chat de ajustes y sílabos importados, inválidos o no disponibles |

Código: `backend/app/api/monitor_uti.py`; pruebas: `backend/tests/test_monitor_uti.py`.

## Acceso

- Token Bearer propio del monitor. En el `.env` solo va su SHA-256 (`MONITOR_TOKEN_HASH`); sin él, `/v1` responde 503.
- Generar o rotar: desde `backend/`, `python -m app.operacion token-monitor <archivo>`. Escribe el token en el archivo (que no debe existir) e imprime el hash. Reiniciar la API después de cambiar el hash.
- El token solo abre `/v1/*`; la sesión de los docentes no sirve en `/v1` y el token no abre el resto de la API.

## Privacidad

Los eventos se arman con campos fijos (herramienta, ámbito, estado, duración, tokens y rutas de campos). Nunca llevan correos, nombres, texto del sílabo, contenido de recursos, conversaciones ni razonamiento del modelo.

## Kit para el responsable del monitor

`kit-generador-recursos/`: ficha `ficha-agente.json` (sin credenciales; completar el contacto técnico), contrato, ejemplos reales y `LEEME.txt`. El token se entrega aparte por un canal seguro.
