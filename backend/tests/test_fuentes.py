"""Fuentes de la guía de estudio: SearchAPI (simulado, sin gastar créditos) y bibliografía del sílabo."""
import json


import httpx
from psycopg.types.json import Jsonb
from pydantic import SecretStr

from app.agentes.coordinador import Coordinador
from app.agentes.mensajes import Encargo
from app.agentes.verificador import verificar_guia_estudio
from app.agentes.workers.guia_estudio import WorkerGuiaEstudio
from app.cola.trabajos import Ambito, encolar, tomar_siguiente
from app.config import Ajustes
from app.exportar.presentacion import presentar
from app.fuentes.searchapi import bibliografia_silabo, buscar, consultas, fuentes_momento, texto_fuentes
from app.llm.cliente import ClienteSimulado
from app.recursos.validacion import validar_contenido
from app.silabo.contexto import contexto_momento
from tests.test_momentos import _seccion
from tests.test_workers_momento import PERFIL, _revisor

RESULTADOS = {"organic_results": [
    {"title": "Probabilidad y estadística para ingenieros", "link": "https://books.example.org/walpole",
     "publication": "RE Walpole, RH Myers - 1999 - books.example.org", "snippet": "Texto clásico.", "type": "LIBRO"},
    {"title": "Copia en red social", "link": "https://www.facebook.com/x", "snippet": "no"},
    {"title": "Sin cifrado", "link": "http://inseguro.example.org/a", "snippet": "no"},
    {"title": "Repetido", "link": "https://books.example.org/walpole", "snippet": "duplicado"},
    {"title": "Guía abierta de distribuciones", "link": "https://repositorio.example.edu/guia.pdf",
     "source": "repositorio.example.edu", "date": "2021", "snippet": "PDF abierto."},
]}


def _http(llamadas, estado=200):
    def manejar(request):
        llamadas.append(dict(request.url.params))
        assert request.headers["Authorization"] == "Bearer clave-prueba"
        return httpx.Response(estado, json=RESULTADOS)
    return httpx.Client(transport=httpx.MockTransport(manejar))


def _config(**kw):
    return Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1", llm_model="m", searchapi_key=SecretStr("clave-prueba"), **kw)


def test_consultas_salen_de_los_temas_del_silabo():
    pedidos = consultas(["• Distribuciones estadísticas", "2. Teorema de Bayes", "Muestreo"], "SOFTWARE", 2)
    assert pedidos[0] == ("google_scholar", "Distribuciones estadísticas Teorema de Bayes Muestreo")
    assert pedidos[1][0] == "google" and "software" in pedidos[1][1]
    assert consultas([], "SOFTWARE", 2) == [] and len(consultas(["Tema"], "X", 1)) == 1


def test_buscar_filtra_deduplica_y_numera():
    llamadas = []
    fuentes, gastados, error = buscar("clave-prueba", "https://api.example/search",
                                      [("google_scholar", "tema"), ("google", "tema pdf")], http=_http(llamadas))
    assert gastados == 2 and error is None and [c["engine"] for c in llamadas] == ["google_scholar", "google"]
    assert [f["id"] for f in fuentes] == ["F1", "F2"]
    assert fuentes[0]["enlace"] == "https://books.example.org/walpole" and fuentes[0]["anio"] == "1999"
    assert fuentes[0]["autores"] == "RE Walpole, RH Myers" and fuentes[1]["anio"] == "2021"
    assert not any("facebook" in f["enlace"] or f["enlace"].startswith("http:") for f in fuentes)


def test_un_fallo_no_rompe_la_guia():
    fuentes, gastados, error = buscar("clave-prueba", "https://api.example/search", [("google", "tema")],
                                      http=_http([], estado=500))
    assert fuentes == [] and gastados == 1 and error == "HTTPStatusError"


def _asignatura(conn, silabo):
    ctx = contexto_momento(silabo, "M2")
    return ctx, conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) values "
                             "('p@uti.edu.ec',%s,%s,'ingenierias',%s) returning id",
                             (ctx.codigo_pf, ctx.version_silabo, Jsonb(silabo.model_dump(mode="json")))).fetchone()["id"]


