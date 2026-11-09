"""Verificador determinista (spec §10.1), sin IA.

Revisa cada ítem entregado por un worker y devuelve sus fallos en español. La regla 1
(esquema) ya la garantizan la salida guiada y la validación Pydantic; la regla 8
(autoevaluación idéntica a la rúbrica) llega con su herramienta (P3).
"""
import re
from difflib import SequenceMatcher
from uuid import UUID

from app.agentes.facultades import normalizar
from app.agentes.mensajes import PlanItem
from app.herramientas.esquemas import ItemCuestionario
from app.silabo.contexto import ContextoClase

PROHIBIDAS = re.compile(
    r"\b(todas|ninguna) (de )?las anteriores\b|\btodas son correctas\b|\bninguna es correcta\b", re.I
)
UMBRAL_DUPLICADO = 0.8  # §10.1.6
MIN_PALABRAS_CONTEXTO = 15  # medido en la prueba de calidad v2
NIVELES_CON_CONTEXTO = {"resolutivo", "reflexivo", "critico"}
NIVELES_CON_PASOS = {"reflexivo", "critico"}
TOLERANCIA_DISTRIBUCION = 1  # §10.1.4

OTRA_ASIGNATURA = "entrega de otra asignatura"

# Coherencia entre la clave y las justificaciones: el modelo a veces marca una opción y explica
# como correcta otra. Es una señal, no una prueba: el docente decide.
JUSTIFICA_ERROR = re.compile(
    r"\b(confunde|incorrect[ao]s?|ignora|invierte|sobregeneraliza|es un error)\b", re.I)
JUSTIFICA_ACIERTO = re.compile(
    r"(?<!no )\b(interpreta|identifica|describe|refleja) (correctamente|claramente)\b"
    r"|(?<!no )\bes (la )?(opción |respuesta )?correcta\b", re.I)
PLANTILLA = re.compile(r"\berror que representa\b", re.I)
CLAVE_CONTRADICHA = "la explicación de la respuesta marcada como correcta dice que está equivocada; revisa la clave"
OTRA_PARECE_CLAVE = "la explicación de una opción marcada como incorrecta la presenta como correcta; revisa la clave"
EXPLICACION_PLANTILLA = "las explicaciones son texto de plantilla y no explican la opción"


def _normal(texto: str) -> str:
    return " ".join(texto.lower().split())


def _parecidas(a: str, b: str) -> bool:
    return SequenceMatcher(None, _normal(a), _normal(b)).ratio() >= UMBRAL_DUPLICADO


def fallos_justificacion(correcta: int, justificaciones: list[str]) -> list[str]:
    """Clave que contradice sus propias explicaciones, o explicaciones de plantilla."""
    f = []
    if 0 <= correcta < len(justificaciones) and JUSTIFICA_ERROR.search(justificaciones[correcta]):
        f.append(CLAVE_CONTRADICHA)
    if any(JUSTIFICA_ACIERTO.search(j) for k, j in enumerate(justificaciones) if k != correcta):
        f.append(OTRA_PARECE_CLAVE)
    if any(PLANTILLA.search(j) for j in justificaciones):
        f.append(EXPLICACION_PLANTILLA)
    return f


def revision_claves(contenido) -> dict[str, list[str]]:
    """La misma comprobación sobre un cuestionario ya guardado; los que no lo son no tienen hallazgos."""
    if not isinstance(contenido, list):
        return {}
    salida = {}
    for item in contenido:
        try:
            f = fallos_justificacion(item["correcta"], [str(o.get("justificacion", "")) for o in item["opciones"]])
        except (KeyError, TypeError, AttributeError):
            continue  # Forma no prevista: no hay nada que comprobar.
        if f:
            salida[str(item.get("item_id"))] = f
    return salida


def verificar_items(
    items: list[ItemCuestionario],
    plan: list[PlanItem],
    contexto: ContextoClase,
    previos: list[str],
    asignatura_entrega: UUID,
    asignatura_trabajo: UUID,
) -> dict[str, list[str]]:
    """Fallos por `item_id` (lista vacía si el ítem pasa)."""
    if asignatura_entrega != asignatura_trabajo:  # A7: la entrega se descarta entera
        return {i.item_id: [OTRA_ASIGNATURA] for i in items}

    niveles_plan = {p.item_id: p.nivel for p in plan}
    ras = {r.id for r in contexto.ra}
    contenidos = {_normal(c) for c in contexto.contenidos}
    resultado: dict[str, list[str]] = {}
    vistas: list[str] = []  # preguntas anteriores dentro del lote

    for item in items:
        f: list[str] = []
        textos = [_normal(o.texto) for o in item.opciones]
        if len(item.opciones) != 4 or len(set(textos)) != len(textos):
            f.append("opciones duplicadas o distintas de cuatro")
        if item.ra not in ras:
            f.append(f"el resultado de aprendizaje {item.ra} no es de esta clase")
        if _normal(item.contenido) not in contenidos:
            f.append("el contenido no es de esta clase")
        if item.nivel in NIVELES_CON_CONTEXTO and len(item.contexto.split()) < MIN_PALABRAS_CONTEXTO:
            f.append(f"contexto profesional de menos de {MIN_PALABRAS_CONTEXTO} palabras")
        if item.nivel in NIVELES_CON_PASOS and len([p for p in item.razonamiento if p.strip()]) < 2:
            f.append("menos de dos pasos de razonamiento")
        if any(_parecidas(item.pregunta, otra) for otra in [*vistas, *previos]):
            f.append("enunciado casi duplicado de otro ya generado")
        if any(PROHIBIDAS.search(t) for t in [item.pregunta, *(o.texto for o in item.opciones)]):
            f.append("frase prohibida (todas/ninguna de las anteriores)")
        f.extend(fallos_justificacion(item.correcta, [o.justificacion for o in item.opciones]))
        esperado = niveles_plan.get(item.item_id)
        if esperado is not None and item.nivel != esperado:
            f.append(f"nivel {item.nivel} distinto del planificado ({esperado})")
        resultado[item.item_id] = f
        vistas.append(item.pregunta)
    return resultado


