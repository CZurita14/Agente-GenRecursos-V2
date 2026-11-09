"""Mensajes tipados entre agentes (spec §3.7).

Cada flecha del sistema es un mensaje inmutable, con su `trabajo_id`, guardado en
PostgreSQL: así cada paso es rastreable y un trabajo se reanuda tras una caída.
"""
from typing import Any, Literal, TypeVar
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.cola.trabajos import Ambito
from app.silabo.contexto import ContextoClase
from app.silabo.modelo import BaseInmutable


class EstiloFacultad(BaseInmutable):
    tipos_de_caso: list[str]
    software_habitual: list[str]
    vocabulario: str = ""
    escenarios: list[str] = []  # Casos concretos que el planificador reparte por ítem.


class PlanItem(BaseInmutable):
    item_id: str
    nivel: Literal["receptivo", "resolutivo", "reflexivo", "critico"]
    foco: str
    caso: str = ""  # Escenario asignado por código, distinto del entregable (§9.4).


class Mensaje(BaseInmutable):
    trabajo_id: UUID
    asignatura_id: UUID


class Encargo(Mensaje):
    codigo_pf: str
    version_silabo: str
    carrera: str
    nivel: int
    ambito: Ambito
    herramienta: str
    perfil_dificultad: str
    instrucciones: str = ""


class PlanRazonado(Mensaje):
    """Lo que decidió el razonador; al reanudar manda sobre el modelo instalado, sea cual sea."""
    version: str
    planes: list[list[PlanItem]]
    escenarios: list[str]  # Casos que quedaron libres, para que el estilo no cambie al reanudar.


class Devolucion(Mensaje):
    item_id: str
    motivo: str
    ronda: int


class TareaLote(Mensaje):
    lote: int
    ronda: int
    contexto: ContextoClase
    estilo: EstiloFacultad
    plan: list[PlanItem]
    ya_generado: list[str]
    resultados_calculados: list[str] = []
    devoluciones: list[Devolucion] = []
    instrucciones: str = ""


class EntregaLote(Mensaje):
    lote: int
    ronda: int
    contenido: list[dict[str, Any]]
    tokens: tuple[int, int]


class ResultadoItem(BaseInmutable):
    item_id: str
    fallos_verificacion: list[str]
    revisor: Literal["ok", "devuelto", "sin_veredicto", "no_aplica"]
    motivo: str = ""


class Veredicto(Mensaje):
    resultados: list[ResultadoItem]


class CheckpointRevision(Mensaje):
    """Objetivos aún pendientes de una ronda; se guarda junto a cada corrección."""
    ronda: int
    pendientes: list[str]
    motivos: dict[str, str]


class Cierre(Mensaje):
    recurso_id: UUID
    estado: Literal["listo", "requiere_revision"]
    tokens: tuple[int, int]


_TIPOS: dict[str, type[Mensaje]] = {
    c.__name__: c for c in (Encargo, PlanRazonado, TareaLote, EntregaLote, Devolucion, Veredicto, Cierre,
                            CheckpointRevision)
}
M = TypeVar("M", bound=Mensaje)


def guardar(conn: psycopg.Connection, m: Mensaje) -> None:
    conn.execute(
        "insert into mensaje (trabajo_id, asignatura_id, tipo, cuerpo) values (%s, %s, %s, %s)",
        (m.trabajo_id, m.asignatura_id, type(m).__name__, Jsonb(m.model_dump(mode="json"))),
    )


def leer(conn: psycopg.Connection, trabajo_id: UUID, tipo: type[M] | None = None) -> list[Mensaje]:
    """Mensajes del trabajo en orden de `id`, reconstruidos con su clase."""
    sql = "select tipo, cuerpo from mensaje where trabajo_id = %s"
    params: list[Any] = [trabajo_id]
    if tipo is not None:
        sql += " and tipo = %s"
        params.append(tipo.__name__)
    filas = conn.execute(sql + " order by id", params).fetchall()
    return [_TIPOS[f["tipo"]].model_validate(f["cuerpo"]) for f in filas]
