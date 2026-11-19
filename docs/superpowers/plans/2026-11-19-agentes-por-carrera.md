# Agentes por carrera Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Contexto parametrizado por carrera (herencia de la facultad, herramientas excluidas, indicaciones por herramienta y glosario leído), con los YAML de las 8 facultades creados y vacíos.

**Architecture:** El agente sigue siendo un perfil YAML en `agentes/`; `facultades.py` aprende el formato nuevo y la herencia; un validador comprueba los perfiles contra el catálogo y las herramientas al arrancar; el estilo resuelto llega a los workers compartidos con las indicaciones de la herramienta y el glosario.

**Tech Stack:** Python 3.12+, Pydantic, PyYAML, FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-11-18-agentes-por-carrera-design.md`

## Global Constraints

- Repositorio `Agente-GenRecursos-V2`, rama `V3-SilabosPesos`. Pruebas desde `backend/` con `../../Agente-GeneradorRecursos/.venv/Scripts/python.exe -m pytest` (ruta absoluta: `C:/Users/Chris/Desktop/CIA/Agente-GeneradorRecursos/.venv/Scripts/python.exe`).
- Con perfiles vacíos la generación es idéntica a la de hoy: `tests/test_equivalencia_v1.py` sigue pasando (ver Task 3 para la única normalización permitida).
- `excluidas` = unión de facultad y carrera; listas de estilo, `vocabulario` y `recomendadas` por ámbito: la carrera reemplaza si no está vacía; `indicaciones`: por herramienta, gana la carrera.
- Glosario: archivo dentro de `agentes/glosarios/`, de hasta 4 000 caracteres. `vocabulario` es solo el nombre del archivo (sin `/`, `\` ni `..`). La ruta nunca llega al prompt.
- Ids de herramienta válidos: claves de `DEFINICIONES` ∪ claves de `HERRAMIENTAS_SIN_IA`.
- Un error en un YAML hace fallar el arranque de la API, el worker y `app.operacion preparado`.
- Commits con `git add` de archivos explícitos y el pie `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Sin push.

## Review Focus

1. Carrera escrita distinto en el sílabo («ENFERMERIA», «Enfermería») o por un nombre alterno del catálogo: debe encontrar su bloque. → Task 1, `test_carrera_por_nombre_normalizado`; Task 2, `test_carrera_por_nombre_alterno`.
2. Trabajos guardados antes del cambio (`TareaLote` en `mensaje` sin `indicaciones` ni `glosario`): deben seguir cargando y reanudarse. → Task 1, `test_estilo_viejo_sin_campos_nuevos`.
3. Una carrera recomienda una herramienta que su facultad excluye: la exclusión gana y no se ofrece. → Task 5, `test_excluida_por_facultad_gana_a_recomendada_por_carrera`.
4. `vocabulario` con ruta que sale de la carpeta (`../.env`): error al cargar, nunca se lee. → Task 1, `test_glosario_fuera_de_carpeta`.
5. Asignatura importada antes con `agente = general` y sílabo sin cambios: pasa a su facultad en la siguiente sincronización. → Task 6.

---

### Task 1: Perfil con herencia, glosario y estilo por herramienta

**Files:**
- Modify: `backend/app/agentes/mensajes.py` (`EstiloFacultad`)
- Modify: `backend/app/agentes/facultades.py`
- Test: `backend/tests/test_facultades.py`

**Interfaces:**
- Produces:
  - `EstiloFacultad` gana `indicaciones: str = ""` (la de una herramienta) y `glosario: str = ""` (texto del archivo).
  - `class HerramientasPerfil(BaseInmutable)`: `recomendadas: dict[str, list[str]] = {}`, `excluidas: list[str] = []`.
  - `PerfilFacultad` gana `herramientas: HerramientasPerfil`, `indicaciones: dict[str, str] = {}`, `carreras: dict[str, AjusteCarrera]`, `glosarios: dict[str, str] = {}` (nombre de archivo → texto, cargado una vez). Se conserva el atributo `herramientas_recomendadas` como propiedad que devuelve `herramientas.recomendadas`.
  - `class AjusteCarrera(BaseInmutable)`: campos de estilo (vacíos por omisión) + `herramientas: HerramientasPerfil = HerramientasPerfil()` + `indicaciones: dict[str, str] = {}`.
  - `estilo_para(perfil, carrera: str, herramienta: str | None = None) -> EstiloFacultad`
  - `herramientas_para(perfil, carrera: str) -> HerramientasPerfil` (recomendadas por ámbito y excluidas ya heredadas).
  - `cargar_perfiles(directorio)` mantiene su firma; acepta el formato viejo (`herramientas_recomendadas`) y el nuevo (`herramientas`), y lee los glosarios de `directorio / "glosarios"`.

