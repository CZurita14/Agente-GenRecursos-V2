# Panel de consumo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Botón y panel de consumo de tokens, abierto a administradores y, con la clave del panel, a cualquier docente con sesión.

**Architecture:** Un servicio de consultas agregadas sobre `llamada_llm`, `trabajo`, `chat_pedido` y `asignatura`; un router `/consumo` con desbloqueo por clave (hash PBKDF2 en el `.env`, cookie firmada ligada a la sesión); un componente React flotante montado en `AppLayout`.

**Tech Stack:** FastAPI, psycopg, hashlib/hmac (stdlib), React 18 + TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-23-panel-consumo-design.md`

## Global Constraints

- La clave nunca en el código, el frontend, el repositorio, los logs ni la bitácora. Solo su hash en `CONSUMO_CLAVE_HASH`.
- Cookie `consumo`: HttpOnly, Secure, SameSite=Lax, 30 minutos, ligada al hash del token de sesión.
- 5 intentos por usuario cada 15 minutos; regla `consumo_clave_usuario_15min`.
- Rango máximo 31 días; por omisión 7 días.
- Sin cambios de esquema en la base de datos.
- Commits con archivos explícitos y `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Sin push.

## Review Focus

1. Cookie `consumo` copiada a otra sesión: debe rechazarse. → Task 2, `test_cookie_de_otra_sesion`.
2. Clave correcta con espacios alrededor: no se recorta (se compara tal cual). → Task 2, `test_clave_con_espacios_no_entra`.
3. Periodo sin llamadas: totales en 0 y listas vacías, no error. → Task 1, `test_periodo_vacio`.
4. Trabajos borrados o de asignaturas inactivas: siguen sumando en totales. → Task 1, `test_asignatura_inactiva_suma`.
5. El cuerpo con la clave no aparece en logs ni bitácora. → Task 2, `test_clave_no_se_registra`.

---

### Task 1: Consultas de consumo

**Files:** Create `backend/app/control/consumo.py`; Test `backend/tests/test_consumo.py`

**Interfaces — Produces:** `resumen(conn, inicio: datetime, fin: datetime, precios: tuple[float, float] | None) -> dict` con claves `totales`, `por_herramienta`, `por_asignatura`, `chat`, `recientes`, `costo_usd`.

- [ ] Pruebas que fallan: `test_totales_y_por_herramienta` (promedio por recurso = tokens ÷ trabajos distintos; `parte_revision` = tokens del rol revisor ÷ total), `test_chat_aparte`, `test_costo_con_y_sin_precios` (USD = entrada ÷ 1e6 × p_ent + salida ÷ 1e6 × p_sal, 4 decimales), `test_recientes_sin_contenido` (solo herramienta, ambito_id, estado, tokens, segundos, fecha; máximo 20), `test_periodo_vacio`, `test_asignatura_inactiva_suma`.
- [ ] Implementar con `statement_timeout` de 3 s, como `admin.py`.
- [ ] Commit `feat(control): consultas de consumo de tokens por herramienta y asignatura`.

### Task 2: Clave del panel y API

**Files:** Modify `backend/app/config.py`, `backend/app/control/servicio.py`, `backend/app/api/aplicacion.py`, `backend/app/operacion.py`; Create `backend/app/api/consumo.py`, `backend/app/control/clave.py`; Test `backend/tests/test_consumo_api.py`

**Interfaces — Produces:**
- `clave.hashear(clave: str, iteraciones=600_000) -> str`, `clave.verificar(clave: str, hash_: str) -> bool`.
- Config: `consumo_clave_hash: SecretStr | None`, `llm_precio_entrada_usd_mtok: float | None`, `llm_precio_salida_usd_mtok: float | None`.
- `POST /consumo/desbloquear` (204 + cookie), `GET /consumo`.
- `python -m app.operacion hash-clave` (stdin → hash).

- [ ] Pruebas que fallan: `test_sin_sesion_401`, `test_sin_clave_403`, `test_clave_erronea_403`, `test_clave_correcta_abre`, `test_admin_entra_directo`, `test_cookie_de_otra_sesion`, `test_cookie_vencida`, `test_sin_hash_503`, `test_sexto_intento_429`, `test_clave_con_espacios_no_entra`, `test_clave_no_se_registra`, `test_hash_clave_por_stdin`.
- [ ] Implementar. La cookie lleva `exp` y la firma HMAC-SHA256 de `hash_token_sesion|exp` con `AUTH_SECRETO`.
- [ ] Correr `pytest tests/test_consumo_api.py tests/test_control_api.py tests/test_config.py -q`.
- [ ] Commit `feat(api): panel de consumo con clave y cookie ligada a la sesión`.

### Task 3: Botón y panel en el frontend

**Files:** Create `frontend/src/components/PanelConsumo.tsx`, `frontend/src/api/consumo.ts`; Modify `frontend/src/components/AppLayout.tsx`, `frontend/src/App.tsx` (montar solo con sesión), `frontend/src/api/tipos.ts`; Test `frontend/tests/consumo.test.ts`

- [ ] Prueba que falla: formateo de tokens (`142 300 → "142 k"`, `1 230 000 → "1,23 M"`) y de costo (`null → "sin precio configurado"`).
- [ ] Implementar: botón `position: fixed` abajo a la derecha (respeta safe-area), panel superpuesto con `role="dialog"`, cerrar con Esc; si `/consumo` responde 403, formulario de clave; selector de periodo; tablas de herramienta, asignatura y recientes.
- [ ] `npm --prefix frontend run check` → tipos, pruebas y build.
- [ ] Verificar en el navegador (localhost): botón visible, layout intacto, desbloqueo y panel.
- [ ] Commit `feat(frontend): botón y panel de consumo de tokens`.

### Task 4: Clave en el .env y documentación

- [ ] Generar el hash de la clave con `hash-clave` y escribir `CONSUMO_CLAVE_HASH` en el `.env` sin mostrarla; reiniciar API.
- [ ] Documentar variables en `.env.example` (sin valores) y una sección en `README.md`.
- [ ] Suite completa del backend y del frontend.
- [ ] Commit `docs: panel de consumo y su configuración`.
