# Generador de Recursos de Estudio UTI · V2

Aplicación web interna para que los docentes de la Universidad Tecnológica Indoamérica conviertan el sílabo de su proyecto formativo en herramientas de estudio: cuestionarios, simulacros, fichas de clase, guías, rúbricas y más. La IA es un modelo local, Qwen3-8B-AWQ servido por vLLM, así que los datos no salen de la red de la universidad.

## Qué es la V2

La V2 consume los sílabos **desde la API del SGA, en JSON**. No hay carga de PDF, lector de PDF, SMTP ni código por correo: el docente ingresa con su usuario y clave del SGA, el sistema trae sus materias y el sílabo de cada una, los valida y genera los recursos. Todo lo que viene después del sílabo validado (contexto, plan, prompts, verificador, revisor, herramientas) es el mismo código de la V1, y su equivalencia está probada (ver más abajo).

> **Estado del SGA real: pendiente de TI (bloqueo B-SGA1).** TI debe definir el mecanismo de autenticación, las consultas de materias y de sílabo y una cuenta de prueba ([docs/sga/para-TI.md](docs/sga/para-TI.md)). Mientras tanto todo funciona contra un **SGA simulado** con fixtures. En producción el adaptador real (`backend/app/sga/real.py`) aún responde «pendiente de TI».

## Cómo funciona

```
Docente ──usuario y clave del SGA──▶ SGA (autentica y entrega materias y sílabos en JSON)
                                         │
              traductor (lista blanca) ◀─┘
                      │
                      ▼
      SilaboUTI validado (esquema + 7 reglas) ──▶ Base de datos
                                                      │
        Docente elige clase, momento o asignatura ◀───┘
                              │
                              ▼
      Contexto ──▶ Plan ──▶ Qwen redacta ──▶ Verificador ──▶ Revisor ──▶ Recurso
                   (código)                  (código)         (Qwen)
```

1. **Ingreso con el SGA.** `POST /auth/ingresar` recibe usuario y clave y los pasa al SGA. Devuelve usuario, correo institucional y nombre (`docs/api-silabo/auth-sga.schema.json`). La clave no se guarda en ningún lugar: ni en la base, ni en los registros. Tras 5 claves erróneas seguidas, el usuario queda bloqueado 15 minutos (429). Si el SGA no responde, el error es 503 y no cuenta como intento fallido.
2. **Materias.** Al ingresar se sincronizan las materias del docente (`id_sga`, `codigo_pf`, `paralelo`, nombre, carrera, estado) y `GET /materias` las lista. Una asignatura cuya materia el SGA ya no lista queda inactiva, pero nunca se borra. Hay una asignatura por docente y código PF: dos paralelos comparten el mismo sílabo.
3. **Sílabo en JSON.** Por cada materia se pide el sílabo. Un **traductor de lista blanca** (`backend/app/sga/traductor.py`) deja pasar solo las claves que declara el contrato `docs/api-silabo/silabo-api.schema.json` y descarta todo lo demás (docente, contacto, firmas, cédula, etc.) sin mirarlo. `SilaboUTI` además rechaza cualquier campo desconocido, de modo que los datos personales no tienen dónde guardarse.
4. **Validación.** El sílabo debe cumplir el esquema (Pydantic) y **7 reglas de integridad** (`backend/app/silabo/integridad.py`): números de momento sin repetir; cada resultado de aprendizaje del momento debe existir; cada momento con sesiones; id de sesión `M<momento>-S<n>` coherente con su momento; id de sesión sin repetir; fecha de la sesión dentro del periodo; contenidos sin elementos vacíos. Los fallos son `ruta: regla`, sin valores del sílabo. Una materia con sílabo inválido se muestra desactivada con su motivo; las demás siguen.
5. **Menú de clases.** El sílabo se guarda una vez y se organiza por semanas, momentos y sesiones. Solo se vuelve a importar si cambia su versión.
6. **Contexto, plan, redacción y controles.** Igual que en la V1: según la clase `M2-S1`, el momento `M2` o la asignatura completa, el código extrae solo esa parte del sílabo; el planificador decide por código el nivel y el foco de cada pregunta; un único constructor de prompts arma el pedido dentro del límite de 8192 tokens, con el sílabo marcado como dato y nunca como instrucción; un verificador determinista y un revisor con Qwen devuelven lo que falla, hasta dos rondas. El resultado final siempre lo revisa el docente.

## Modelo matemático (igual que en la V1)

