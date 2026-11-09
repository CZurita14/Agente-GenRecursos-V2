"""Propuestas del coordinador: datos estrictos, nunca órdenes ejecutadas aquí."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, TypeAdapter

TextoRespuesta = Annotated[StrictStr, Field(max_length=2000)]
Identificador = Annotated[StrictStr, Field(max_length=100)]


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Ajustar(_Estricto):
    accion: Literal["ajustar_recurso"]
    mensaje_al_docente: TextoRespuesta
    recurso_id: UUID
    items: Annotated[list[Identificador], Field(max_length=40)]
    rutas: Annotated[
        list[Annotated[list[StrictStr | StrictInt], Field(min_length=1, max_length=12)]],
        Field(max_length=40),
    ]
    instrucciones: Annotated[StrictStr, Field(max_length=2000)]


class Ambito(_Estricto):
    tipo: Literal["clase", "momento", "asignatura"]
    id: StrictStr


class Generar(_Estricto):
    accion: Literal["generar"]
    mensaje_al_docente: TextoRespuesta
    ambito: Ambito
    herramientas: Annotated[list[Identificador], Field(min_length=1, max_length=20)]
    cantidad: Annotated[StrictInt, Field(ge=1, le=40)]
    instrucciones: Annotated[StrictStr, Field(max_length=2000)]


class Aclarar(_Estricto):
    accion: Literal["aclarar"]
    mensaje_al_docente: TextoRespuesta


class FueraDeAlcance(_Estricto):
    accion: Literal["fuera_de_alcance"]
    mensaje_al_docente: TextoRespuesta


Accion = Annotated[Ajustar | Generar | Aclarar | FueraDeAlcance, Field(discriminator="accion")]
_ADAPTADOR = TypeAdapter(Accion)


def validar_accion(datos: dict) -> Accion:
    """Valida el objeto de acción sin envoltorio; rechaza extras y coerciones escalares."""
    return _ADAPTADOR.validate_python(datos)


class SalidaAccion(_Estricto):
    """Objeto raíz compatible con servidores que no admiten una unión en la raíz."""
    accion: Accion