- [ ] **Step 1: Pruebas que fallan** en `test_facultades.py`, con perfiles escritos en `tmp_path` (incluye `general.yaml` mínimo):
  - `test_carrera_hereda_de_la_facultad`: carrera sin datos → `estilo_para(...) == perfil.estilo` con `indicaciones == ""` y `glosario == ""`.
  - `test_carrera_por_nombre_normalizado`: bloque `enfermeria`; `estilo_para(p, "ENFERMERÍA").escenarios == ["triaje"]`.
  - `test_indicaciones_por_herramienta`: facultad `{practica_guiada: "F", tarjetas: "T"}`, carrera `{practica_guiada: "C"}` → `estilo_para(p, c, "practica_guiada").indicaciones == "C"`, `"tarjetas"` → `"T"`, sin herramienta → `""`.
  - `test_herramientas_heredadas`: facultad `excluidas: [tarjetas]`, `recomendadas: {clase: [cuestionario]}`; carrera `excluidas: [presentacion]`, `recomendadas: {momento: [simulacro]}` → `excluidas == ["presentacion", "tarjetas"]` (ordenadas), `recomendadas == {"clase": ["cuestionario"], "momento": ["simulacro"]}`.
  - `test_glosario_leido`: `glosarios/salud.md` con `"PA: presión arterial"` y `vocabulario: salud.md` → `estilo_para(...).glosario == "PA: presión arterial"`.
  - `test_glosario_fuera_de_carpeta` (parametrizado `"../x.md"`, `"sub/x.md"`, `"no_existe.md"`) → `cargar_perfiles` lanza `ValueError`.
  - `test_glosario_demasiado_largo`: 4 001 caracteres → `ValueError`.
  - `test_recomendada_y_excluida_a_la_vez`: en la misma carrera → `ValueError`.
  - `test_clave_desconocida`: `estilo: {colores: []}` → `ValueError`.
  - `test_formato_viejo_sigue_cargando`: YAML con `herramientas_recomendadas` → `perfil.herramientas.recomendadas` igual.
  - `test_estilo_viejo_sin_campos_nuevos`: `EstiloFacultad.model_validate({"tipos_de_caso": [], "software_habitual": [], "vocabulario": "x", "escenarios": []})` funciona.

- [ ] **Step 2:** Correr `pytest tests/test_facultades.py -q` → fallan las nuevas.

- [ ] **Step 3: Implementar** en `mensajes.py` y `facultades.py`. Los errores de `cargar_perfiles` nombran el archivo y la clave, nunca el contenido del glosario. `vocabulario` sigue guardando el nombre del archivo; `glosario` lleva el texto.

- [ ] **Step 4:** Correr `pytest tests/test_facultades.py tests/test_mensajes.py -q` → pasan.

- [ ] **Step 5: Commit** `feat(agentes): perfil por carrera con herencia, indicaciones y glosario`.

---

### Task 2: Validación contra el catálogo y las herramientas al arrancar

**Files:**
- Create: `backend/app/agentes/validar_perfiles.py`
- Modify: `backend/app/agentes/facultades.py` (`cargar_carreras`)
- Modify: `backend/app/api/aplicacion.py:48`, `backend/worker.py:95`, `backend/app/operacion.py:56`
- Test: `backend/tests/test_validar_perfiles.py`

