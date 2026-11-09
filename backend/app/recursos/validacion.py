"""Validación pura de ediciones contra el contexto guardado del trabajo."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agentes.verificador import verificar_ficha, verificar_items
from app.agentes.workers.definiciones import DEFINICIONES
from app.herramientas.esquemas import (
    Ejemplo, FichaAplicacion, FichaConceptual, ItemCuestionario, Opcion,
)
from app.silabo.contexto import ContextoClase


class EdicionInvalida(ValueError):
    """La edición no cumple el contrato estructural o el ámbito del trabajo."""


class _Opcion(Opcion):
    model_config = ConfigDict(strict=True, extra="forbid")


class _Item(ItemCuestionario):
    model_config = ConfigDict(strict=True, extra="forbid")
    # SequenceMatcher compara todos los pares; acotar cada entrada evita
    # amplificación cuadrática de CPU aun dentro del límite global de JSON.
    pregunta: str = Field(min_length=25, max_length=1000)
    opciones: list[_Opcion] = Field(min_length=4, max_length=4)


class _Conceptual(FichaConceptual):
    model_config = ConfigDict(strict=True, extra="forbid")


class _Ejemplo(Ejemplo):
    model_config = ConfigDict(strict=True, extra="forbid")


class _Aplicacion(FichaAplicacion):
    model_config = ConfigDict(strict=True, extra="forbid")
    ejemplo: _Ejemplo


class _Ficha(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    conceptual: _Conceptual
    aplicacion: _Aplicacion


def _ids_original(valor) -> set[str]:
    """El original solo acredita identidad, incluso si requiere revisión."""
    if type(valor) is not list or not 1 <= len(valor) <= 40:
        raise EdicionInvalida
    ids: set[str] = set()
    for item in valor:
        if type(item) is not dict:
            raise EdicionInvalida
        item_id = item.get("item_id")
        if type(item_id) is not str or not item_id.strip() or item_id in ids:
            raise EdicionInvalida
        ids.add(item_id)
    return ids


def _items(valor, contexto: ContextoClase) -> list[_Item]:
    if type(valor) is not list or not 1 <= len(valor) <= 40:
        raise EdicionInvalida
    items = [_Item.model_validate(item) for item in valor]
    ras = {ra.id for ra in contexto.ra}
    contenidos = {" ".join(c.lower().split())
                  for c in (contexto.contenidos or [contexto.momento_titulo])}
    ids = [item.item_id for item in items]
    if len(set(ids)) != len(ids):
        raise EdicionInvalida
    for item in items:
        if (len(item.opciones) != 4 or item.ra not in ras
                or " ".join(item.contenido.lower().split()) not in contenidos):
            raise EdicionInvalida
    return items


def validar_contenido(
    herramienta: str, contenido, original, contexto: ContextoClase,
    asignatura_id: UUID,
) -> tuple[list[dict] | dict, dict[str, list[str]]]:
    """Canoniza la edición y devuelve únicamente comprobaciones deterministas.

    El llamador proporciona el snapshot del trabajo y su asignatura. No se
    consulta el sílabo vigente ni se produce un veredicto de IA.
    """
    try:
        if herramienta in ("cuestionario", "simulacro"):
            anteriores = _ids_original(original)
            items = _items(contenido, contexto)
            if not {i.item_id for i in items} <= anteriores:
                raise EdicionInvalida
            canonico = [item.model_dump(mode="json") for item in items]
            # Sin plan: el docente puede cambiar libremente el nivel.
            fallos = verificar_items(items, [], contexto, [], asignatura_id, asignatura_id)
            return canonico, fallos
        if herramienta == "ficha_clase":
            ficha = _Ficha.model_validate(contenido).model_dump(mode="json")
            return ficha, {"ficha": verificar_ficha(ficha, contexto)}
        definicion = DEFINICIONES.get(herramienta)
        if (definicion is None or definicion.es_quiz or not isinstance(contenido, dict)
                or set(contenido) != set(definicion.secciones)):
            raise EdicionInvalida
        canonico = {s: m.model_validate(contenido[s]).model_dump(mode="json")
                    for s, m in zip(definicion.secciones, definicion.modelos)}
        if herramienta == "estudio_caso" and canonico["caso"]["escenario"] != original["caso"]["escenario"]:
            raise EdicionInvalida  # El escenario lo fija el código (C9).
        return canonico, {definicion.id_revision: definicion.verificar(canonico, contexto)}
    except (ValidationError, EdicionInvalida, TypeError, AttributeError):
        raise EdicionInvalida("El contenido editado no es válido.") from None