- **Razonador** (`backend/app/razonador.py`, entrenado en `backend/ciencia_datos/`): un codificador MiniLM multilingüe (`paraphrase-multilingual-MiniLM-L12-v2`) ajustado con SimCSE sin etiquetas (pérdida contrastiva, escala 20 = temperatura 0,05). Produce vectores con norma L2, así que el producto punto es el coseno. Decide dos cosas:
  - **Temas:** k-medias con semilla fija sobre los vectores de los focos; k entre 2 y 8 elegido por silueta, y a igualdad el menor. Las preguntas recorren un foco de cada tema antes de repetir.
  - **Casos libres:** un caso queda libre solo si su mayor coseno con cualquier entregable está estrictamente por debajo de un umbral fijado en la evaluación.
- **Planificador determinista** (`backend/app/agentes/planificador.py`): la **tabla de especificaciones** reparte las preguntas entre los niveles (receptivo, resolutivo, reflexivo, crítico) según el perfil de dificultad con el **método del mayor resto**, con porcentajes enteros y desempate hacia el nivel más bajo. Los **focos** se asignan uniformemente si hay más focos que preguntas, y con un **paso coprimo** con el número de focos si hay más preguntas que focos.
- **Verificador:** reglas deterministas sobre cada recurso.
- **Qwen3-8B** solo redacta (enunciado, opciones, respuesta correcta, explicaciones). No participa en vectores, entrenamiento ni evaluación.

El razonador es **opcional y está apagado por omisión** (sin `RAZONADOR_RUTA`, la generación es la de siempre). Entrenamiento, evaluación y criterios: [docs/ciencia-datos.md](docs/ciencia-datos.md).

## Herramientas

| Con IA | Ámbito |
|---|---|
| Cuestionario autocorregible | Clase |
| Ficha de clase (conceptual y de aplicación) | Clase |
| Simulacro | Momento |
| Repaso del momento | Momento |
| Guía de la evidencia | Momento |
| Estudio de caso | Momento |
| Guía del producto final | Asignatura |

**Sin IA:** hoja de ruta, rúbrica del momento, rúbrica final, autoevaluaciones y lista de verificación de la evidencia. Salen directamente del sílabo.

Los recursos se editan, se ajustan con un chat privado y se exportan a HTML, PDF y Word.

## Qué apartados del sílabo se usan

| Uso | Apartados |
|---|---|
| Generar recursos | Facultad, carrera, periodo, nombre y nivel del proyecto formativo, competencia del perfil, resultados de aprendizaje, problema (descripción, reto y producto final), momentos (título, fechas, evidencia, política de IA, rúbrica) y sesiones (fecha, contenidos, actividades docente, práctica y autónoma, entregables) |
| Entrenar el modelo de ciencia de datos | Textos de resultados de aprendizaje, evidencias, contenidos y actividades |
| No se usan hoy | PIS, metodologías, bibliografía, competencia del proyecto formativo, metacompetencia, horas y créditos (el contrato los admite como opcionales) |

El detalle está en [docs/api-silabo/README.md](docs/api-silabo/README.md).

## Arquitectura

```
Docentes ──HTTPS──▶ proxy (nginx) ──▶ web (React)
                         │
                         └──/api/──▶ api (FastAPI) ──▶ db (PostgreSQL 18)
                                         │                 ▲
                                         ▼                 │
                                      SGA (API)   worker ──┘──▶ vLLM con Qwen (fuera de Docker)
```

| Parte | Tecnología | Carpeta |
|---|---|---|
| Acceso al SGA (proveedor, traductor, simulado, sincronización) | Python 3.12+ | `backend/app/sga/` |
| Validación del sílabo, agentes, API y worker | Python 3.12+, FastAPI, Pydantic | `backend/app/` |
| Interfaz | React 18, TypeScript, Vite | `frontend/` |
| Base de datos y cola de trabajos | PostgreSQL 18 | `kb/`, `backend/app/db/` |
| Perfiles por facultad | YAML | `agentes/` |
| Catálogo de facultades y carreras | YAML | `kb/catalogo.yaml` |
| Despliegue | Docker Compose, nginx | `infra/` |
| Ciencia de datos (fuera de producción) | PyTorch, sentence-transformers, ONNX | `backend/ciencia_datos/` |

## Puesta en marcha

### Desarrollo con el SGA simulado

En el `.env` de la raíz (no versionado), además de la base de datos y el servidor de IA, van estas cinco variables:

```text
ENTORNO=desarrollo
API_ORIGEN=http://localhost:5173
SGA_PROVEEDOR=simulado
SGA_SIMULADO_DIR=backend/tests/fixtures/sga
AUTH_SECRETO=<al menos 32 caracteres aleatorios propios>
```

- `SGA_SIMULADO_DIR` es relativa a la raíz del proyecto. Si la carpeta no tiene `usuarios.json`, la API no arranca y lo dice.
- `AUTH_SECRETO` se genera una vez, por ejemplo con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. No se versiona ni se comparte; sin él el ingreso responde 503.
- `API_ORIGEN` es el origen del servidor de Vite (`npm --prefix frontend run dev`), que reenvía `/api/*` a la API en el puerto 8001. No hace falta HTTPS local.

