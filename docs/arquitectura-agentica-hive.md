# Arquitectura agéntica de Hive (johpaz/hive)

> **Fecha:** 2026-10-19
> **Repositorio:** https://github.com/johpaz/hive · rama `master`, commit
> `cf5003b` (2026-09-23).
> **Herramienta:** REA 6.7.0 (`rea-agents`), comando
> `analyze-javascript-application` sobre `packages/core`, más lectura directa
> de imports y comentarios de cabecera del código.
> **Relación con este proyecto:** Hive es la base de PumaNet (el fork
> institucional) y la referencia para la arquitectura multiagente del
> Generador de Recursos UTI (§8).

---

## 1. Cómo se obtuvo este mapa

| Dato de REA sobre `packages/core` | Valor |
|---|---|
| Archivos relevantes / analizados | 235 / 233, sin fallos de parseo |
| Nodos / relaciones del grafo de la aplicación | 2 638 / 3 934 |
| Símbolos exportados | 873 |
| Endpoints de red detectados | 47 |
| Duración del análisis | 53 s |

**Límite encontrado:** REA no resolvió los imports relativos sin extensión que
usa Bun (`./agent-loop` en lugar de `./agent-loop.ts`); los marca como "no
encontrados". El grafo de REA sí es fiable para **exportaciones, endpoints,
paquetes, workers y dependencias externas**. Las dependencias internas entre
módulos se completaron leyendo los imports del código fuente.

La carpeta `Bia/` (modelos 3D) se excluyó del clon: sus rutas superan el
límite de Windows y no contiene código.

---

## 2. Paquetes del monorepo

| Paquete | Archivos | Rol |
|---|---|---|
| `packages/core` (`@johpaz/hive-agents-core`) | 237 | Motor: agentes, gateway, herramientas, canales, almacenamiento |
| `packages/hive-ui` | 254 | Interfaz web (setup, proveedores, agentes, "oficina") |
| `packages/cli` | 29 | Comando `hive` (start, onboard, doctor…) |
| `packages/skills` | 26 | 11 skills empaquetadas: a2ui, agents, api, artifacts, cli, cron_manager, cron_reminder, filesystem, office, search_knowledge, web |
| `packages/mcp` (`@johpaz/hive-agents-mcp`) | 7 | Gestor de clientes MCP y sus transportes |
| `apps/hive-desktop` | 68 | Aplicación de escritorio (Tauri) |

---

## 3. Arquitectura en capas

```text
 Canales: webchat · WhatsApp (Baileys) · Telegram (grammy) · Slack (bolt) · Discord
     │                         ▲  narración de progreso (events/channel-narration)
     ▼                         │
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ GATEWAY  server · routes (26) · seguridad/pairing · TTS y voz realtime     │
 │   DurableLaneQueue: cola persistente por "carril", 1 job activo por carril,│
 │   máx. 4 globales, leases que sobreviven a caídas (jobQueue)               │
 └───────────────────────────────┬───────────────────────────────────────────┘
                                 ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ COORDINADOR  AgentService → AgentLoop.runAgent (máx. 10 iteraciones)        │
 │   context-compiler: arma el prompt y elige, por búsqueda en índice,         │
 │     herramientas · skills · reglas del playbook · agentes del catálogo      │
 │   llm-client → 16 proveedores (Anthropic, OpenAI, Gemini, DeepSeek, Ollama, │
 │     OpenRouter, NVIDIA, Groq, Qwen, Mistral…)                                │
 │   tool-runtime: herramientas en worker threads con timeout                  │
 │   Jev (opcional): plano de decisión — paralelo o secuencial, ruteo           │
 │   stuck-loop · compaction · circuit breaker · retry                          │
 └───────┬──────────────────────────────────────────────┬────────────────────┘
         │ task_delegate (sync | async)                  │ goal_run
         ▼                                               ▼
 ┌──────────────────────────────┐            ┌──────────────────────────────┐
 │ WORKERS (agentes especialistas)│◄─bus──►   │ GOAL RUNNER                   │
 │  runAgentIsolated: su propio   │  agent-bus│  presupuesto duro: iteraciones,│
 │  loop, herramientas acotadas   │           │  tokens y turnos de todo el run│
 └──────────────┬───────────────┘            └──────────────┬───────────────┘
                ▼                                            ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ VERIFICACIÓN  acceptance-checks (deterministas, sin LLM) → delegation-     │
 │   groups (fan-in) → turno de cierre del coordinador → task_revise          │
 │   proof-packet: evidencia comprimida de cada run verificado                │
 └───────────────────────────────────────────────────────────────────────────┘
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ APRENDIZAJE (ACE, en segundo plano)  tracer → reflector → curator →        │
 │   reglas del playbook (helpful/harmful), que el context-compiler reinyecta │
 └───────────────────────────────────────────────────────────────────────────┘
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ ALMACENAMIENTO  HiveDB (@johpaz/hive-db), ~40 colecciones; run-store con   │
 │   checkpoints y concurrencia optimista; secretos cifrados                  │
 └───────────────────────────────────────────────────────────────────────────┘
 Transversal: MCP (hot-reload, sincroniza sus tools al índice) · scheduler cron
 · heartbeat · plugins · canvas/A2UI · event-bus
```

