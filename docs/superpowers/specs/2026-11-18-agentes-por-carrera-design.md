# Agentes por carrera: contexto parametrizado

Fecha: 2026-11-18 · Rama: `V3-SilabosPesos` · Estado: borrador para aprobar

## Intención

Cada carrera debe generar herramientas con la lógica de su disciplina: una práctica guiada de Software es un ejercicio de código; la de Enfermería, un caso clínico. Hoy solo Ingenierías tiene perfil; las otras 7 facultades (Salud es 42 de 51 sílabos reales) usan el agente `general`, sin contexto.

El usuario decidió: **mantener la arquitectura** (orquestador que enruta, agente como perfil de datos, workers compartidos sin estado) y **dejar la lógica parametrizada y lista**, para cargar el contenido de cada carrera cuando llegue su documentación.

## Objetivos

1. Un perfil por facultad con un bloque por carrera, que hereda de la facultad.
2. Por carrera: casos, escenarios, software, glosario, herramientas recomendadas y **excluidas**, e **indicaciones por herramienta**.
3. Las herramientas excluidas no se ofrecen ni se pueden encolar.
4. Las indicaciones y el glosario de la carrera llegan al prompt del worker y al chat de ajustes.
5. Los archivos de las 8 facultades quedan creados con su estructura y vacíos: hasta que se llenen, la generación es idéntica a la de hoy.

## No objetivos

- Pantalla de administración o tabla en la base de datos.
- Recuperar la base de conocimiento con documentos oficiales (`kb/archivo/`).
- Escribir el contenido real de cada carrera (casos, glosarios). Lo valida cada facultad.
- Cambiar los workers, el verificador o el revisor.

## Anti-objetivos

- Contenido inventado presentado como oficial de una carrera.
- Que un perfil vacío cambie la generación: con perfiles vacíos, la prueba de equivalencia con la V1 (59 huellas) debe seguir idéntica.
- Que un error de escritura en un YAML se descubra en producción: se valida al arrancar.

## Enfoques considerados

| Enfoque | A favor | En contra |
|---|---|---|
| **A. YAML en `agentes/` (elegido)** | Ya está conectado; se versiona y revisa en git; sin migración | Cambiar el contexto exige desplegar |
| B. Tabla en la base y pantalla de administración | Lo edita cada coordinador sin desplegar | Permisos, pantalla, migración; cambios sin revisión |
| C. Base de conocimiento con documentos oficiales | Contexto rico | Se retiró por decisión del usuario (solo el sílabo); pesada y ruidosa |

## Diseño

### Formato del perfil (`agentes/<facultad>.yaml`)

```yaml
id: salud
facultad: FCSBH                      # sigla en kb/catalogo.yaml
estilo:
  tipos_de_caso: []
  software_habitual: []
  vocabulario: ""                    # ruta a agentes/glosarios/<archivo>.md, o vacío
  escenarios: []
herramientas:
  recomendadas: {clase: [], momento: [], asignatura: []}
  excluidas: []
indicaciones: {}                     # herramienta -> texto
carreras:
  enfermeria:                        # nombre de la carrera en el catálogo (se normaliza)
    tipos_de_caso: []
    escenarios: []
    vocabulario: ""
    herramientas: {recomendadas: {}, excluidas: []}
    indicaciones: {}
```

`herramientas_recomendadas` (formato actual) se sigue leyendo y equivale a `herramientas.recomendadas`.

### Herencia (carrera → facultad → general)

- Listas de estilo y `vocabulario`: la de la carrera reemplaza a la de la facultad si no está vacía (como hoy en `estilo_para`).
- `recomendadas`: por ámbito, la de la carrera reemplaza si no está vacía.
- `excluidas`: unión de facultad y carrera.
- `indicaciones`: por herramienta; la de la carrera gana.

### Validación al cargar (falla al arrancar la API y el worker)

- Claves desconocidas: error.
- Cada id de herramienta (recomendadas, excluidas, indicaciones) debe existir en `DEFINICIONES` o en `HERRAMIENTAS_SIN_IA`.
- Cada carrera debe existir en `kb/catalogo.yaml` bajo la facultad del perfil (comparación normalizada, admite `nombres_alt`).
- `vocabulario`, si no está vacío, debe ser un archivo existente dentro de `agentes/glosarios/`, de hasta 4 000 caracteres.
- Una herramienta no puede estar a la vez recomendada y excluida en la misma carrera.

### Dónde se usa

| Punto | Cambio |
|---|---|
| `agentes/facultades.py` | Nuevo modelo del perfil, herencia y validación; `estilo_para` devuelve también indicaciones y el texto del glosario |
| `recursos/servicio.py` (`catalogo`) | Quita las excluidas y ordena por las recomendadas de la carrera |
| `agentes/orquestador.py` (`crear_trabajos`) | Rechaza una herramienta excluida con un mensaje para el docente |
| `llm/prompts.py` (`_seccion_perfil`) | Agrega «Indicaciones de la carrera para esta herramienta» y el glosario leído; la ruta nunca llega al prompt |
| `chat/ajustes.py` | Usa el mismo estilo de la carrera |
| `agentes/<facultad>.yaml` | Se crean las 7 facultades que faltan, con todas sus carreras y valores vacíos |
| `agentes/glosarios/` | Carpeta con un README que explica el formato |

El enrutamiento sigue igual (`enrutar` por facultad); la carrera se resuelve en cada trabajo con `encargo.carrera`.

### Cosas que deja el diseño al implementador

- **Asignaturas ya importadas con `agente = general`:** al sincronizar, si el enrutamiento da otro perfil, se actualiza `asignatura.agente` aunque la versión del sílabo no cambie (decisión propia, a revisar).
- **Presupuesto de tokens:** las indicaciones y el glosario entran en la sección de perfil; si no cabe, el glosario se recorta antes que la rúbrica (decisión propia).
- Nombres exactos de funciones y modelos Pydantic.

## Pruebas

- Herencia: carrera vacía = facultad; listas, recomendadas, excluidas e indicaciones.
- Validación: cada regla con un YAML inválido.
- Catálogo sin excluidas; `generar` rechaza una excluida.
- Prompt con indicaciones y glosario; sin ellos, idéntico al actual.
- Equivalencia V1: 59 huellas idénticas con los perfiles vacíos.
- Los 8 YAML reales cargan sin errores.
