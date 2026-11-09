"""Prueba real optativa: LLM_REAL=1; usa únicamente el vLLM configurado."""
import json
import os
import time
from pathlib import Path

import httpx
import pytest

from app.agentes.evidencia import PaqueteEvidencia
from app.agentes.facultades import cargar_catalogo, cargar_perfiles
from app.agentes.orquestador import SolicitudGeneracion, crear_asignatura, crear_trabajos, procesar_uno
from app.cola.trabajos import Ambito
from app.config import ajustes
from app.llm.cliente import ClienteVLLM
from worker import registrar_llamada

RAIZ = Path(__file__).resolve().parents[2]


def guardar_traza(conn, destino: Path, resumen: dict, llamadas: list) -> None:
    """Escribe mensajes, recursos y tiempos por llamada; sin prompts ni razonamiento."""
    trabajos = {}
    for t in conn.execute("select id,herramienta,ambito_id,estado from trabajo").fetchall():
        trabajos[str(t["id"])] = {
            "herramienta": t["herramienta"], "clase": t["ambito_id"], "estado": t["estado"],
            "mensajes": [{"tipo": m["tipo"], "cuerpo": m["cuerpo"]} for m in conn.execute(
                "select tipo,cuerpo from mensaje where trabajo_id=%s order by id", (t["id"],)).fetchall()],
        }
    recursos = [{"herramienta": r["herramienta"], "estado": r["estado"], "contenido": r["contenido"],
                 "evidencia": r["evidencia"]}
                for r in conn.execute("select * from recurso order by creado").fetchall()]
    detalle = [{"rol": c["rol"], "trabajo_id": str(c["trabajo_id"]), "segundos": c["segundos"],
                "tokens": [c["tokens_entrada"], c["tokens_salida"]], "ok": c["ok"]} for c in llamadas]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"resumen": resumen, "llamadas": detalle, "trabajos": trabajos,
                                   "recursos": recursos}, ensure_ascii=False, indent=1, default=str),
                       encoding="utf-8")


@pytest.mark.servidor
@pytest.mark.skipif(os.getenv("LLM_REAL") != "1", reason="requiere LLM_REAL=1 y red UTI")
def test_humo_nucleo(silabo, conn, nueva_conexion, record_property):
    config = ajustes()
    try:
        respuesta = httpx.get(config.llm_base_url.rstrip("/") + "/models", timeout=8)
        respuesta.raise_for_status()
    except httpx.HTTPError:
        pytest.skip("servidor de IA no alcanzable desde esta red")
    modelos = respuesta.json()["data"]
    modelo = next((m for m in modelos if m["id"] == config.llm_model), None)
    assert modelo is not None, "el modelo configurado no está servido por vLLM"
    assert modelo.get("max_model_len") == 8192

    perfiles = cargar_perfiles(RAIZ / "agentes")
    aid = crear_asignatura(conn, dueno="humo@uti.edu.ec", silabo=silabo,
                           catalogo=cargar_catalogo(RAIZ / "kb/catalogo.yaml"), perfiles=perfiles)
    for clase, herramienta in (("M3-S4", "cuestionario"), ("M2-S1", "ficha_clase")):
        crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("clase", clase), [herramienta], cantidad=4))

    def registrar(datos):
        c = nueva_conexion()
        try:
            registrar_llamada(c, datos)
        finally:
            c.close()

    inicio = time.monotonic()
    cliente = ClienteVLLM(config.llm_base_url, config.llm_model, config.llm_timeout_s,
                         config.llm_max_concurrencia, registrar, config.llm_api_key)
    try:
        # La prueba no espera 30-600 s de backoff: una espera queda visible como tal.
        for _ in range(2):
            assert procesar_uno(conn, cliente, perfiles, "humo-local", config.lease_s)
    finally:
        cliente.close()
    trabajos = conn.execute("select estado,error from trabajo").fetchall()
    assert all(t["estado"] in ("listo", "requiere_revision") for t in trabajos), trabajos
    recursos = conn.execute("select herramienta,estado,evidencia from recurso order by creado").fetchall()
    assert len(recursos) == 2
    llamadas = conn.execute("select * from llamada_llm").fetchall()
    assert llamadas and all(c["asignatura_id"] == aid and c["trabajo_id"] is not None for c in llamadas)
    assert all(c["tokens_entrada"] + c["tokens_salida"] <= 8192 for c in llamadas)
    segundos = round(time.monotonic() - inicio, 2)
    resumen = {"segundos": segundos, "llamadas": len(llamadas),
               "tokens_entrada": sum(c["tokens_entrada"] for c in llamadas),
               "tokens_salida": sum(c["tokens_salida"] for c in llamadas)}
    record_property("humo", resumen)
    print("HUMO_LOCAL", resumen)
    if destino := os.getenv("HUMO_GUARDAR"):
        # Conserva el diálogo coordinador-worker-revisor antes de que se borre el esquema de prueba.
        guardar_traza(conn, Path(destino), resumen, llamadas)
    for r in recursos:
        e = PaqueteEvidencia.model_validate(r["evidencia"])
        print(r["herramienta"], r["estado"], e.resumen())


@pytest.mark.servidor
@pytest.mark.skipif(os.getenv("LLM_REAL") != "1", reason="requiere LLM_REAL=1 y red UTI")
def test_humo_momento(silabo, conn, nueva_conexion, record_property):
    """P3b: simulacro, guía de la evidencia y estudio de caso de M3, y guía del producto final."""
    config = ajustes()
    perfiles = cargar_perfiles(RAIZ / "agentes")
    aid = crear_asignatura(conn, dueno="humo@uti.edu.ec", silabo=silabo,
                           catalogo=cargar_catalogo(RAIZ / "kb/catalogo.yaml"), perfiles=perfiles)
    crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("momento", "M3"),
                                             ["simulacro", "guia_evidencia", "estudio_caso"], cantidad=4))
    crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("asignatura", "asignatura"), ["guia_producto_final"]))

    def registrar(datos):
        c = nueva_conexion()
        try:
            registrar_llamada(c, datos)
        finally:
            c.close()

    inicio = time.monotonic()
    cliente = ClienteVLLM(config.llm_base_url, config.llm_model, config.llm_timeout_s,
                          config.llm_max_concurrencia, registrar, config.llm_api_key)
    try:
        for _ in range(4):
            assert procesar_uno(conn, cliente, perfiles, "humo-momento", config.lease_s)
    finally:
        cliente.close()
    trabajos = conn.execute("select herramienta,estado from trabajo").fetchall()
    assert all(t["estado"] in ("listo", "requiere_revision") for t in trabajos), trabajos
    llamadas = conn.execute("select * from llamada_llm").fetchall()
    assert all(c["tokens_entrada"] + c["tokens_salida"] <= 8192 for c in llamadas)
    resumen = {"segundos": round(time.monotonic() - inicio, 2), "llamadas": len(llamadas),
               "max_tokens_llamada": max(c["tokens_entrada"] + c["tokens_salida"] for c in llamadas)}
    record_property("humo_momento", resumen)
    print("HUMO_MOMENTO", resumen)
    for r in conn.execute("select herramienta,estado,evidencia from recurso order by creado").fetchall():
        print(r["herramienta"], r["estado"], r["evidencia"]["veredictos"], r["evidencia"]["verificaciones"])
    if destino := os.getenv("HUMO_GUARDAR"):
        guardar_traza(conn, Path(destino), resumen, llamadas)
