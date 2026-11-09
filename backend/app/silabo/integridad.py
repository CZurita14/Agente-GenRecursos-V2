"""Validación del sílabo que llega del SGA (contrato JSON, docs/api-silabo).

Los fallos son `"<ruta>: <regla>"` con rutas al estilo JSON
(`momentos[0].sesiones[1].id`). Nunca incluyen valores del sílabo.
"""
import re

from pydantic import ValidationError

from app.silabo.modelo import SilaboUTI

_ID_SESION = re.compile(r"^M(\d+)-S(\d+)$")


class SilaboInvalido(ValueError):
    """El sílabo no cumple el contrato; `fallos` lista ruta y regla, sin valores."""

    def __init__(self, fallos: list[str]):
        self.fallos = list(fallos)
        super().__init__("; ".join(self.fallos))


def _ruta(loc: tuple) -> str:
    ruta = ""
    for parte in loc:
        if isinstance(parte, int):
            ruta += f"[{parte}]"
        else:
            ruta += f".{parte}" if ruta else str(parte)
    return ruta or "(raíz)"


def validar_integridad(s: SilaboUTI) -> list[str]:
    """Reglas entre campos; acumula todos los fallos."""
    fallos: list[str] = []
    ras = {r.id for r in s.resultados_aprendizaje}
    numeros: set[int] = set()
    ids: set[str] = set()
    for i, m in enumerate(s.momentos):
        base = f"momentos[{i}]"
        if m.numero in numeros:
            fallos.append(f"{base}.numero: repetido")
        numeros.add(m.numero)
        for j, ra in enumerate(m.ra):
            if ra not in ras:
                fallos.append(f"{base}.ra[{j}]: resultado de aprendizaje inexistente")
        if not m.sesiones:
            fallos.append(f"{base}.sesiones: vacío")
        for j, se in enumerate(m.sesiones):
            sb = f"{base}.sesiones[{j}]"
            coincide = _ID_SESION.match(se.id)
            if not coincide or int(coincide.group(1)) != m.numero:
                fallos.append(f"{sb}.id: debe ser M<momento>-S<n>")
            if se.id in ids:
                fallos.append(f"{sb}.id: repetido")
            ids.add(se.id)
            if not s.periodo.inicio <= se.fecha <= s.periodo.fin:
                fallos.append(f"{sb}.fecha: fuera del periodo")
            for k, c in enumerate(se.contenidos):
                if not c.strip():
                    fallos.append(f"{sb}.contenidos[{k}]: vacío")
    return fallos


def cargar_silabo(datos: dict) -> SilaboUTI:
    """Valida con Pydantic y luego la integridad; lanza `SilaboInvalido`."""
    try:
        s = SilaboUTI.model_validate(datos)
    except ValidationError as e:
        raise SilaboInvalido(
            [f"{_ruta(err['loc'])}: {err['type']}" for err in e.errors()]
        ) from None
    fallos = validar_integridad(s)
    if fallos:
        raise SilaboInvalido(fallos)
    return s
