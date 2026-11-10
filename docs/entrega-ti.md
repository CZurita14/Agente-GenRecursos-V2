# Ficha de entrega a TI · Generador de Recursos de Estudio UTI (P7 D4)

**Estado:** borrador para revisión. No se ha enviado a TI ni desplegado en ningún servidor institucional. Los comandos son para que TI los revise y ejecute; nada se ejecuta solo.

**Qué es:** aplicación web interna para que los docentes ingresen con su usuario del SGA, reciban sus sílabos desde el SGA y generen herramientas de estudio con un modelo de IA local (Qwen3-8B-AWQ servido por vLLM). Los datos no salen de la red de la universidad.

**Documentos de apoyo:** [manual de operación](operacion.md) (detalle de cada comando, respaldo y restauración) · [plan y resultados de P7](superpowers/plans/2026-10-28-p7-despliegue.md) (prueba de instalación aislada 24/24).

---

## 1. Lo que necesitamos de TI

Cada punto bloquea la puesta en marcha. Entre paréntesis, la puerta abierta en `progress.md`.

| # | Necesidad | Detalle | Puerta |
|---|---|---|---|
| 1 | Servidor | Linux x86-64 con Docker Engine y Docker Compose v2. Recursos en §3. | B5 |
| 2 | Nombre y DNS | Un nombre interno (p. ej. `materiales.uti.edu.ec`) que resuelva al servidor. | B5 |
| 3 | Certificado TLS | Cadena completa (`fullchain.pem`) y clave privada (`privkey.pem`) para ese nombre, y quién los renueva. | B5 |
| 4 | Puertos | Abrir 443 (y 80 para redirigir) desde la red de docentes al servidor. Nada más se publica. | B5 |
| 5 | Servidor de IA | URL interna del vLLM con Qwen y cuántas peticiones simultáneas admite (§5). | B6 |
| 6 | SGA | Mecanismo de autenticación, consulta de materias del docente y del sílabo en JSON, cuenta de prueba, tiempos y límites. Los docentes entran con su usuario y clave del SGA. Detalle en [sga/para-TI.md](sga/para-TI.md). | B-SGA1 |
| 7 | Administradores | Correos `@uti.edu.ec` o `@indoamerica.edu.ec` de quienes ven el consumo. | B10 |
| 8 | Respaldo | Dónde se guardan los respaldos cifrados, con qué frecuencia y por cuánto tiempo. | B5 |
| 9 | Aviso de privacidad | Aprobado por la institución antes de abrir el acceso a docentes. | B9 |

---

## 2. Arquitectura

```
 Docentes ──HTTPS 443──▶ proxy (nginx) ──▶ web (interfaz estática)
                              │
                              └──/api/──▶ api (FastAPI) ──▶ db (PostgreSQL 18)
                                                          ▲
                                          worker ─────────┘──▶ servidor de IA (vLLM, fuera de Docker)
```

Seis servicios en un Compose propio (`infra/compose.yaml`), con nombre de proyecto propio:

| Servicio | Función | Red | Puertos al host |
|---|---|---|---|
| `proxy` | HTTPS, redirección desde HTTP, cabeceras de seguridad, límite de cuerpo 1 MiB | `borde` (interna) + `publica` | **Solo este**: 80 y 443 |
| `web` | Sirve la interfaz | `borde` | Ninguno |
| `api` | API de la aplicación | `datos`, `borde`, `salida` | Ninguno |
| `worker` | Genera los recursos con la IA (cola en la base) | `datos`, `salida` | Ninguno |
| `db` | PostgreSQL 18 con volumen persistente | `datos` (interna) | Ninguno |
| `migrar` | Aplica el esquema una vez y termina | `datos` | Ninguno |

- `api` y `worker` necesitan salida (`salida`) solo para llegar al servidor de IA y al SGA. La base no tiene salida.
- Todos corren sin privilegios, con raíz de solo lectura y sin capacidades del kernel. Las imágenes base están fijadas por digest.
- La API solo confía en la IP fija del proxy (`IP_PROXY`) para conocer la IP del cliente. Si TI pone otro balanceador delante, hay que revisarlo antes.

---

## 3. Recursos del servidor

| Elemento | Valor de referencia |
|---|---|
| Memoria límite por contenedor | `api` 1,5 GB · `worker` 1,5 GB · `web` 128 MB · `proxy` 128 MB · `db` sin límite fijo |
| Memoria recomendada del servidor | 4 GB o más (sin contar el servidor de IA) |
| Disco para imágenes | ≈ 1,4 GB (backend 591 MB, PostgreSQL 641 MB, nginx 2 × 93 MB) |
| Disco para datos y respaldos | A definir por TI según el número de docentes; la base crece con sílabos y recursos (texto). Prever espacio para varios respaldos. |
| Logs | Rotados por Docker: 10 MB × 3 archivos por servicio |
| GPU | No la necesita esta aplicación; solo el servidor de IA |

---

## 4. Variables de configuración

Se parte de [`infra/.env.example`](../infra/.env.example). El archivo real se guarda **fuera del repositorio**, con acceso restringido, y nunca se sube a Git. Antes de arrancar se valida con `infra/operar.py … validar`, que no imprime valores.