def test_fuentes_se_guardan_por_momento(conn, silabo):
    ctx, aid = _asignatura(conn, silabo)
    llamadas = []
    primera = fuentes_momento(conn, _config(), aid, 2, list(ctx.contenidos), ctx.carrera, http=_http(llamadas))
    segunda = fuentes_momento(conn, _config(), aid, 2, list(ctx.contenidos), ctx.carrera, http=_http(llamadas))
    assert primera == segunda and len(primera) == 2 and len(llamadas) == 2  # La segunda no gasta créditos.
    fila = conn.execute("select creditos,consultas from fuente_momento where asignatura_id=%s", (aid,)).fetchone()
    assert fila["creditos"] == 2 and len(fila["consultas"]) == 2
    sin_clave = Ajustes(_env_file=None, database_url="no-usar", llm_base_url="http://no-usar/v1", llm_model="m")
    assert fuentes_momento(conn, sin_clave, aid, 3, list(ctx.contenidos), ctx.carrera) == []


def _fuentes(silabo):
    web, _, _ = buscar("clave-prueba", "https://api.example/search", [("google_scholar", "tema")], http=_http([]))
    return {"silabo": bibliografia_silabo(silabo) or [{"id": "B1", "tipo": "basica", "texto": "Libro base del sílabo."}],
            "web": web}


def test_guia_cita_fuentes_verificadas_y_trae_bibliografia(conn, silabo):
    ctx, aid = _asignatura(conn, silabo)
    fuentes = _fuentes(silabo)
    encolar(conn, asignatura_id=aid, agente="ingenierias", ambito=Ambito("momento", "M2"),
            herramienta="guia_estudio", parametros={})
    t = tomar_siguiente(conn, "w1", 360)
    e = Encargo(trabajo_id=t.id, asignatura_id=aid, codigo_pf=ctx.codigo_pf, version_silabo=ctx.version_silabo,
                carrera=ctx.carrera, nivel=ctx.nivel, ambito=t.ambito, herramienta="guia_estudio",
                perfil_dificultad="fundamentacion", fuentes=fuentes)
    pedidos = []

    def worker(mensajes):
        pedidos.append(mensajes[-1]["content"])
        n = int(mensajes[-1]["content"].split("Sección ")[1].split(" de 4")[0])
        s = _seccion(n)
        if n == 2:
            s["apartados"][0]["desarrollo"] += " Según la bibliografía básica [B1] y el texto clásico [F1]."
        return json.dumps(s)

    cliente = ClienteSimulado({"worker": worker, "revisor": _revisor()})
    cliente.contexto_max = 1_000_000
    cierre = Coordinador(PERFIL, {"guia_estudio": WorkerGuiaEstudio()}, cliente).ejecutar(conn, t, e, ctx, lambda: True)
    r = conn.execute("select * from recurso").fetchone()
    assert cierre.estado == "listo", json.dumps(r["evidencia"]["verificaciones"])
    assert all("<fuentes>" in p and "[F1]" in p and "no escribas enlaces" in p for p in pedidos)
    assert "https://" not in pedidos[0]  # El modelo no recibe enlaces que pueda copiar mal.
    bib = r["contenido"]["aplicacion"]["bibliografia"]
    assert bib["web"][0]["enlace"] == "https://books.example.org/walpole" and bib["silabo"][0]["id"] == "B1"
    grupo = next(b for b in presentar("guia_estudio", r["contenido"]) if b.get("titulo") == "Bibliografía")
    tabla = next(b for b in grupo["bloques"] if b["tipo"] == "tabla")
    assert tabla["filas"][0][2] == "https://books.example.org/walpole" and tabla["filas"][0][3] == "sí"
    assert tabla["filas"][1][3] == "no"

    # Editar la guía no cambia la bibliografía (los enlaces los pone el sistema).
    editado = json.loads(json.dumps(r["contenido"]))
    editado["aplicacion"]["bibliografia"]["web"][0]["enlace"] = "https://falso.example.com"
    canonico, _ = validar_contenido("guia_estudio", editado, r["contenido"], ctx, aid)
    assert canonico["aplicacion"]["bibliografia"]["web"][0]["enlace"] == "https://books.example.org/walpole"


def test_verificador_de_citas_y_enlaces(silabo):
    ctx = contexto_momento(silabo, "M2")
    completa = {"introduccion": _seccion(1), "desarrollo_1": _seccion(2), "desarrollo_2": _seccion(3),
                "aplicacion": {**_seccion(4), "bibliografia": {"silabo": [{"id": "B1", "tipo": "basica", "texto": "x"}],
                                                               "web": []}}}
    assert "no cita la bibliografía" in " ".join(verificar_guia_estudio(completa, ctx))
    completa["desarrollo_1"]["apartados"][0]["desarrollo"] += " Ver [B1] y [F9]."
    assert "inexistentes: F9" in " ".join(verificar_guia_estudio(completa, ctx))
    seccion = _seccion(3)
    seccion["apartados"][0]["desarrollo"] += " Más en https://sitio.example.com"
    assert "escribe enlaces" in " ".join(verificar_guia_estudio(seccion, ctx))