**Interfaces:**
- Consumes: `cargar_perfiles`, `PerfilFacultad` (Task 1).
- Produces:
  - `cargar_carreras(ruta: Path) -> dict[str, set[str]]` en `facultades.py`: sigla → nombres normalizados de sus carreras, con `nombres_alt`.
  - `validar_perfiles(perfiles, carreras: dict[str, set[str]], herramientas: set[str]) -> list[str]`: fallos `"<id perfil>: <ruta>: <motivo>"`.
  - `cargar_validados(directorio: Path, ruta_catalogo: Path) -> dict[str, PerfilFacultad]`: carga, valida contra `DEFINICIONES` ∪ `HERRAMIENTAS_SIN_IA` y lanza `ValueError` con todos los fallos juntos.
  - `estilo_para` resuelve la carrera también por sus `nombres_alt`: `PerfilFacultad` gana `alias: dict[str, str] = {}` (nombre alterno normalizado → clave de carrera), que `cargar_validados` completa desde el catálogo.

- [ ] **Step 1: Pruebas que fallan:**
  - `test_carrera_fuera_del_catalogo`: perfil FCSBH con carrera `astronomia` → fallo que contiene `carreras.astronomia`.
  - `test_herramienta_inexistente`: `excluidas: [dibujo]` → fallo que contiene `dibujo`.
  - `test_indicacion_de_herramienta_inexistente`: `indicaciones: {dibujo: "x"}` → fallo.
  - `test_carrera_de_otra_facultad`: perfil FCSBH con carrera `software` → fallo.
  - `test_carrera_por_nombre_alterno`: perfil FING con bloque `software`; `estilo_para(p, "INGENIERIA DE SOFTWARE")` devuelve el estilo de `software`.
  - `test_perfiles_reales_validos`: `cargar_validados(RAIZ/"agentes", RAIZ/"kb/catalogo.yaml")` no lanza.

- [ ] **Step 2:** Correr `pytest tests/test_validar_perfiles.py -q` → fallan.

- [ ] **Step 3: Implementar** y reemplazar `cargar_perfiles(...)` por `cargar_validados(..., RAIZ / "kb/catalogo.yaml")` en los tres arranques. El import de `DEFINICIONES` y `HERRAMIENTAS_SIN_IA` va dentro de `validar_perfiles.py` (no en `facultades.py`) para no crear ciclos.

- [ ] **Step 4:** Correr `pytest tests/test_validar_perfiles.py tests/test_facultades.py tests/test_config.py tests/test_infra_config.py -q` → pasan.

- [ ] **Step 5: Commit** `feat(agentes): validar perfiles contra catálogo y herramientas al arrancar`.

---

### Task 3: Indicaciones y glosario en el prompt

**Files:**
- Modify: `backend/app/llm/prompts.py` (`_seccion_perfil`, `construir_prompt`)
- Modify: `backend/tests/test_equivalencia_v1.py` (normalización)
- Test: `backend/tests/test_prompts.py`

**Interfaces:**
- Consumes: `EstiloFacultad.indicaciones`, `EstiloFacultad.glosario` (Task 1).
- Produces: `_seccion_perfil(c, e, *, con_glosario: bool = True) -> str`.

- [ ] **Step 1: Pruebas que fallan** en `test_prompts.py`:
  - `test_indicaciones_de_la_carrera`: estilo con `indicaciones="Caso clínico paso a paso."` → el user contiene `"Indicaciones de la carrera para esta herramienta: Caso clínico paso a paso."` dentro de `<silabo>`.
  - `test_glosario_en_lineas_y_sin_ruta`: `vocabulario="salud.md"`, `glosario="PA: presión arterial\nFC: frecuencia cardiaca"` → contiene `"Glosario de la carrera:\n- PA: presión arterial\n- FC: frecuencia cardiaca"` y no contiene `"salud.md"` ni `"Vocabulario:"`.
  - `test_sin_campos_nuevos_igual_que_antes`: con el `ESTILO` actual del archivo, el prompt es igual al de hoy (comparar contra el resultado calculado antes del cambio, guardado como literal en la prueba).
  - `test_glosario_sale_antes_que_ya_generado`: `contar` que solo admite el prompt sin glosario → el resultado conserva todos los `ya_generado` y no tiene `"Glosario de la carrera"`.

- [ ] **Step 2:** Correr `pytest tests/test_prompts.py -q` → fallan.

