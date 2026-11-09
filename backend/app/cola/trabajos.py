"""Cola durable de trabajos en PostgreSQL: lease por worker y carril por asignatura.

Cada función abre su propia transacción; funciona sobre conexiones autocommit y,
dentro de una transacción externa, como savepoint.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

ACTIVOS = ("generando", "verificando", "revisando")

# Candidatos: pendientes ya disponibles, o activos con lease vencido (worker caído).
# El OR va entre paréntesis antes del NOT EXISTS. El NOT EXISTS descarta la
# asignatura si OTRO trabajo ocupa el carril, con lease vigente o no: un pendiente
# de un carril cuyo activo venció chocaría siempre con trabajo_carril y taparía la
# recuperación de ese activo.
_TOMAR = """
select t.id from trabajo t
where (
    (t.estado in ('en_cola', 'en_espera') and t.disponible_desde <= now())
    or (t.estado in ('generando', 'verificando', 'revisando')
        and coalesce(t.lease_hasta, '-infinity') < now())
  )
  and not exists (
    select 1 from trabajo o
    where o.asignatura_id = t.asignatura_id and o.id <> t.id
      and o.estado in ('generando', 'verificando', 'revisando')
  )
order by t.creado, t.id
limit 1
for update of t skip locked
"""


@dataclass(frozen=True)
class Ambito:
    tipo: Literal["clase", "momento", "asignatura"]
    id: str


@dataclass(frozen=True)
class Trabajo:
    id: UUID
    asignatura_id: UUID
    agente: str
    ambito: Ambito
    herramienta: str
    parametros: dict
    estado: str
    lotes_total: int
    lotes_hechos: int
    rondas_revision: int
    intentos: int
    worker_id: str | None
    lease_hasta: datetime | None
    disponible_desde: datetime
    tokens_entrada: int
    tokens_salida: int
    error: str | None
    creado: datetime
    actualizado: datetime
    lease_version: int
    tipo: str = 'generacion'


def _trabajo(f: dict) -> Trabajo:
    f = dict(f)
    ambito = Ambito(f.pop("ambito_tipo"), f.pop("ambito_id"))
    return Trabajo(ambito=ambito, **f)


def encolar(conn: psycopg.Connection, *, asignatura_id: UUID, agente: str, ambito: Ambito,
            herramienta: str, parametros: dict, tipo: str = 'generacion') -> UUID:
    with conn.transaction():
        f = conn.execute(
            "insert into trabajo (asignatura_id, agente, ambito_tipo, ambito_id, herramienta,"
            " parametros,tipo) values (%s, %s, %s, %s, %s, %s,%s) returning id",
            (asignatura_id, agente, ambito.tipo, ambito.id, herramienta, Jsonb(parametros), tipo),
        ).fetchone()
    return f["id"]


def tomar_siguiente(conn: psycopg.Connection, worker_id: str, lease_s: int) -> Trabajo | None:
    """Toma el trabajo más antiguo disponible y lo pasa a generando con lease nuevo.

    Devuelve None si no hay candidato o si otro worker ganó el carril a la vez
    (UniqueViolation en trabajo_carril). Un trabajo retomado (lease vencido) suma 1
    a `intentos`, reinicia en 'generando' y conserva lotes_hechos, tokens y
    rondas_revision; la política de reanudación es de la Tarea 13.
    """
    try:
        with conn.transaction():
            f = conn.execute(_TOMAR).fetchone()
            if f is None:
                return None
            f = conn.execute(
                "update trabajo set"
                " intentos = intentos + case when estado = any(%s) then 1 else 0 end,"
                " lease_version = lease_version + 1, estado = 'generando', worker_id = %s,"
                " lease_hasta = now() + make_interval(secs => %s), actualizado = now()"
                " where id = %s returning *",
                (list(ACTIVOS), worker_id, lease_s, f["id"]),
            ).fetchone()
    except psycopg.errors.UniqueViolation:
        return None
    return _trabajo(f)


def renovar_lease(conn: psycopg.Connection, trabajo_id: UUID, worker_id: str,
                  lease_s: int, *, lease_version: int | None = None) -> bool:
    """Extiende el lease; False si el trabajo ya no es de este worker o no está activo."""
    with conn.transaction():
        f = conn.execute(
            "update trabajo set lease_hasta = now() + make_interval(secs => %s),"
            " actualizado = now()"
            " where id = %s and worker_id = %s and estado = any(%s) "
            "and lease_hasta > clock_timestamp() and (%s::bigint is null or lease_version=%s) returning id",
            (lease_s, trabajo_id, worker_id, list(ACTIVOS), lease_version, lease_version),
        ).fetchone()
    return f is not None


def _cerco(trabajo_id: UUID, worker_id: str | None, lease_version: int | None = None) -> tuple[str, tuple]:
    """WHERE por id; con worker_id, además exige que siga siendo suyo y activo."""
    if worker_id is None:
        return " where id = %s", (trabajo_id,)
    return (" where id = %s and worker_id = %s and estado = any(%s) "
            "and lease_hasta > clock_timestamp() and (%s::bigint is null or lease_version=%s)",
            (trabajo_id, worker_id, list(ACTIVOS), lease_version, lease_version))


def registrar_avance(conn: psycopg.Connection, trabajo_id: UUID, *, estado: str | None = None,
                     lotes_total: int | None = None, lotes_hechos: int | None = None,
                     rondas_revision: int | None = None, tokens: tuple[int, int] = (0, 0),
                     worker_id: str | None = None, lease_version: int | None = None) -> bool:
    """Actualiza los campos dados (None = sin cambio) y suma los tokens.

    `estado` solo admite estados activos; los finales se fijan con terminar().
    Devuelve True si actualizó el trabajo.
    """
    if estado is not None and estado not in ACTIVOS:
        raise ValueError(f"estado no activo: {estado}")
    donde, args = _cerco(trabajo_id, worker_id, lease_version)
    with conn.transaction():
        cur = conn.execute(
            "update trabajo set estado = coalesce(%s, estado),"
            " lotes_total = coalesce(%s, lotes_total),"
            " lotes_hechos = coalesce(%s, lotes_hechos),"
            " rondas_revision = coalesce(%s, rondas_revision),"
            " tokens_entrada = tokens_entrada + %s, tokens_salida = tokens_salida + %s,"
            " actualizado = now()" + donde,
            (estado, lotes_total, lotes_hechos, rondas_revision, tokens[0], tokens[1], *args),
        )
        return cur.rowcount == 1


def terminar(conn: psycopg.Connection, trabajo_id: UUID,
             estado: Literal["listo", "requiere_revision", "error"],
             error: str | None = None, *, worker_id: str | None = None,
             lease_version: int | None = None) -> bool:
    """Fija el estado final y libera el lease (y con él el carril).

    Con worker_id no toca un trabajo que otro worker ya retomó. True si actualizó.
    """
    donde, args = _cerco(trabajo_id, worker_id, lease_version)
    with conn.transaction():
        cur = conn.execute(
            "update trabajo set estado = %s, error = %s, worker_id = null, lease_hasta = null,"
            " actualizado = now()" + donde,
            (estado, error, *args),
        )
        return cur.rowcount == 1


def poner_en_espera(conn: psycopg.Connection, trabajo_id: UUID, *,
                    worker_id: str | None = None, lease_version: int | None = None) -> datetime | None:
    """Suma un intento, libera el carril y devuelve cuándo vuelve a estar disponible.

    Espera = min(30·2^(intentos−1), 600) s con los intentos ya sumados; en el SET,
    `intentos` es el valor anterior, de ahí 2^intentos. None si no actualizó nada
    (id desconocido o, con worker_id, trabajo que ya no es suyo).
    """
    donde, args = _cerco(trabajo_id, worker_id, lease_version)
    with conn.transaction():
        f = conn.execute(
            "update trabajo set estado = 'en_espera', intentos = intentos + 1,"
            " disponible_desde = now()"
            " + make_interval(secs => least(30 * power(2, intentos), 600)),"
            " worker_id = null, lease_hasta = null, actualizado = now()"
            + donde + " returning disponible_desde",
            args,
        ).fetchone()
    return None if f is None else f["disponible_desde"]


def listar(conn: psycopg.Connection, asignatura_id: UUID) -> list[Trabajo]:
    filas = conn.execute(
        "select * from trabajo where asignatura_id = %s order by creado, id", (asignatura_id,)
    ).fetchall()
    return [_trabajo(f) for f in filas]