| Variable | Qué poner | Quién la da |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `genrecursos-app` (no usar `genrecursos`, `rootdev` ni `genrecursos-db`) | Fijo |
| `ENTORNO` | `produccion` | Fijo |
| `DOMINIO` | Nombre del punto 2, sin `https://` | TI |
| `API_ORIGEN` | `https://` + `DOMINIO` (con `:puerto` si no es 443) | TI |
| `IP_PUBLICACION` | IP de la interfaz por la que entran los docentes (`127.0.0.1` por defecto: no publica hacia fuera) | TI |
| `PUERTO_HTTP` / `PUERTO_HTTPS` | `80` / `443` | TI |
| `TLS_DIR` | Ruta absoluta a la carpeta con `fullchain.pem` y `privkey.pem` (legible por UID/GID 101) | TI |
| `RED_PROXY` / `IP_PROXY` / `RANGO_DINAMICO` | Subred interna de Docker para el borde (por defecto `172.31.250.0/28`, `.2`, `.8/29`). Cambiar solo si choca con una red existente; `RANGO_DINAMICO` no debe incluir `IP_PROXY`. | TI |
| `POSTGRES_DB` / `POSTGRES_USER` | Nombres simples (letras, números, `_`, `-`) | Operador |
| `POSTGRES_PASSWORD` | Aleatoria, ≥ 32 caracteres, solo `A-Z a-z 0-9 _ -` (p. ej. `secrets.token_urlsafe(32)`) | Operador |
| `AUTH_SECRETO` | Aleatorio, ≥ 32 caracteres. Guardarlo en el gestor de secretos. | Operador |
| `LLM_BASE_URL` | URL del vLLM terminada en `/v1` | TI |
| `LLM_MODEL` | `Qwen/Qwen3-8B-AWQ` | TI confirma |
| `LLM_API_KEY` | Si el vLLM la exige; si no, `no-se-necesita` | TI |
| `LLM_MAX_CONCURRENCIA` | Peticiones simultáneas del worker a la IA (empezar en `1`) | TI (§5) |
| `SGA_PROVEEDOR` | `real` (el simulado no se admite en producción) | Fijo |
| `SGA_TIMEOUT_S` | Segundos máximos por llamada al SGA (15 por omisión); ajustar con los tiempos que informe TI en el punto 6 | TI |
| `ADMINISTRADORES` | Lista JSON, p. ej. `["persona@uti.edu.ec"]`; no vacía en producción | Institución |
| `LIMITE_IP_MINUTO` | Peticiones por minuto por IP (600). **Subir si los docentes salen por una sola IP (NAT)**: todos comparten esta cuota. | TI |
| Otros `LIMITE_*` | Cuotas por usuario y por correo (ingresar, generar, editar). Valores por defecto en `infra/.env.example`; normalmente no se tocan. | Opcional |
| `AUDITORIA_RETENCION_DIAS` | Días que se guardan los registros de acceso (30, máximo 365) | Institución |
| `RAZONADOR_RUTA` | **Vacía** (apagado). Solo si el usuario decide encender el razonador entrenado: `/modelos/<versión>` de un modelo aprobado ([guía](ciencia-datos.md)). Solo la recibe el `worker`. | Institución, con TI |

Fijadas en el Compose (no se cambian por variable): JSON hasta 1 MiB y 30 s de recepción; timeouts de IA 120 s (generación) y 240 s (revisión).

---

## 5. Servidor de IA (vLLM)

La aplicación habla con el servidor de IA por su API compatible con OpenAI. Debe:

- Responder `GET <LLM_BASE_URL>/models` con el modelo `LLM_MODEL` y **`max_model_len` exactamente 8192**; si no, la aplicación se declara «degradada» y no genera con IA.
- Responder `POST /tokenize` (en la raíz, sin `/v1`) y `POST <LLM_BASE_URL>/chat/completions` aceptando `response_format` de tipo `json_schema` (salida guiada) y `chat_template_kwargs.enable_thinking` (plantilla de Qwen3). vLLM lo admite de serie.
- Ser alcanzable desde la red `salida` de Docker y **no** publicarse a través del proxy.

**Concurrencia:** cada worker abre hasta `LLM_MAX_CONCURRENCIA` peticiones a la vez. Varias réplicas del worker **multiplican** esa cifra; no es un límite global. TI debe indicar el total que admite el vLLM y ajustar `LLM_MAX_CONCURRENCIA` × réplicas por debajo.

**Si la IA cae:** los docentes siguen entrando, consultando, editando, validando y descargando; los pedidos con IA quedan en espera y se procesan cuando vuelve. Probado así en la instalación aislada.

---

**Razonador entrenado (opcional, apagado).** El Compose declara el volumen `modelos`, montado de solo lectura en `/modelos` únicamente en el `worker`. Mientras `RAZONADOR_RUTA` esté vacía no se usa y la generación es la de siempre; la imagen no lleva PyTorch (solo `numpy`, `scikit-learn`, `onnxruntime` y `tokenizers`). No hay nada que instalar hasta que exista un modelo aprobado; entonces TI copia su carpeta al volumen y ajusta la variable (pasos en [operación](operacion.md)). Un modelo ausente, de prueba o sin aprobar impide que el `worker` arranque, y la causa queda en su bitácora.