---

## 4. Patrón multiagente

### 4.1 Roles

| Rol | Quién | Qué hace |
|---|---|---|
| **Coordinador** | Agente con `role: "coordinator"` (uno por usuario) | Conversa, decide si resuelve o delega, juzga la entrega en su turno de cierre. Su proveedor y modelo se copian a los agentes que no tienen uno propio |
| **Workers de catálogo** | 8 especialistas sembrados (§4.2) | Ejecutan tareas acotadas con herramientas limitadas y criterios de aceptación propios |
| **Workers creados** | `agent_create` (requiere consultar modelos disponibles; puede atarse a un servidor MCP) | Especialistas privados del usuario; se archivan con `agent_archive` |

### 4.2 Catálogo sembrado

| id | Especialidad | Criterio de aceptación |
|---|---|---|
| `web_researcher` | Investigación web con fuentes | Conclusiones con fuentes trazables |
| `browser_operator` | Navegación y formularios | Estado final comprobado visual o estructuralmente |
| `workspace_file_operator` | Archivos del workspace | Estado final verificado por lectura o listado |
| `software_engineer` | Implementar, depurar y probar | Pruebas pasan; cambios acotados |
| `office_document_agent` | PDF, Word, Excel, PowerPoint | El archivo existe, no está vacío y reabre sin error |
| `a2ui_builder` | Formularios y dashboards A2UI v0.9 | Superficie con componentes y bindings válidos |
| `schedule_automation_agent` | Jobs cron | Job persistido con estado, zona horaria y próxima ejecución |
| `api_operator` | APIs REST autorizadas | Status y contrato de respuesta esperados |

### 4.3 Herramientas de orquestación (`tools/agents`)

| Herramienta | Función |
|---|---|
| `task_delegate` | Delegar una tarea acotada a un worker. **Sync** bloquea la conversación; **async** la encola y avisa en el mismo chat al terminar |
| `task_revise` | Devolver la tarea al worker con retroalimentación; continúa en el mismo hilo y conserva su contexto |
| `task_list` | Estado real de las tareas (TaskDoc y JobDoc son la fuente de verdad) |
| `agent_find` / `agent_create` / `agent_archive` | Descubrir, crear y retirar workers |
| `bus_publish` / `bus_read` | Mensajes entre workers sin pasar por el coordinador |
| `memory_write` / `memory_search` / … | Memoria persistente de largo plazo |
| `get_available_models` | Modelos disponibles para crear agentes |

### 4.4 Ciclo de una delegación

```text
Coordinador ── task_delegate(worker, tarea, criterios) ──► DurableLaneQueue (jobQueue)
                                                             │
                                             runAgentIsolated(worker) con run-store
                                             (checkpoint tras cada ida y vuelta al LLM)
                                                             │
                              acceptance-checks: checkTool por criterio, inspección
                              de artefactos y "delivery gates" — 0 llamadas al LLM
                                                             │
                     delegation-groups: reúne los resultados de tareas paralelas
                                                             │
Coordinador (turno de cierre): juzga lo que los checks no cubren ("unchecked")
        ├── cumple → responde al usuario (+ proof-packet si es goal/proyecto)
        └── no cumple → task_revise(feedback) → el worker sigue en su hilo
```

Decisiones de diseño visibles en los comentarios del código:

- **El verificador dejó de ser un agente.** Antes un `acceptance_verifier`
  corría un loop completo hasta 3 veces; se reemplazó por checks
  deterministas, y el coordinador juzga solo lo que queda sin verificar.
- **Presupuestos duros** en el goal runner (iteraciones, tokens y turnos
  sumados en todo el run) para evitar bucles infinitos; además hay un detector
  de bucles atascados.
- **Durabilidad:** colas, runs y checkpoints persisten cada transición; un
  worker caído se recupera por lease vencido.
- **Concurrencia acotada:** 1 job por carril y 4 en total; Jev decide si un
  lote de herramientas va en paralelo (solo lecturas independientes o tareas
  delegadas separadas).

### 4.5 Jev, el plano de decisión (opcional)

