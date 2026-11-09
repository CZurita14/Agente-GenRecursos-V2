"""P3b T3: el coordinador trabaja con trabajos de momento como con los de clase."""
import pytest
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

from app.agentes.coordinador import Coordinador
from app.agentes.facultades import cargar_perfiles
from app.agentes.mensajes import Encargo, EntregaLote
from app.agentes.workers.definiciones import DEFINICIONES, Definicion
from app.cola.trabajos import Ambito, encolar, tomar_siguiente
from app.silabo.contexto import contexto_momento
from tests.test_coordinador import RAIZ, cliente_revisor


class _Repaso(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str


class WorkerMomento:
    herramienta = "prueba_momento"

    def __init__(self, falla_primero=False):
        self.tareas, self.falla = [], falla_primero

    def generar(self, tarea, cliente):
        self.tareas.append(tarea)
        if self.falla:
            self.falla = False
            raise RuntimeError("caída simulada")
        assert tarea.contexto.clase_id == "M3"
        return EntregaLote(trabajo_id=tarea.trabajo_id, asignatura_id=tarea.asignatura_id, lote=tarea.lote,
                           ronda=tarea.ronda, contenido=[{"texto": f"Repaso lote {tarea.lote}"}], tokens=(5, 5))


@pytest.fixture
def momento(conn, silabo, monkeypatch):
    monkeypatch.setitem(DEFINICIONES, "prueba_momento",
                        Definicion("momento", secciones=("uno", "dos"), modelos=(_Repaso, _Repaso),
                                   verificar=lambda d, c: [], id_revision="prueba"))
    ctx = contexto_momento(silabo, "M3")
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('p@uti.edu.ec',%s,%s,'ingenierias',%s) returning id",
                       (ctx.codigo_pf, ctx.version_silabo, Jsonb(silabo.model_dump(mode="json")))).fetchone()["id"]
    encolar(conn, asignatura_id=aid, agente="ingenierias", ambito=Ambito("momento", "M3"),
            herramienta="prueba_momento", parametros={})
    t = tomar_siguiente(conn, "w1", 360)
    e = Encargo(trabajo_id=t.id, asignatura_id=aid, codigo_pf=ctx.codigo_pf, version_silabo=ctx.version_silabo,
                carrera=ctx.carrera, nivel=ctx.nivel, ambito=t.ambito, herramienta="prueba_momento",
                perfil_dificultad="fundamentacion")
    return t, e, ctx


def _coordinador(worker):
    perfil = cargar_perfiles(RAIZ / "agentes")["ingenierias"]
    return Coordinador(perfil, {"prueba_momento": worker}, cliente_revisor())


def test_trabajo_de_momento_simulado(conn, momento):
    t, e, ctx = momento
    cierre = _coordinador(WorkerMomento()).ejecutar(conn, t, e, ctx, lambda: True)
    r = conn.execute("select * from recurso").fetchone()
    assert cierre.estado == r["estado"] == "listo"
    assert (r["ambito_id"], set(r["contenido"])) == ("M3", {"uno", "dos"})
    assert r["evidencia"]["veredictos"] == {"prueba": "ok"} and r["evidencia"]["borrador"] is False


def test_retoma_trabajo_de_momento(conn, momento):
    t, e, ctx = momento
    with pytest.raises(RuntimeError):
        _coordinador(WorkerMomento(falla_primero=True)).ejecutar(conn, t, e, ctx, lambda: True)
    worker = WorkerMomento()
    assert _coordinador(worker).ejecutar(conn, t, e, ctx, lambda: True).estado == "listo"
    assert [x.lote for x in worker.tareas] == [1, 2]


def test_herramienta_de_otro_ambito_no_se_encola(conn, silabo):
    from app.agentes.orquestador import SolicitudGeneracion, crear_trabajos
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('p@uti.edu.ec','X','1','ingenierias',%s) returning id",
                       (Jsonb(silabo.model_dump(mode="json")),)).fetchone()["id"]
    with pytest.raises(ValueError):
        crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("momento", "M3"), ["cuestionario"]))
    with pytest.raises(KeyError):  # Contrato existente: la API lo traduce a 422.
        crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("clase", "M9-S1"), ["cuestionario"]))


@pytest.mark.parametrize("herramienta, cambio", [
    ("guia_evidencia", {"rubrica": []}), ("repaso_momento", {"sesiones": []}),
    ("estudio_caso", {"ra": []}), ("simulacro", {"ra": []})])
def test_requisitos_del_silabo_antes_de_encolar(conn, silabo, herramienta, cambio):
    # Revisión P3b: sin rúbrica, sesiones o RA el esquema es imposible; no se gasta GPU.
    from app.agentes.orquestador import SolicitudGeneracion, crear_trabajos
    from app.silabo.modelo import SilaboUTI
    datos = silabo.model_dump()
    datos["momentos"][1].update(cambio)
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('p@uti.edu.ec','X','1','ingenierias',%s) returning id",
                       (Jsonb(SilaboUTI.model_validate(datos).model_dump(mode="json")),)).fetchone()["id"]
    with pytest.raises(ValueError):
        crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("momento", "M3"), [herramienta]))
    assert conn.execute("select count(*) n from trabajo").fetchone()["n"] == 0


def test_guia_final_sin_rubrica_final_no_se_encola(conn, silabo):
    from app.agentes.orquestador import SolicitudGeneracion, crear_trabajos
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('p@uti.edu.ec','X','1','ingenierias',%s) returning id",
                       (Jsonb({**silabo.model_dump(mode="json"), "rubrica_producto_final": []}),)).fetchone()["id"]
    with pytest.raises(ValueError):
        crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("asignatura", "asignatura"), ["guia_producto_final"]))