## 6. Instalación (para que TI la revise)

Rutas de ejemplo en Linux: el repositorio en `/opt/genrecursos`, la configuración en `/srv/genrecursos/operacion.env`. Usar siempre el mismo archivo, proyecto y Compose.

```bash
cd /opt/genrecursos
python3 infra/operar.py --entorno /srv/genrecursos/operacion.env --proyecto genrecursos-app validar
docker compose --env-file /srv/genrecursos/operacion.env --project-name genrecursos-app -f infra/compose.yaml build
docker compose --env-file /srv/genrecursos/operacion.env --project-name genrecursos-app -f infra/compose.yaml up -d --wait db
docker compose --env-file /srv/genrecursos/operacion.env --project-name genrecursos-app -f infra/compose.yaml run --rm migrar
docker compose --env-file /srv/genrecursos/operacion.env --project-name genrecursos-app -f infra/compose.yaml up -d --wait api worker web proxy
```

No ejecutar `docker compose config` sin filtrar: imprime los secretos.

### Comprobaciones después de instalar

| Comprobación | Resultado esperado |
|---|---|
| `docker compose … ps` | Los cinco servicios `Up (healthy)`; `migrar` `Exited (0)` |
| `http://DOMINIO/` | Redirige (308) a `https://DOMINIO/` |
| `https://DOMINIO/` con verificación de certificado | Abre la pantalla de ingreso, con el logo UTI |
| `https://DOMINIO/api/salud` | 404 (la salud interna no se publica) |
| Ingresar con una cuenta del SGA | Entra y aparecen sus materias (prueba real del SGA, B-SGA1) |
| Abrir una materia con sílabo importado y generar una hoja de ruta | Se genera, se valida y se descarga en HTML, PDF y Word |
| Generar una ficha de clase | Pasa a «Lista» en uno o dos minutos (prueba real de la IA, B6) |
| `docker port <proyecto>-proxy-1` | Solo 80 y 443; ningún otro servicio publica puertos |

---

## 7. Operación periódica

| Tarea | Frecuencia sugerida | Comando |
|---|---|---|
| Respaldo de la base | Diario (TI decide) | `python3 infra/operar.py --entorno … --proyecto genrecursos-app respaldo --salida /respaldos/AAAAMMDD.dump` |
| Prueba de restauración | Mensual, siempre en base nueva | `… restaurar --archivo /respaldos/AAAAMMDD.dump --base verificacion_AAAAMMDD` |
| Purga de datos de seguridad vencidos (sesiones, bloqueos de ingreso, cuotas y registros de acceso de más de 30 días) | Diaria | `docker compose --env-file … --project-name genrecursos-app -f infra/compose.yaml run --rm --no-deps api python -m app.control.mantenimiento` |
| Renovar certificado | Antes de su vencimiento | Reemplazar los dos archivos de `TLS_DIR` y recrear `proxy` |
| Vigilar | Continuo | Salud de servicios, disco, vencimiento TLS, trabajos en espera |

- El respaldo genera el archivo y su `.sha256`. **No va cifrado:** cifrarlo con el mecanismo institucional y guardar una copia fuera del servidor.
- La restauración nunca escribe sobre la base en uso ni sobre una base existente (lo rechaza).
- La purga no borra sílabos, recursos ni historial académico.
- Actualizaciones: ventana de mantenimiento → detener `proxy`, `api` y `worker` (el worker tiene hasta 600 s para terminar) → respaldo → `migrar` → arrancar. Detalle en el [manual](operacion.md).

---

## 8. Decisiones abiertas para TI

1. **Cuota por IP.** La API limita a 600 peticiones por minuto por IP. Si los docentes salen por una misma IP (NAT), comparten ese límite: TI debe indicarlo y subir `LIMITE_IP_MINUTO` antes de abrir el acceso. La cuota por usuario (120/min) sigue protegiendo frente a abusos individuales.
2. **Réplicas del worker** según la concurrencia que admita el vLLM (§5).
3. **Balanceador delante del proxy.** Si existe, revisar la cadena de IPs reenviadas antes de habilitarlo.
4. **Retención** de respaldos y de registros de acceso (`AUDITORIA_RETENCION_DIAS`, hoy 30 días).

## 9. Lo que no se ha probado

La instalación se probó completa en un equipo de desarrollo con un proyecto aislado, datos sintéticos, certificado autofirmado y la IA caída a propósito. **No** se ha probado: certificado institucional, SGA real, Qwen real dentro de este Compose ni el servidor de TI. La imagen con las dependencias del razonador se construyó una vez durante esta rama con `pip check` limpio, pero no se ha corrido con un modelo aprobado en un `worker` real: solo existe una prueba de humo con 2 sílabos, que no mide calidad. Esa verificación es la del §6 en el servidor de TI.
