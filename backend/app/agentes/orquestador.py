"""Enrutamiento y despacho deterministas; todo razonamiento usa el cliente local."""
import logging
from dataclasses import dataclass
from uuid import UUID

from psycopg.types.json import Jsonb

from app.agentes.coordinador import Coordinador, LeasePerdido
from app.agentes.facultades import enrutar
from app.agentes.mensajes import Encargo
from app.agentes.planificador import PERFILES, perfil_por_nivel
from app.agentes.workers import WORKERS
from app.agentes.workers.definiciones import DEFINICIONES
from app.cola.trabajos import Ambito, encolar, poner_en_espera, renovar_lease, terminar, tomar_siguiente
from app.llm.cliente import JsonInvalido, ServidorNoDisponible
from app.silabo.contexto import contexto_ambito
from app.silabo.modelo import SilaboUTI

registro = logging.getLogger(__name__)
MAX_INTENTOS_RECUPERACION = 5


def crear_asignatura(conn, *, dueno: str, silabo: SilaboUTI, catalogo, perfiles) -> UUID:
    agente = enrutar(silabo.facultad, catalogo, perfiles)
    pf = silabo.proyecto_formativo
    with conn.transaction():
        fila = conn.execute(
            "insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
            "values (%s,%s,%s,%s,%s) on conflict (dueno,codigo_pf) do update set "
            "version_silabo=excluded.version_silabo,agente=excluded.agente,silabo=excluded.silabo returning id",
            (dueno, pf.codigo, pf.version, agente, Jsonb(silabo.model_dump(mode="json"))),
        ).fetchone()
    return fila["id"]


@dataclass(frozen=True)
class SolicitudGeneracion:
    asignatura_id: UUID
    ambito: Ambito
    herramientas: list[str]
    cantidad: int = 12
    instrucciones: str = ""
    perfil_dificultad: str | None = None


def crear_trabajos(conn, solicitud: SolicitudGeneracion) -> list[UUID]:
    if solicitud.perfil_dificultad is not None and solicitud.perfil_dificultad not in PERFILES:
        raise ValueError("perfil de dificultad desconocido")
    if not solicitud.herramientas or any(h not in WORKERS or h not in DEFINICIONES for h in solicitud.herramientas):
        raise ValueError("herramienta desconocida o selección vacía")
    if any(DEFINICIONES[h].ambito != solicitud.ambito.tipo for h in solicitud.herramientas):
        raise ValueError("herramienta de otro ámbito")
    if type(solicitud.cantidad) is not int or not 1 <= solicitud.cantidad <= 40:
        raise ValueError("cantidad debe ser un entero entre 1 y 40")
    if len(set(solicitud.herramientas)) != len(solicitud.herramientas):
        raise ValueError("herramientas duplicadas en la solicitud")
    with conn.transaction():
        asignatura = conn.execute("select * from asignatura where id=%s for share", (solicitud.asignatura_id,)).fetchone()
        if asignatura is None:
            raise ValueError("asignatura inexistente")
        silabo = SilaboUTI.model_validate(asignatura["silabo"])
        contexto = contexto_ambito(silabo, solicitud.ambito)  # Falla antes de encolar si el ámbito no existe.
        for h in solicitud.herramientas:
            # Sin lo que el esquema necesita (rúbrica, sesiones, RA) no se gasta GPU.
            if motivo := DEFINICIONES[h].requisitos(contexto):
                raise ValueError(motivo)
        # El trabajo conserva una instantánea: subir otro sílabo no cambia un trabajo en curso.
        parametros = dict(cantidad=solicitud.cantidad, instrucciones=solicitud.instrucciones,
                          silabo=asignatura["silabo"], version_silabo=asignatura["version_silabo"])
        if solicitud.perfil_dificultad is not None:
            parametros["perfil_dificultad"] = solicitud.perfil_dificultad
        return [encolar(conn, asignatura_id=solicitud.asignatura_id, agente=asignatura["agente"],
                        ambito=solicitud.ambito, herramienta=h, parametros=parametros)
                for h in solicitud.herramientas]


def procesar_uno(conn, cliente, perfiles, worker_id: str, lease_s: int, razonador=None) -> bool:
    trabajo = tomar_siguiente(conn, worker_id, lease_s)
    if trabajo is None:
        return False
    cerco = dict(worker_id=worker_id, lease_version=trabajo.lease_version)
    try:
        if trabajo.intentos >= MAX_INTENTOS_RECUPERACION:
            terminar(conn, trabajo.id, "error", "límite de recuperaciones agotado", **cerco)
            return True
        if trabajo.tipo == 'chat':
            from app.chat.ejecutor import procesar_chat
            procesar_chat(conn, trabajo, cliente, perfiles, worker_id, lease_s)  # El chat no consulta el razonador.
            return True
        silabo = SilaboUTI.model_validate(trabajo.parametros["silabo"])
        ctx = contexto_ambito(silabo, trabajo.ambito)
        encargo = Encargo(
            trabajo_id=trabajo.id, asignatura_id=trabajo.asignatura_id,
            codigo_pf=ctx.codigo_pf, version_silabo=ctx.version_silabo,
            carrera=ctx.carrera, nivel=ctx.nivel, ambito=trabajo.ambito,
            herramienta=trabajo.herramienta, perfil_dificultad=trabajo.parametros.get("perfil_dificultad", perfil_por_nivel(ctx.nivel)),
            instrucciones=trabajo.parametros.get("instrucciones", ""),
        )
        Coordinador(perfiles[trabajo.agente], WORKERS, cliente, razonador=razonador).ejecutar(
            conn, trabajo, encargo, ctx,
            lambda: renovar_lease(conn, trabajo.id, worker_id, lease_s, lease_version=trabajo.lease_version),
        )
    except LeasePerdido:
        registro.info("lease perdido: trabajo_id=%s", trabajo.id)
    except ServidorNoDisponible:
        poner_en_espera(conn, trabajo.id, **cerco)
    except Exception as error:
        # Se conserva solo el tipo en la BD: el texto de una excepción de un SDK
        # puede contener prompts o credenciales. El log tampoco imprime esos cuerpos.
        nombre = type(error).__name__
        detalle = "JSON inválido tras los reintentos" if isinstance(error, JsonInvalido) else f"{nombre}: no se pudo completar el trabajo"
        terminar(conn, trabajo.id, "error", detalle, **cerco)
        registro.error("trabajo_id=%s error=%s", trabajo.id, nombre)
    return True
