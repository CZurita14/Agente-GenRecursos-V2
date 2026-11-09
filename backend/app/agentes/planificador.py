"""Planificador determinista: tabla de especificaciones y lotes (sin IA).

Decide cuántos ítems hay de cada nivel cognitivo (spec §6.2), asigna a cada
ítem un foco tomado de las actividades y contenidos de la clase (§9.3) y
reparte el plan en lotes que caben en el contexto del modelo (§5.3).
No usa aleatoriedad: el mismo contexto produce siempre el mismo plan.
"""
import hashlib
import re
from itertools import zip_longest
from math import gcd
from typing import TYPE_CHECKING

from app.agentes.facultades import PerfilFacultad, estilo_para, normalizar
from app.agentes.mensajes import EstiloFacultad, PlanItem
from app.silabo.contexto import ContextoClase

if TYPE_CHECKING:
    from app.razonador import Razonador

# Orden de niveles de menor a mayor; también es el desempate del mayor resto.
NIVELES = ("receptivo", "resolutivo", "reflexivo", "critico")

# Porcentajes enteros por perfil (suma 100). "Crítico/Cocreativo" se agrupa en `critico`.
PERFILES: dict[str, dict[str, int]] = {
    "fundamentacion": {"receptivo": 20, "resolutivo": 40, "reflexivo": 30, "critico": 10},
    "profesional": {"receptivo": 10, "resolutivo": 30, "reflexivo": 35, "critico": 25},
    "avanzado": {"receptivo": 0, "resolutivo": 20, "reflexivo": 40, "critico": 40},
}
for _nombre, _pct in PERFILES.items():
    assert sum(_pct.values()) == 100, f"el perfil {_nombre} no suma 100"


def perfil_por_nivel(nivel: int, posgrado: bool = False) -> str:
    """Niveles 1-3 fundamentación, 4-7 profesional, 8 o más (o posgrado) avanzado."""
    if posgrado or nivel >= 8:
        return "avanzado"
    if nivel >= 4:
        return "profesional"
    return "fundamentacion"


def tabla_especificaciones(n: int, perfil: str) -> dict[str, int]:
    """Reparte `n` ítems entre los niveles con el método del mayor resto.

    Los porcentajes son enteros, así que no hay errores de coma flotante. Ante restos iguales gana el nivel más bajo (orden de
    `NIVELES`). La suma siempre es `n`.
    """
    if n < 0:
        raise ValueError("n debe ser >= 0")
    if perfil not in PERFILES:
        raise ValueError(f"perfil desconocido: {perfil!r}")
    porcentajes = PERFILES[perfil]
    base = {nv: n * porcentajes[nv] // 100 for nv in NIVELES}
    restos = {nv: n * porcentajes[nv] % 100 for nv in NIVELES}
    faltan = n - sum(base.values())
    # sorted es estable: a igual resto se conserva el orden de NIVELES.
    for nv in sorted(NIVELES, key=lambda x: -restos[x])[:faltan]:
        base[nv] += 1
    return base


def _focos(contexto: ContextoClase) -> list[str]:
    """Actividades y contenidos intercalados (primero actividad)."""
    intercalados = [
        f.strip()
        for par in zip_longest(contexto.actividades, contexto.contenidos)
        for f in par
        if f and f.strip()
    ]
    return intercalados or [contexto.momento_titulo]


def _indice_foco(k: int, n: int, m: int) -> int:
    """Índice del foco del ítem `k` (de `n`) sobre una lista de `m` focos.

    - Si n <= m: se reparten uniformemente por toda la lista, (k*m)//n, de modo
      que aparecen tanto actividades como contenidos.
    - Si n > m: se recorre la lista con un paso coprimo con m (el menor >= 2),
      así ítems consecutivos (del mismo nivel o no) nunca comparten foco y un
      foco no queda siempre atado al mismo nivel.
    """
    if n <= m:
        return (k * m) // n
    paso = next(p for p in range(2, m + 3) if gcd(p, m) == 1)
    return (k * paso) % m


def _palabras(texto: str) -> set[str]:
    return {p for p in re.findall(r"\w+", normalizar(texto)) if len(p) >= 6}


def _casos_libres(escenarios: list[str], entregables: list[str]) -> list[str]:
    """Escenarios que no comparten palabras clave con los entregables (§9.4 regla 1)."""
    vetadas = set().union(*(_palabras(e) for e in entregables)) if entregables else set()
    return [e for e in escenarios if not _palabras(e) & vetadas]


def estilo_razonado(
    perfil: PerfilFacultad, carrera: str, contexto: ContextoClase, razonador: "Razonador | None",
) -> EstiloFacultad:
    """Estilo de la carrera con los casos que el razonador deja libres.

    Sin razonador es `estilo_para`. Con razonador decide solo sobre lo que ya pasó el filtro de
    palabras, así que nunca es menos estricto. Sin casos libres, `escenarios` queda vacío y rige
    lo de siempre: ítems sin caso y `escenario_para` con sus respaldos.
    """
    estilo = estilo_para(perfil, carrera)
    if razonador is None:
        return estilo
    entregables = contexto.entregables_momento
    libres = _casos_libres(list(estilo.escenarios), entregables)
    return estilo.model_copy(update={"escenarios": razonador.casos_libres(libres, entregables)})


def _rotacion_por_tema(focos: list[str], razonador: "Razonador") -> list[str]:
    """Un foco de cada tema antes de repetir; el tema que se agota se salta."""
    temas = razonador.temas(focos)
    rondas = max(map(len, temas), default=0)
    return [focos[tema[r]] for r in range(rondas) for tema in temas if r < len(tema)]


def planificar(
    contexto: ContextoClase, n: int, perfil: str, tam_lote: int = 4,
    escenarios: list[str] = (), razonador: "Razonador | None" = None,
) -> list[list[PlanItem]]:
    """Plan de `n` ítems `i1…in`, de menor a mayor nivel, en lotes de `tam_lote`.

    Los focos salen de las actividades y contenidos de la clase (intercalados,
    actividad primero) y se asignan con `_indice_foco`: dos clases con el mismo
    contenido pero distintas actividades obtienen focos distintos, sin perder
    contenidos en cuestionarios cortos. Es totalmente determinista.

    Con `escenarios`, cada ítem recibe un caso que no se parece a los entregables
    del momento; la rotación arranca en un punto fijo por clase para que dos
    clases no repitan la misma secuencia.

    Con `razonador`, los focos se recorren por tema en lugar de con `_indice_foco`. Los casos no
    pasan por él aquí: `escenarios` ya llega de `estilo_razonado`.
    """
    if tam_lote < 1:
        raise ValueError("tam_lote debe ser >= 1")
    tabla = tabla_especificaciones(n, perfil)
    focos = _focos(contexto)
    if razonador is None:
        asignados = [focos[_indice_foco(k, n, len(focos))] for k in range(n)]
    else:
        rotacion = _rotacion_por_tema(focos, razonador)
        asignados = [rotacion[k % len(rotacion)] for k in range(n)]
    casos = _casos_libres(list(escenarios), contexto.entregables_momento)
    inicio = int(hashlib.sha256(contexto.clase_id.encode()).hexdigest(), 16) % len(casos) if casos else 0
    niveles = [nv for nv in NIVELES for _ in range(tabla[nv])]
    items = [
        PlanItem(item_id=f"i{k + 1}", nivel=nv, foco=asignados[k],
                 caso=casos[(inicio + k) % len(casos)] if casos else "")
        for k, nv in enumerate(niveles)
    ]
    return [items[i : i + tam_lote] for i in range(0, len(items), tam_lote)]