El SGA simulado lee `usuarios.json`, `materias/<usuario>.json` y `sga_silabos/<codigo_pf>.json` de esa carpeta: dos docentes de prueba (`docente.uno`, `docente.dos`) y tres sílabos simulados `S91-SIMU-…` que traen claves privadas falsas para comprobar que el traductor las descarta. `usuarios.json` guarda solo el hash SHA-256 de cada clave; **las claves de prueba están en las constantes de las pruebas** (`backend/tests/test_auth.py`), no en la documentación. El proveedor simulado no se admite con `ENTORNO=produccion`.

### Producción

Exige `SGA_PROVEEDOR=real`, que depende de TI (B-SGA1): [docs/sga/para-TI.md](docs/sga/para-TI.md). El despliegue institucional (servidor, DNS, TLS, servidor de IA) está en [docs/entrega-ti.md](docs/entrega-ti.md); la operación, el respaldo y la restauración, en [docs/operacion.md](docs/operacion.md); la API, en [docs/desarrollo-api.md](docs/desarrollo-api.md).

### Pruebas

```bash
# Backend (base: 1202 pasan, 14 deseleccionadas)
cd backend && ../.venv/Scripts/python.exe -m pytest -m "not servidor and not modelo" -q
# Modelo de ciencia de datos (entorno con PyTorch)
cd backend && HF_HUB_OFFLINE=1 ../.venv-ciencia/Scripts/python.exe -m pytest -m modelo -q tests/test_razonador.py tests/test_cd_*.py
# Frontend
npm --prefix frontend test
npm --prefix frontend run build
```

### Equivalencia con la V1

Un sílabo del SGA, una vez traducido y validado, produce exactamente el mismo contexto, prompts, plan y menú que en la V1. `backend/tests/test_equivalencia_v1.py` compara **59 huellas** generadas con el código de la V1 (commit `011bd68`) contra la V2: las 59 son idénticas. El oráculo y su generador están en `backend/tests/fixtures/v1/`.

Cuando TI entregue acceso al SGA real, `python -m app.sga.comparar <carpeta_sga> <carpeta_referencia>` compara los JSON del SGA con los de referencia y lista las rutas de campos distintas y el porcentaje de coincidencia, nunca valores ([docs/sga/para-TI.md](docs/sga/para-TI.md)).

## Documentación

| Documento | Contenido |
|---|---|
| [progress.md](progress.md) | Estado del proyecto, bitácora y decisiones |
| [docs/sga/para-TI.md](docs/sga/para-TI.md) | Qué debe entregar TI para conectar el SGA real |
| [docs/api-silabo/](docs/api-silabo/) | Contratos JSON: sílabo, materias y autenticación |
| [docs/ciencia-datos.md](docs/ciencia-datos.md) | Modelo de ciencia de datos, simulación y evaluación |
| [docs/entrega-ti.md](docs/entrega-ti.md) | Ficha de entrega del despliegue a TI |
| [docs/operacion.md](docs/operacion.md) | Operación, respaldo y restauración |
| [docs/desarrollo-api.md](docs/desarrollo-api.md) | API local, configuración y pruebas |
| [docs/superpowers/plans/](docs/superpowers/plans/) | Planes de implementación |

### Historia de V1

Estos documentos describen la V1 (entrada por el PDF del sílabo) y se conservan como historia; no describen el comportamiento actual de la V2:

- [docs/especificacion-generador-recursos-uti-v1.0.md](docs/especificacion-generador-recursos-uti-v1.0.md) a [v1.3](docs/especificacion-generador-recursos-uti-v1.3.md) (especificaciones)
- [docs/mapeo-silabo.md](docs/mapeo-silabo.md) (estructura del PDF)
- [docs/arquitectura-agentica-hive.md](docs/arquitectura-agentica-hive.md)
- [docs/base-conocimiento-carreras.md](docs/base-conocimiento-carreras.md)
- [docs/privacidad-borrador.md](docs/privacidad-borrador.md)
- [docs/prueba-calidad-silabo.md](docs/prueba-calidad-silabo.md)
- [docs/catalogo-herramientas.md](docs/catalogo-herramientas.md)
- [docs/analisis-astra-ai.md](docs/analisis-astra-ai.md)

## Datos que no se versionan

Los sílabos reales (`Silabos/`), el archivo `.env`, los modelos entrenados de `modelos/` y los datos generados de `datos_cd/` quedan fuera del repositorio: pueden contener datos personales o pesan demasiado.