def test_texto_de_fuentes_sin_enlaces():
    texto = texto_fuentes({"silabo": [{"id": "B1", "tipo": "basica", "texto": "Libro"}],
                           "web": [{"id": "F1", "titulo": "T", "autores": "A", "anio": "2020", "sitio": "s.org",
                                    "fragmento": "r", "enlace": "https://s.org/x"}]})
    assert "[B1]" in texto and "[F1] T (A · 2020 · s.org)" in texto and "https://" not in texto



def test_cada_consulta_queda_medida_con_su_tiempo(conn, silabo):
    from datetime import datetime, timedelta, timezone
    from app.control.consumo import resumen
    ctx, aid = _asignatura(conn, silabo)
    fuentes_momento(conn, _config(), aid, 2, list(ctx.contenidos), ctx.carrera, http=_http([]))
    fuentes_momento(conn, _config(), aid, 3, list(ctx.contenidos), ctx.carrera, http=_http([], estado=500))
    filas = conn.execute("select momento,motor,ok,resultados,segundos from busqueda_web order by id").fetchall()
    assert [(f["momento"], f["ok"]) for f in filas] == [(2, True), (2, True), (3, False), (3, False)]
    assert all(f["segundos"] >= 0 for f in filas) and filas[0]["resultados"] == 5
    ahora = datetime.now(timezone.utc)
    bw = resumen(conn, [aid], ahora - timedelta(days=1), ahora + timedelta(days=1))["busqueda_web"]
    assert bw["creditos"] == 4 and bw["fallidas"] == 2 and bw["momentos"] == 2
    assert [(m["momento"], m["creditos"], m["fuentes"]) for m in bw["por_momento"]] == [(2, 2, 2), (3, 2, 0)]
    # El fallo total no se guarda como fuentes: el próximo intento vuelve a buscar (y se vuelve a medir).
    assert conn.execute("select count(*) n from fuente_momento where momento=3").fetchone()["n"] == 0


def test_la_guia_pide_mas_salida_solo_con_ventana_grande(silabo):
    from uuid import uuid4 as nuevo
    from app.agentes.mensajes import EstiloFacultad, TareaLote
    ctx = contexto_momento(silabo, "M2")
    tarea = TareaLote(trabajo_id=nuevo(), asignatura_id=nuevo(), lote=2, ronda=0, contexto=ctx,
                      estilo=EstiloFacultad(tipos_de_caso=[], software_habitual=[]), plan=[], ya_generado=[])
    for ventana, esperado in ((1_000_000, 9000), (None, 3500)):
        cliente = ClienteSimulado({"worker": lambda m: json.dumps(_seccion(2))})
        if ventana:
            cliente.contexto_max = ventana
        WorkerGuiaEstudio().generar(tarea, cliente)
        assert cliente.llamadas[-1]["max_tokens"] == esperado


def test_la_guia_quita_enlaces_y_espera_mas(silabo):
    from uuid import uuid4 as nuevo
    from app.agentes.mensajes import EstiloFacultad, TareaLote
    ctx = contexto_momento(silabo, "M2")
    tarea = TareaLote(trabajo_id=nuevo(), asignatura_id=nuevo(), lote=2, ronda=0, contexto=ctx,
                      estilo=EstiloFacultad(tipos_de_caso=[], software_habitual=[]), plan=[], ya_generado=[])
    s = _seccion(2)
    s["apartados"][0]["desarrollo"] += " Consulta la documentación (https://ionicframework.com/docs) y www.ejemplo.org/x."
    cliente = ClienteSimulado({"worker": lambda m: json.dumps(s)})
    cliente.contexto_max = 1_000_000
    entrega = WorkerGuiaEstudio().generar(tarea, cliente)
    texto = entrega.contenido[0]["apartados"][0]["desarrollo"]
    assert "http" not in texto and "www." not in texto and texto.endswith("Consulta la documentación y")
    assert cliente.llamadas[-1]["timeout_s"] == 300
    assert verificar_guia_estudio(entrega.contenido[0], ctx) == []