- [ ] **Step 3: Implementar.** Quitar la línea `Vocabulario:` de `_seccion_perfil`. Cada línea del glosario pasa por `_limpio` y se lista con `_lista`. En `construir_prompt`, si `cabe(len(ya), total_rubrica)` falla y hay glosario, se reintenta con `con_glosario=False` antes de recortar `ya_generado`; desde ahí, el orden de recorte de hoy.

- [ ] **Step 4: Normalizar la equivalencia.** La V1 imprimía la ruta del glosario (`Vocabulario: agentes/glosarios/ingenierias.md`, 9 apariciones en el oráculo). En `test_equivalencia_v1.py`, `normalizar` quita de cada prompt las líneas que empiezan con `"Vocabulario: "`. Comentario: corrección intencional, la ruta nunca debió llegar al modelo.

- [ ] **Step 5:** Correr `pytest tests/test_prompts.py tests/test_equivalencia_v1.py -q` → pasan (59 huellas).

- [ ] **Step 6: Commit** `feat(prompts): indicaciones y glosario de la carrera; la ruta del glosario ya no llega al modelo`.

---

### Task 4: La herramienta llega al estilo en generación y chat

**Files:**
- Modify: `backend/app/agentes/planificador.py` (`estilo_razonado`)
- Modify: `backend/app/agentes/coordinador.py:118`, `:123`
- Modify: `backend/app/chat/ajustes.py:206`
- Test: `backend/tests/test_coordinador.py`, `backend/tests/test_chat_ajustes.py`

**Interfaces:**
- Consumes: `estilo_para(perfil, carrera, herramienta)` (Task 1).
- Produces: `estilo_razonado(perfil, carrera, contexto, razonador, herramienta: str | None = None) -> EstiloFacultad`.

- [ ] **Step 1: Pruebas que fallan:**
  - En `test_coordinador.py`, `test_estilo_lleva_indicaciones_de_la_herramienta`: perfil con `indicaciones: {cuestionario: "Usa casos clínicos."}`; el `TareaLote` guardado del trabajo tiene `estilo.indicaciones == "Usa casos clínicos."`.
  - En `test_chat_ajustes.py`, `test_ajuste_usa_indicaciones_de_la_carrera`: el `TareaLote` que recibe el worker simulado tiene esas indicaciones.

- [ ] **Step 2:** Correr ambas → fallan.

- [ ] **Step 3: Implementar** pasando `encargo.herramienta` en el coordinador (las dos ramas: plan guardado y plan nuevo) y `herramienta` en `ajustes.py`.

- [ ] **Step 4:** Correr `pytest tests/test_coordinador.py tests/test_coordinador_ambito.py tests/test_chat_ajustes.py tests/test_planificador.py -q` → pasan.

- [ ] **Step 5: Commit** `feat(agentes): el estilo de cada trabajo lleva las indicaciones de su herramienta`.

---

### Task 5: Catálogo y pedido respetan las herramientas de la carrera

**Files:**
- Modify: `backend/app/recursos/servicio.py` (`catalogo`, `generar`)
- Test: `backend/tests/test_generacion_api.py` (o el archivo de pruebas del catálogo que ya cubre `/herramientas`)

**Interfaces:**
- Consumes: `herramientas_para(perfil, carrera)` (Task 1).
- Produces: mensaje 422 exacto: `"Esta herramienta no está disponible para la carrera."`

- [ ] **Step 1: Pruebas que fallan** (perfil de prueba con `excluidas` para la carrera de los sílabos simulados):
  - `test_catalogo_oculta_excluidas`: `GET …/herramientas?ambito=clase` no lista `tarjetas`.
  - `test_catalogo_recomienda_por_carrera`: las recomendadas de la carrera salen primero con `recomendada: true`.
  - `test_generar_excluida_422`: `POST …/generar` con `tarjetas` → 422 con el mensaje exacto; no se crea ningún trabajo.
  - `test_generar_sin_ia_excluida_422`: igual con `hoja_ruta` excluida.
  - `test_excluida_por_facultad_gana_a_recomendada_por_carrera`: no aparece en el catálogo.

- [ ] **Step 2:** Correr → fallan.

