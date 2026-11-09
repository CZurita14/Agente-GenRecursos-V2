"""P3b T4: simulacro = cuestionario con el contexto del momento (catálogo #11)."""
import pytest
from psycopg.types.json import Jsonb

from app.agentes.coordinador import Coordinador
from app.agentes.facultades import cargar_perfiles
from app.agentes.mensajes import Encargo
from app.agentes.workers import WORKERS, WorkerSimulacro
from app.agentes.workers.definiciones import DEFINICIONES
from app.cola.trabajos import Ambito, encolar, tomar_siguiente
from app.silabo.contexto import contexto_momento
from tests.test_coordinador import RAIZ, WorkerPrueba, cliente_revisor


def test_registro():
    assert isinstance(WORKERS["simulacro"], WorkerSimulacro)
    assert WORKERS["simulacro"].herramienta == "simulacro"
    d = DEFINICIONES["simulacro"]
    assert (d.ambito, d.es_quiz) == ("momento", True)


def _preparar(conn, silabo, cantidad=12):
    ctx = contexto_momento(silabo, "M3")
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('p@uti.edu.ec',%s,%s,'ingenierias',%s) returning id",
                       (ctx.codigo_pf, ctx.version_silabo, Jsonb(silabo.model_dump(mode="json")))).fetchone()["id"]
    encolar(conn, asignatura_id=aid, agente="ingenierias", ambito=Ambito("momento", "M3"),
            herramienta="simulacro", parametros={"cantidad": cantidad})
    t = tomar_siguiente(conn, "w1", 360)
    e = Encargo(trabajo_id=t.id, asignatura_id=aid, codigo_pf=ctx.codigo_pf, version_silabo=ctx.version_silabo,
                carrera=ctx.carrera, nivel=ctx.nivel, ambito=t.ambito, herramienta="simulacro",
                perfil_dificultad="fundamentacion")
    return t, e, ctx


def _coordinador(worker):
    return Coordinador(cargar_perfiles(RAIZ / "agentes")["ingenierias"], {"simulacro": worker}, cliente_revisor())


def test_simulacro_m3(conn, silabo):
    t, e, ctx = _preparar(conn, silabo)
    worker = WorkerPrueba("simulacro")
    cierre = _coordinador(worker).ejecutar(conn, t, e, ctx, lambda: True)
    r = conn.execute("select * from recurso").fetchone()
    assert cierre.estado == "listo" and r["ambito_id"] == "M3" and len(r["contenido"]) == 12
    assert r["evidencia"]["tabla_real"] == dict(receptivo=2, resolutivo=5, reflexivo=4, critico=1)
    assert r["evidencia"]["borrador"] is True  # H8: borrador hasta cumplir 14/16.
    # Los focos del plan salen de las actividades de las cuatro sesiones del momento.
    focos = {p.foco for tarea in worker.tareas for p in tarea.plan}
    assert sum(any(s in f for f in focos) for s in ("M3-S1", "M3-S2", "M3-S3", "M3-S4")) >= 3


def test_simulacro_con_contenido_ajeno_se_marca(conn, silabo):
    t, e, ctx = _preparar(conn, silabo, cantidad=4)

    class Ajeno(WorkerPrueba):
        def generar(self, tarea, cliente):
            entrega = super().generar(tarea, cliente)
            contenido = [dict(i, contenido="DISTRIBUCIONES DE OTRO MOMENTO") for i in entrega.contenido]
            return entrega.model_copy(update={"contenido": contenido})

    assert _coordinador(Ajeno("simulacro")).ejecutar(conn, t, e, ctx, lambda: True).estado == "requiere_revision"
