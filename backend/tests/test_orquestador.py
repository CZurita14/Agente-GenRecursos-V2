"""Enrutamiento, reanudación y aislamiento de la ejecución completa."""
import hashlib
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.agentes.facultades import cargar_catalogo, cargar_perfiles
from app.agentes.orquestador import SolicitudGeneracion, crear_asignatura, crear_trabajos, procesar_uno
from app.cola.trabajos import Ambito
from app.llm.cliente import ClienteSimulado, ServidorNoDisponible

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def perfiles():
    return cargar_perfiles(RAIZ / "agentes")


def asignatura(conn, silabo, perfiles, dueno="prueba@uti.edu.ec"):
    return crear_asignatura(conn, dueno=dueno, silabo=silabo,
                            catalogo=cargar_catalogo(RAIZ / "kb/catalogo.yaml"), perfiles=perfiles)


def solicitud(aid, herramientas=None, cantidad=4):
    return SolicitudGeneracion(aid, Ambito("clase", "M2-S1"), herramientas or ["cuestionario"], cantidad)


def cliente_sano(silabos, barrera=None):
    from app.silabo.contexto import contexto_clase
    contextos = {s.proyecto_formativo.codigo: contexto_clase(s, "M2-S1") for s in silabos}
    vistos = set()
    cerrojo = threading.Lock()

    def worker(mensajes):
        texto = mensajes[-1]["content"]
        sello = mensajes[0]["content"].split("\n")[0]
        codigo = re.search(r"Asignatura (.+?) ·", sello)[1]
        ctx = contextos[codigo]
        if barrera:
            with cerrojo:
                primero = codigo not in vistos
                vistos.add(codigo)
            if primero:
                barrera.wait(timeout=15)
        if "Genera" in texto and "ítems" in texto:
            planes = re.findall(r"^- (i\d+) · nivel (\w+) · foco: (.+)$", texto, re.M)
            items = []
            for iid, nivel, foco in planes:
                digest = hashlib.sha256((iid+codigo).encode()).hexdigest()
                items.append(dict(nivel=nivel, ra=ctx.ra[0].id, contenido=ctx.contenidos[0], foco=foco,
                                  contexto=sello + " " + "Caso ficticio de datos de la asignatura para evaluar una decisión fundamentada en evidencia técnica.",
                                  pregunta="¿Cómo interpreta " + " ".join(digest[i:i+5] for i in range(0, 60, 5)) + "?",
                                  opciones=[dict(texto="VALIDA" if k == 0 else f"Error {k}",
                                                 justificacion="j", error_que_representa="e") for k in range(4)],
                                  correcta=0, razonamiento=["paso 1", "paso 2"]))
            return json.dumps({"items": items})
        if "ideas_clave" in texto:
            return json.dumps(dict(ideas_clave=["a", "b", "c"], relacion_ra="RA1", errores_frecuentes=["error"]))
        return json.dumps(dict(ejemplo=dict(enunciado="e", pasos=["p"], resultado="r"), autocomprobacion=["a", "b", "c"]))

    def revisor(mensajes):
        opciones = re.findall(r"^(\d)\) (.+)$", mensajes[-1]["content"], re.M)
        return json.dumps(dict(veredictos=[dict(opcion=int(k), valida="VALIDA" in v, motivo="") for k, v in opciones],
                               resuelve_entregable=False, motivo="", entregable=""))
    return ClienteSimulado(dict(worker=worker, revisor=revisor))


def test_enruta_al_crear(conn, silabo, perfiles):
    aid = asignatura(conn, silabo, perfiles)
    assert conn.execute("select agente from asignatura where id=%s", (aid,)).fetchone()["agente"] == "ingenierias"
    s = silabo.model_copy(update={"facultad": "FACULTAD DE ASTRONOMÍA"})
    assert asignatura(conn, s, perfiles) == aid
    assert conn.execute("select agente from asignatura where id=%s", (aid,)).fetchone()["agente"] == "general"


def test_un_trabajo_por_herramienta(conn, silabo, perfiles):
    aid = asignatura(conn, silabo, perfiles)
    trabajos = crear_trabajos(conn, solicitud(aid, ["cuestionario", "ficha_clase"]))
    assert len(trabajos) == 2
    assert [r["estado"] for r in conn.execute("select estado from trabajo")] == ["en_cola", "en_cola"]


def test_peticion_invalida_no_encola_parcialmente(conn, silabo, perfiles):
    aid = asignatura(conn, silabo, perfiles)
    with pytest.raises(ValueError):
        crear_trabajos(conn, solicitud(aid, ["cuestionario", "inexistente"]))
    assert conn.execute("select count(*) as n from trabajo").fetchone()["n"] == 0


def test_servidor_caido_queda_en_espera(conn, silabo, perfiles):
    aid = asignatura(conn, silabo, perfiles)
    tid = crear_trabajos(conn, solicitud(aid))[0]
    class Caido(ClienteSimulado):
        def contar_tokens(self, mensajes):
            raise ServidorNoDisponible("fuera de red")
    assert procesar_uno(conn, Caido({}), perfiles, "w1", 360)
    f = conn.execute("select estado,intentos from trabajo where id=%s", (tid,)).fetchone()
    assert f == dict(estado="en_espera", intentos=1)
    conn.execute("update trabajo set disponible_desde=now() where id=%s", (tid,))
    assert procesar_uno(conn, cliente_sano([silabo]), perfiles, "w2", 360)
    assert conn.execute("select estado from trabajo where id=%s", (tid,)).fetchone()["estado"] == "listo"