- [ ] **Step 3: Implementar.** En `catalogo`: `h = herramientas_para(self.perfiles[a["agente"]], silabo.carrera)`; filtra `disponibles` por `h.excluidas` y ordena por `h.recomendadas.get(ambito, [])`. En `generar`: la comprobación va al inicio, antes de separar con y sin IA. (El spec lo ubicaba en el orquestador; va en el servicio porque ahí están los perfiles y cubre también las herramientas sin IA.)

- [ ] **Step 4:** Correr `pytest tests/test_generacion_api.py tests/test_sin_ia_api.py tests/test_materias_api.py -q` → pasan.

- [ ] **Step 5: Commit** `feat(recursos): el catálogo y el pedido respetan las herramientas de la carrera`.

---

### Task 6: Reenrutar asignaturas ya importadas

**Files:**
- Modify: `backend/app/asignaturas/servicio.py` (`ServicioAsignaturas`)
- Modify: `backend/app/sga/sincronizar.py` (rama `sin_cambios`)
- Test: `backend/tests/test_sga_sincronizar.py`

**Interfaces:**
- Produces: `ServicioAsignaturas.reenrutar(asignatura_id: str, silabo: SilaboUTI) -> bool` (True si cambió `asignatura.agente`).

- [ ] **Step 1: Prueba que falla** `test_sin_cambios_actualiza_el_agente`: sincronizar; poner `agente='general'` a mano en la asignatura; sincronizar otra vez → estado `sin_cambios` y `agente == 'ingenierias'`; `version_silabo` y `silabo` no cambian.

- [ ] **Step 2:** Correr → falla.

- [ ] **Step 3: Implementar** con `enrutar(silabo.facultad, self.catalogo, self.perfiles)` y un `update … where id=%s and agente<>%s`.

- [ ] **Step 4:** Correr `pytest tests/test_sga_sincronizar.py tests/test_materias_api.py -q` → pasan.

- [ ] **Step 5: Commit** `feat(sga): reenrutar al agente de su facultad las asignaturas sin cambios`.

---

### Task 7: Perfiles de las 8 facultades, glosarios y documentación

**Files:**
- Create: `agentes/arquitectura.yaml` (FADA), `agentes/economicas.yaml` (FACEAN), `agentes/educacion.yaml` (FCED), `agentes/medio_ambiente.yaml` (FCMA), `agentes/salud.yaml` (FCSBH), `agentes/sociales.yaml` (FCSH), `agentes/jurisprudencia.yaml` (FJCP)
- Create: `agentes/glosarios/README.md`
- Modify: `agentes/ingenierias.yaml` (`vocabulario: ""`; bloques vacíos para Industrial, Ingeniería Civil, Mecatrónica y Electricidad; `herramientas_recomendadas` pasa a `herramientas.recomendadas`)
- Create: `agentes/README.md` (formato, herencia, cómo cargar una carrera)
- Modify: `README.md` (tabla de piezas: perfiles por carrera)
- Test: `backend/tests/test_validar_perfiles.py`

- [ ] **Step 1: Prueba que falla** `test_las_ocho_facultades_y_sus_carreras`: con `cargar_validados` reales, hay un perfil por cada sigla del catálogo; cada perfil tiene un bloque por cada carrera del catálogo de su sigla; todos los bloques nuevos están vacíos (`estilo_para(p, c) == p.estilo` para las facultades nuevas).

- [ ] **Step 2:** Correr → falla.

- [ ] **Step 3: Crear los YAML** con el formato del spec, valores vacíos y un comentario de cabecera: «Contenido pendiente de la documentación de la carrera; vacío = misma generación que el agente general». Ningún contenido inventado.

- [ ] **Step 4:** Correr `pytest tests/test_validar_perfiles.py tests/test_facultades.py tests/test_equivalencia_v1.py -q` → pasan.

- [ ] **Step 5: Suite completa:** `pytest -q -p no:cacheprovider --deselect tests/test_cd_entrenar.py --deselect tests/test_razonador.py` → 0 fallos; y los dos archivos de modelo con `.venv-ciencia`.

- [ ] **Step 6: Commit** `feat(agentes): perfiles de las 8 facultades listos para cargar contexto`.