- Modelo `typesafe/jev-1.13` vía `https://openrouter.ai/api/alpha/decisions`;
  solo se activa si hay proveedor OpenRouter habilitado.
- Responde preguntas cerradas (elección con probabilidades, o sí/no) para
  rutear especialistas, planear la iteración y decidir paralelismo.
- 3 s de timeout y 60 s de enfriamiento tras fallos: si no responde, el loop
  sigue con su comportamiento por defecto.

### 4.6 Aprendizaje continuo (ACE)

1. **Tracer** registra trazas y uso de cada llamada.
2. **Reflector** (segundo plano, cada N trazas) produce *reflections*.
3. **Curator** las convierte en reglas del **playbook** con contadores
   *helpful/harmful* y desactiva las que hacen más daño que bien; nunca
   reescribe el playbook completo.
4. El **context-compiler** selecciona reglas del playbook en cada turno.

---

## 5. Almacenamiento (HiveDB)

Colecciones más usadas (número de referencias en el código): `agents` (52),
`models` (31), `users` (28), `cronJobs` (27), `providers` (23), `skills`,
`mcpServers` y `channels` (17), `jobQueue` (16), `tools` (11), `tasks` (10),
`conversations`, `taskRuns`, `agentRuns`, `artifacts`, `playbook`, `memory`,
`delegationGroups`, `agentBusMessages`, `proofPackets`, `reflections`,
`traces`, `usageRecords`, `secrets`, entre otras (~40 en total).

---

## 6. Integraciones externas

| Tipo | Detectado por REA |
|---|---|
| LLM | SDK de Anthropic, OpenAI, Google GenAI, Ollama; endpoints de OpenRouter, Groq, DashScope; descubrimiento de modelos (`/models`, `/api/tags`) |
| Visión | Gemini, Anthropic Messages, OpenAI Chat Completions |
| Voz | ElevenLabs, Groq y OpenAI (STT/TTS), DashScope, TTS local (`localhost:${TTS_PORT}`) |
| Canales | `@whiskeysockets/baileys`, `grammy`, `@slack/bolt`, `discord.js` |
| Office | `docx`, `pptxgenjs`, `xlsx`, `mammoth`, `pdf-lib`, `pdfjs-dist`, `jszip` |
| Actualizaciones | GitHub releases de `johpaz/hive` y registro npm de `@johpaz/hive-agents` |

---

## 7. Puntos de atención

- **Imports relativos sin extensión:** impiden a REA (y a otras herramientas
  estáticas) resolver el grafo interno. Si se quiere usar REA en CI, conviene
  sumar un paso que resuelva los imports con la configuración de TypeScript.
- **Jev depende de un endpoint alfa de OpenRouter:** si cambia, el sistema
  sigue funcionando (hay fallback), pero se pierde el ruteo y el paralelismo
  asistido.
- **Concurrencia global fija en 4:** relevante si muchos docentes generan a la
  vez (§8).

---

## 8. Qué aporta a la arquitectura del Generador de Recursos UTI

| Necesidad del spec v1.1 | Equivalente en Hive | Cómo usarlo |
|---|---|---|
| Orquestador que enruta por facultad | Coordinador + `agent_find` / catálogo indexado | El orquestador elige el agente por la facultad del sílabo (regla determinista, sin LLM) |
| Un agente por facultad | Workers de catálogo con `role`, herramientas y `acceptance` propios | Cada facultad = una entrada de catálogo con su conocimiento y sus criterios |
| Generación bajo demanda que puede tardar | `task_delegate` async + `DurableLaneQueue` + aviso al terminar | Un job por clase; el docente sigue usando el menú mientras se genera |
| Control de calidad del recurso (§8 del spec) | `acceptance-checks` deterministas + juicio de cierre + `task_revise` | Los checks de esquema, clave y distribución son los criterios de aceptación; lo no verificable lo juzga el revisor |
| Trazabilidad de cada herramienta | `proof-packet` | Un paquete por recurso: clase, RA, checks aplicados y su resultado |
| Que el sistema mejore con el uso | ACE (reflector → curator → playbook) | Aprender de las ediciones que hacen los docentes a los ítems generados |
| Presupuesto de IA | Presupuestos duros del goal runner y registro de uso | Tope de tokens por clase generada |

**Decisión pendiente:** construir los agentes de facultad **sobre PumaNet**
(el fork de Hive), reutilizando su coordinador, colas, verificación y
aprendizaje, o **en un backend propio** (FastAPI, como dice el spec)
copiando solo los patrones. La primera opción ahorra la infraestructura
agéntica pero ata el proyecto a TypeScript/Bun y al ciclo de cambios de Hive.