def test_json_invalido_termina_en_error(conn, silabo, perfiles):
    aid = asignatura(conn, silabo, perfiles)
    crear_trabajos(conn, solicitud(aid))
    procesar_uno(conn, ClienteSimulado({"worker": lambda _: "no es JSON"}), perfiles, "w", 360)
    fila = conn.execute("select estado,error from trabajo").fetchone()
    assert fila["estado"] == "error" and "JSON" in fila["error"]


def test_trabajo_conserva_version_del_silabo(conn, silabo, perfiles):
    aid = asignatura(conn, silabo, perfiles)
    crear_trabajos(conn, solicitud(aid))
    cambiado = silabo.model_copy(deep=True)
    cambiado = cambiado.model_copy(update={"proyecto_formativo": cambiado.proyecto_formativo.model_copy(update={"version": "2.0"})})
    asignatura(conn, cambiado, perfiles)
    procesar_uno(conn, cliente_sano([silabo]), perfiles, "w", 360)
    assert conn.execute("select version_silabo from recurso").fetchone()["version_silabo"] == silabo.proyecto_formativo.version


def test_aislamiento_dos_asignaturas(conn, nueva_conexion, silabo, perfiles):
    from worker import registrar_llamada
    otro = silabo.model_copy(deep=True)
    otro = otro.model_copy(update={"proyecto_formativo": otro.proyecto_formativo.model_copy(update={
        "codigo": "B26-TIC-2-11111-2222", "nombre": "Tecnologías de la información"})})
    otro.momentos[0].sesiones[0].contenidos[:] = ["CONTENIDO-EXCLUSIVO-TIC"]
    a, b = [asignatura(conn, s, perfiles, f"docente{k}@uti.edu.ec") for k, s in enumerate([silabo, otro])]
    for aid in (a, b):
        crear_trabajos(conn, solicitud(aid, cantidad=1))
    cliente = cliente_sano([silabo, otro], threading.Barrier(2))
    completar = cliente.completar
    def completar_y_registrar(mensajes, **kw):
        respuesta = completar(mensajes, **kw)
        c = nueva_conexion()
        try:
            registrar_llamada(c, dict(trabajo_id=kw["trabajo_id"], asignatura_id=kw["asignatura_id"],
                                      rol=kw["rol"], tokens_entrada=respuesta.tokens_entrada,
                                      tokens_salida=respuesta.tokens_salida, segundos=0, ok=True))
        finally:
            c.close()
        return respuesta
    cliente.completar = completar_y_registrar
    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros = [pool.submit(procesar_uno, nueva_conexion(), cliente, perfiles, f"w{k}", 360) for k in range(2)]
        assert all(f.result(timeout=40) for f in futuros)
    assert conn.execute("select count(*) as n from recurso").fetchone()["n"] == 2
    registros = conn.execute("select l.asignatura_id, t.asignatura_id as asignatura_trabajo "
                             "from llamada_llm l join trabajo t on t.id=l.trabajo_id").fetchall()
    assert len(registros) == len(cliente.llamadas)
    assert {r["asignatura_id"] for r in registros} == {a, b}
    assert all(r["asignatura_id"] == r["asignatura_trabajo"] for r in registros)
    for aid, ajeno in ((a, otro.proyecto_formativo.codigo), (b, silabo.proyecto_formativo.codigo)):
        for tabla, campo in (("mensaje", "cuerpo"), ("recurso", "contenido")):
            filas = conn.execute(f"select {campo} from {tabla} where asignatura_id=%s", (aid,)).fetchall()
            assert filas and all(ajeno not in json.dumps(f[campo]) for f in filas)
    for llamada in cliente.llamadas:
        codigo = silabo.proyecto_formativo.codigo if llamada["asignatura_id"] == a else otro.proyecto_formativo.codigo
        ajeno = otro.proyecto_formativo.codigo if llamada["asignatura_id"] == a else silabo.proyecto_formativo.codigo
        assert codigo in llamada["mensajes"][0]["content"]
        assert ajeno not in json.dumps(llamada["mensajes"])


def test_cola_vacia(conn, perfiles):
    assert not procesar_uno(conn, ClienteSimulado({}), perfiles, "w", 360)


def test_recuperaciones_agotadas_terminan_trabajo(conn, silabo, perfiles):
    aid = asignatura(conn, silabo, perfiles)
    crear_trabajos(conn, solicitud(aid))
    conn.execute("update trabajo set intentos=5")
    cliente = ClienteSimulado({})
    assert procesar_uno(conn, cliente, perfiles, "w", 360)
    fila = conn.execute("select estado,error from trabajo").fetchone()
    assert fila["estado"] == "error" and "recuperaciones" in fila["error"]
    assert not cliente.llamadas
