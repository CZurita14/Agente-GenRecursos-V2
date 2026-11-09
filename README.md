# Generador de Recursos de Estudio UTI

Aplicación web interna para que los docentes de la Universidad Tecnológica Indoamérica conviertan el sílabo de su proyecto formativo en herramientas de estudio: cuestionarios, simulacros, fichas de clase, guías, rúbricas y más. La IA es un modelo local, Qwen3-8B-AWQ servido por vLLM, así que los datos no salen de la red de la universidad.

> **Entrada actual: el PDF del sílabo.** Todo el sistema funciona hoy consumiendo el PDF institucional que sube el docente. Existe un contrato JSON para recibir el sílabo desde una API ([docs/api-silabo/](docs/api-silabo/)), pero **es solo una propuesta documentada y validada con pruebas**: no hay ningún punto de entrada por API implementado.

## Cómo funciona

```
PDF del sílabo ──▶ Lector (sin IA) ──▶ SilaboUTI ──▶ Base de datos
                                                        │
          Docente elige clase, momento o asignatura ◀───┘
                              │
                              ▼
        Contexto ──▶ Plan ──▶ Qwen redacta ──▶ Verificador ──▶ Revisor ──▶ Recurso
                     (código)                  (código)         (Qwen)
```

1. **Lectura del PDF, sin IA.** El lector (`backend/app/silabo/lector/`) abre el PDF y extrae la portada y las secciones II a VI: datos del proyecto formativo, resultados de aprendizaje, problema, momentos, sesiones, rúbricas y bibliografía. Produce un objeto `SilaboUTI` (`backend/app/silabo/modelo.py`).
2. **Privacidad desde el lector.** Las secciones I (perfil y contacto del docente) y VII (firmas) no se leen. `SilaboUTI` rechaza cualquier campo desconocido, de modo que los datos personales no tienen dónde guardarse. Si al PDF le falta algo esencial, se rechaza con un mensaje claro.
3. **Menú de clases.** El sílabo leído se guarda una vez y se organiza por semanas, momentos y sesiones. El PDF no se vuelve a leer.
4. **Contexto.** Según lo que elija el docente (una clase `M2-S1`, un momento `M2` o la asignatura completa), el código extrae solo esa parte del sílabo: contenidos, actividades, resultados de aprendizaje, rúbrica, entregables, política de IA, competencia del perfil y problema. No hay búsqueda por vectores en este paso.
5. **Plan sin IA.** Para cuestionarios y simulacros, el planificador decide por código el nivel cognitivo y el foco de cada pregunta.
6. **Redacción con Qwen.** Un único constructor de prompts arma el pedido dentro del límite de 8192 tokens. El sílabo va marcado como dato, nunca como instrucción.
7. **Controles.** Un verificador determinista y un revisor con Qwen devuelven lo que falla para corregirlo, hasta dos rondas. La regla de integridad impide resolver los entregables evaluados del estudiante. El resultado final siempre lo revisa el docente.

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

De lo que el lector extrae del PDF, el sistema consume:

| Uso | Apartados |
|---|---|
| Generar recursos | Facultad, carrera, periodo, nombre y nivel del proyecto formativo, competencia del perfil, resultados de aprendizaje, problema (descripción, reto y producto final), momentos (título, fechas, evidencia, política de IA, rúbrica) y sesiones (fecha, contenidos, actividades docente, práctica y autónoma, entregables) |
| Entrenar el modelo de ciencia de datos | Textos de resultados de aprendizaje, evidencias, contenidos y actividades |
| No se usan hoy | PIS, metodologías, bibliografía, competencia del proyecto formativo, metacompetencia, horas y créditos |

El detalle, con las pasadas de prueba que lo validan, está en [docs/api-silabo/README.md](docs/api-silabo/README.md).

## Arquitectura

```
Docentes ──HTTPS──▶ proxy (nginx) ──▶ web (React)
                         │
                         └──/api/──▶ api (FastAPI) ──▶ db (PostgreSQL 18)
                                                          ▲
                                        worker ───────────┘──▶ vLLM con Qwen (fuera de Docker)
```

| Parte | Tecnología | Carpeta |
|---|---|---|
| Lector de PDF, agentes, API y worker | Python 3.12+, FastAPI, Pydantic | `backend/app/` |
| Interfaz | React 18, TypeScript, Vite | `frontend/` |
| Base de datos y cola de trabajos | PostgreSQL 18 | `kb/`, `backend/app/db/` |
| Perfiles por facultad | YAML | `agentes/` |
| Catálogo de facultades y carreras | YAML | `kb/catalogo.yaml` |
| Despliegue | Docker Compose, nginx | `infra/` |
| Ciencia de datos (fuera de producción) | PyTorch, sentence-transformers, ONNX | `backend/ciencia_datos/` |

## Ciencia de datos

Un codificador entrenado (MiniLM multilingüe ajustado con aprendizaje contrastivo) puede razonar sobre el sílabo antes de que Qwen escriba: agrupa los focos por tema y descarta casos parecidos a los entregables. Qwen no participa en vectores, entrenamiento ni evaluación.

- **Opcional y apagado por omisión.** Sin la variable `RAZONADOR_RUTA`, la generación es la de siempre. En producción solo se carga un modelo aprobado con etiquetas docentes.
- **Entrenamiento y evaluación** con separación 70/30 por sílabo y evaluación única por versión: [docs/ciencia-datos.md](docs/ciencia-datos.md).
- **Simulación de sílabos.** Mientras llegan más sílabos reales, se generan sílabos simulados para 29 carreras de grado. El modelo que se entrena con ellos queda marcado como `preliminar` y nunca puede cargarse en producción.
- **Resultado de la corrida actual:** el modelo base sin ajustar acierta la facultad de un fragmento en el 30,4 % de los casos, frente a un 13,8 % al azar. Ajustarlo con simulados lo empeora, así que el entrenamiento útil espera los sílabos reales.

## Puesta en marcha

- **Despliegue institucional:** [docs/entrega-ti.md](docs/entrega-ti.md), con requisitos de servidor, DNS, TLS, servidor de IA y SMTP.
- **Operación, respaldo y restauración:** [docs/operacion.md](docs/operacion.md).
- **Desarrollo de la API:** [docs/desarrollo-api.md](docs/desarrollo-api.md).
- **Pruebas del backend:**

```bash
cd backend && ../.venv/Scripts/python.exe -m pytest -m "not servidor and not modelo" -q
```

## Documentación

| Documento | Contenido |
|---|---|
| [progress.md](progress.md) | Estado del proyecto, bitácora y decisiones |
| [docs/especificacion-generador-recursos-uti-v1.3.md](docs/especificacion-generador-recursos-uti-v1.3.md) | Especificación vigente |
| [docs/mapeo-silabo.md](docs/mapeo-silabo.md) | Estructura del PDF del sílabo y contrato `SilaboUTI` |
| [docs/catalogo-herramientas.md](docs/catalogo-herramientas.md) | Catálogo de herramientas |
| [docs/ciencia-datos.md](docs/ciencia-datos.md) | Modelo de ciencia de datos, simulación y evaluación |
| [docs/api-silabo/](docs/api-silabo/) | Contrato JSON propuesto para una futura API (no implementado) |
| [docs/superpowers/plans/](docs/superpowers/plans/) | Planes de implementación por bloque |

## Datos que no se versionan

Los PDF reales de `Silabos/`, el archivo `.env`, los modelos entrenados de `modelos/` y los datos generados de `datos_cd/` quedan fuera del repositorio: pueden contener datos personales o pesan demasiado.