def verificar_distribucion(items: list[ItemCuestionario], tabla: dict[str, int]) -> list[str]:
    """Regla 4: cantidad por nivel dentro de la tabla de especificaciones (±1)."""
    reales = {nivel: 0 for nivel in tabla}
    for item in items:
        reales[item.nivel] = reales.get(item.nivel, 0) + 1
    return [
        f"nivel {nivel}: {reales.get(nivel, 0)} ítems frente a {esperado} planificados"
        for nivel, esperado in tabla.items()
        if abs(reales.get(nivel, 0) - esperado) > TOLERANCIA_DISTRIBUCION
    ]


def _textos(valor) -> list[str]:
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [t for v in valor.values() for t in _textos(v)]
    if isinstance(valor, list):
        return [t for v in valor for t in _textos(v)]
    return []


def verificar_ficha(ficha: dict, contexto: ContextoClase) -> list[str]:
    """Frases prohibidas y campos de texto vacíos en una sección de la ficha."""
    textos = _textos(ficha)
    fallos = []
    if any(not t.strip() for t in textos):
        fallos.append("hay campos vacíos")
    if any(PROHIBIDAS.search(t) for t in textos):
        fallos.append("frase prohibida (todas/ninguna de las anteriores)")
    return fallos


# --- Herramientas de momento y asignatura (P3b) -----------------------------------

def _seccion(datos: dict, nombre: str) -> dict:
    """El coordinador verifica la sección suelta y, al cerrar, el recurso {nombre: sección}."""
    return datos[nombre] if set(datos) == {nombre} else datos


def _tokens(texto: str) -> list[str]:
    """Palabras normalizadas, sin puntuación: una coma no debe ocultar una copia."""
    return re.findall(r"\w+", normalizar(texto))


def _copia(fuentes: list[str], textos: list[str], n: int = 12, minimo: int = 5) -> bool:
    """¿Algún entregable (o 12 palabras seguidas de él) aparece literal en los textos?

    Con entregables cortos basta el entregable entero, si tiene al menos `minimo` palabras.
    """
    resto = " " + " ".join(" ".join(_tokens(t)) for t in textos) + " "
    for fuente in fuentes:
        palabras = _tokens(fuente)
        largo = min(n, len(palabras))
        if largo < minimo:
            continue
        if any(f" {' '.join(palabras[i:i + largo])} " in resto for i in range(len(palabras) - largo + 1)):
            return True
    return False


def _palabras(texto: str) -> set[str]:
    return set(re.findall(r"\w{6,}", normalizar(texto)))


def verificar_repaso(datos: dict, contexto: ContextoClase) -> list[str]:
    d = _seccion(datos, "repaso")
    fallos = verificar_ficha(d, contexto)
    sesiones = {a.split(":", 1)[0] for a in contexto.actividades}
    ids = [s.get("clase_id") for s in d.get("sesiones", [])]
    if any(i not in sesiones for i in ids) or len(ids) != len(set(ids)):
        fallos.append("sesiones ajenas al momento o repetidas")
    return fallos


def verificar_guia_evidencia(datos: dict, contexto: ContextoClase) -> list[str]:
    """§9.4: la guía explica la evidencia, no la resuelve ni la copia fuera de «qué se pide»."""
    d = _seccion(datos, "guia")
    fallos = verificar_ficha(d, contexto)
    indicadores = {f.indicador for f in contexto.rubrica}
    if any(c.get("indicador") not in indicadores for c in d.get("como_se_valora", [])):
        fallos.append("indicador ajeno a la rúbrica del momento")
    if _copia(contexto.entregables_momento, _textos({k: v for k, v in d.items() if k != "que_se_pide"})):
        fallos.append("copia el texto de la evidencia fuera de «qué se pide»")
    return fallos


def verificar_estudio_caso(datos: dict, contexto: ContextoClase) -> list[str]:
    """C9: el escenario lo asigna el código y el caso debe ambientarse en él."""
    d = _seccion(datos, "caso")
    fallos = verificar_ficha({k: v for k, v in d.items() if k != "escenario"}, contexto)
    if d.get("ra") not in {r.id for r in contexto.ra}:
        fallos.append("RA ajeno al momento")
    escenario = _palabras(d.get("escenario", ""))
    if not escenario:
        fallos.append("sin escenario asignado")
    else:
        vetadas = set().union(*(_palabras(e) for e in contexto.entregables_momento)) if contexto.entregables_momento else set()
        if escenario & vetadas:
            fallos.append("el escenario coincide con el de un entregable")
        if not escenario & _palabras(d.get("caso", "")):
            fallos.append("el caso no se ambienta en el escenario asignado")
    return fallos


def verificar_guia_producto_final(datos: dict, contexto: ContextoClase) -> list[str]:
    d = _seccion(datos, "guia_final")
    fallos = verificar_ficha(d, contexto)
    momentos = [a.split(":", 1)[0] for a in contexto.actividades]
    ruta = [p.get("momento") for p in d.get("ruta", [])]
    if sorted(ruta) != sorted(momentos):
        fallos.append("la ruta no tiene un paso por cada momento")
    indicadores = {f.indicador for f in contexto.rubrica}
    if any(c.get("indicador") not in indicadores for c in d.get("criterios", [])):
        fallos.append("indicador ajeno a la rúbrica del producto final")
    if _copia(contexto.entregables_momento, _textos(d)):
        fallos.append("copia el texto del producto final")
    return fallos
