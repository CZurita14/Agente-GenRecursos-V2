"""Contexto de una clase: lo que los agentes necesitan saber de una sesión."""
import re
from datetime import date

from app.silabo.modelo import (
    BaseInmutable,
    FilaRubrica,
    Problema,
    ResultadoAprendizaje,
    SilaboUTI,
)


class ContextoClase(BaseInmutable):
    codigo_pf: str
    version_silabo: str
    asignatura: str
    carrera: str
    nivel: int
    clase_id: str
    fecha: date
    momento_titulo: str
    contenidos: list[str]
    actividades: list[str]
    ra: list[ResultadoAprendizaje]
    rubrica: list[FilaRubrica]
    competencia_perfil: str
    problema: Problema
    politica_ia: str
    entregables_momento: list[str]


def contexto_clase(silabo: SilaboUTI, clase_id: str) -> ContextoClase:
    """Extrae el contexto de la sesión `clase_id` (p. ej. "M2-S1").

    Lanza `KeyError` si la clase no existe.
    """
    for momento in silabo.momentos:
        for sesion in momento.sesiones:
            if sesion.id != clase_id:
                continue
            # Las actividades distinguen dos clases con el mismo contenido.
            candidatas = [
                sesion.docente.texto,
                sesion.docente.asincronica.texto if sesion.docente.asincronica else "",
                sesion.practico.texto,
                sesion.autonomo.texto,
            ]
            # La evidencia del momento es un entregable (§9.4) aunque las sesiones no listen ninguno.
            entregables: list[str] = [momento.evidencia] if momento.evidencia.strip() else []
            for s in momento.sesiones:
                for e in s.entregables:
                    if e not in entregables:
                        entregables.append(e)
            pf = silabo.proyecto_formativo
            return ContextoClase(
                codigo_pf=pf.codigo,
                version_silabo=pf.version,
                asignatura=pf.nombre,
                carrera=silabo.carrera,
                nivel=pf.nivel,
                clase_id=sesion.id,
                fecha=sesion.fecha,
                momento_titulo=momento.titulo,
                contenidos=list(sesion.contenidos),
                actividades=[t for t in candidatas if t.strip()],
                ra=[r.model_copy(deep=True) for r in silabo.resultados_aprendizaje if r.id in momento.ra],
                # Copias profundas: `niveles` es un dict y no se comparte con el sílabo.
                rubrica=[f.model_copy(deep=True) for f in momento.rubrica],
                competencia_perfil=silabo.competencia_perfil,
                problema=silabo.problema.model_copy(deep=True),
                politica_ia=momento.politica_ia,
                entregables_momento=entregables,
            )
    raise KeyError(clase_id)


def _base(silabo: SilaboUTI) -> dict:
    pf = silabo.proyecto_formativo
    return {"codigo_pf": pf.codigo, "version_silabo": pf.version, "asignatura": pf.nombre,
            "carrera": silabo.carrera, "nivel": pf.nivel, "competencia_perfil": silabo.competencia_perfil,
            "problema": silabo.problema.model_copy(deep=True)}


def _sin_repetir(textos) -> list[str]:
    return [t for t in dict.fromkeys(t for t in textos if t.strip())]


def contexto_momento(silabo: SilaboUTI, momento_id: str) -> ContextoClase:
    """Contexto del momento `M<n>`: sus sesiones juntas, con su RA, rúbrica y política.

    Mismo contrato que una clase, así el núcleo (prompts, verificador, revisor) sirve
    sin cambios. Lanza `KeyError` si el momento no existe.
    """
    m = re.fullmatch(r"M(\d+)", momento_id)
    momento = next((x for x in silabo.momentos if m and x.numero == int(m.group(1))), None)
    if momento is None:
        raise KeyError(momento_id)
    return ContextoClase(
        **_base(silabo), clase_id=momento_id, fecha=momento.fecha_inicio, momento_titulo=momento.titulo,
        contenidos=_sin_repetir(c for s in momento.sesiones for c in s.contenidos),
        # Una actividad por sesión (con el docente y práctica): el momento se reconoce por lo que se hace.
        actividades=_sin_repetir(f"{s.id}: {s.docente.texto} {s.practico.texto}".strip() for s in momento.sesiones),
        ra=[r.model_copy(deep=True) for r in silabo.resultados_aprendizaje if r.id in momento.ra],
        rubrica=[f.model_copy(deep=True) for f in momento.rubrica],
        politica_ia=momento.politica_ia,
        entregables_momento=_sin_repetir([momento.evidencia] + [e for s in momento.sesiones for e in s.entregables]),
    )


def contexto_asignatura(silabo: SilaboUTI) -> ContextoClase:
    """Contexto de toda la asignatura: rúbrica final y producto final como entregable."""
    return ContextoClase(
        **_base(silabo), clase_id="asignatura", fecha=silabo.periodo.inicio,
        momento_titulo=silabo.proyecto_formativo.nombre,
        # Sin los contenidos de cada sesión: la sección del ámbito nunca se recorta y la guía del
        # producto final (#16) solo necesita los momentos, sus evidencias y la rúbrica final.
        contenidos=[],
        actividades=_sin_repetir(f"M{m.numero}: {m.titulo}" for m in silabo.momentos),
        ra=[r.model_copy(deep=True) for r in silabo.resultados_aprendizaje],
        rubrica=[f.model_copy(deep=True) for f in silabo.rubrica_producto_final],
        politica_ia="; ".join(f"M{m.numero}: {m.politica_ia}" for m in silabo.momentos),
        entregables_momento=_sin_repetir([silabo.problema.producto_final] + [m.evidencia for m in silabo.momentos]),
    )


def contexto_ambito(silabo: SilaboUTI, ambito) -> ContextoClase:
    """Contexto según `ambito.tipo` (clase, momento o asignatura). KeyError si no existe."""
    if ambito.tipo == "clase":
        return contexto_clase(silabo, ambito.id)
    if ambito.tipo == "momento":
        return contexto_momento(silabo, ambito.id)
    if ambito.tipo == "asignatura" and ambito.id == "asignatura":
        return contexto_asignatura(silabo)
    raise KeyError(ambito.id)


def contexto_por_id(silabo: SilaboUTI, ambito_id: str) -> ContextoClase:
    """Contexto a partir del id guardado en el recurso: `asignatura`, `M<n>` o una clase."""
    if ambito_id == "asignatura":
        return contexto_asignatura(silabo)
    if re.fullmatch(r"M\d+", ambito_id):
        return contexto_momento(silabo, ambito_id)
    return contexto_clase(silabo, ambito_id)
