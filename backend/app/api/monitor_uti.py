"""API UTI v1 para el Monitor de Agentes de la UTI (contrato monitor-api-v1.json, versión 1.1.0).

Solo lectura: capacidades, salud y registro de actividad. El Generador no expone pesos ni
entrenamiento desde el monitor (configuration=false, training=false), así que /v1/config,
/v1/config/apply, /v1/training-jobs y /v1/operations no existen.

Acceso: `Authorization: Bearer <token del monitor>`. En la configuración solo vive su SHA-256
(MONITOR_TOKEN_HASH); la sesión de los docentes no sirve aquí y este token no abre nada más.

Privacidad: los eventos salen de las tablas de trabajos y de sincronización, y solo llevan la
herramienta, el ámbito, el estado, duraciones, tokens y rutas de campos. Nunca correos, nombres,
texto del sílabo, contenido de recursos, conversaciones ni razonamiento del modelo.
"""
import base64
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Query, Request

from app.exportar.html import NOMBRES
from app.exportar.presentacion import nombre_ambito

router = APIRouter(prefix="/v1")
INICIO_SERVICIO = datetime.now(timezone.utc)
_EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)
VENTANA_ERRORES = timedelta(minutes=15)

try:  # Métricas del proceso solo si psutil está instalado; si no, se omiten (no se inventan ceros).
    import psutil
    _PROCESO = psutil.Process()
    _PROCESO.cpu_percent(interval=None)  # La primera lectura solo fija el punto de partida.
except Exception:  # noqa: BLE001
    _PROCESO = None


def _autorizar(request: Request) -> str:
    config = request.app.state.config
    if config.monitor_token_hash is None:
        raise HTTPException(503, "El acceso del monitor no está configurado")
    esquema, _, token = request.headers.get("authorization", "").partition(" ")
    calculado = hashlib.sha256(token.strip().encode()).hexdigest()
    if esquema.lower() != "bearer" or not token.strip() or not hmac.compare_digest(
            calculado, config.monitor_token_hash.get_secret_value().strip().lower()):
        raise HTTPException(401, "Token del monitor inválido")
    return config.monitor_agent_id


def _conexion(request: Request):
    conn = request.app.state.conexion()
    conn.autocommit = True
    conn.execute("set statement_timeout to '3s'")
    return closing(conn)


@router.get("/capabilities")
def capacidades(request: Request):
    return {"protocolVersion": "1", "agentId": _autorizar(request), "configuration": False, "training": False,
            "weightRules": {}}


@router.get("/health")
def salud(request: Request):
    _autorizar(request)
    metricas: dict = {}
    if _PROCESO is not None:
        try:
            metricas["cpuPercent"] = round(min(100.0, _PROCESO.cpu_percent(interval=None)), 1)
            metricas["memoryMb"] = round(_PROCESO.memory_info().rss / 2**20, 1)
        except Exception:  # noqa: BLE001
            metricas = {}
    try:
        with _conexion(request) as conn:
            f = conn.execute("select count(*) total, count(*) filter (where not ok) fallos from llamada_llm "
                             "where creado >= now() - %s", (VENTANA_ERRORES,)).fetchone()
    except Exception:  # noqa: BLE001 - sin base de datos el Generador no puede atender
        return {"status": "not_ready", "metrics": metricas}
    estado = "ready"
    if f["total"]:
        metricas["errorRate"] = round(f["fallos"] / f["total"], 4)
        if f["total"] >= 3 and metricas["errorRate"] >= 0.5:
            estado = "degraded"
    return {"status": estado, "metrics": metricas}


# --- eventos -------------------------------------------------------------------------------------

def _cursor(ts: datetime, id_: str) -> str:
    return base64.urlsafe_b64encode(f"{ts.isoformat()}|{id_}".encode()).decode().rstrip("=")


def _leer_cursor(cursor: str | None) -> tuple[datetime, str]:
    if not cursor:
        return _EPOCA, ""
    try:
        crudo = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, _, id_ = crudo.partition("|")
        momento = datetime.fromisoformat(ts)
        if momento.tzinfo is None or not id_:
            raise ValueError
        return momento, id_
    except ValueError:
        raise HTTPException(400, "Cursor inválido") from None


_SQL = """
with eventos as (
  select t.creado ts, 'trabajo:' || t.id || ':solicitado' id, 'solicitado' clase, t.tipo, t.herramienta,
         t.ambito_id, t.estado, null::text error, 0::bigint dur_ms, 0::bigint tokens, t.id::text ejecucion,
         null::jsonb fallos, null::text codigo
    from trabajo t where t.tipo = 'generacion'
  union all
  select t.actualizado, 'trabajo:' || t.id || ':' || t.estado, 'final', t.tipo, t.herramienta, t.ambito_id, t.estado,
         t.error, (extract(epoch from t.actualizado - t.creado) * 1000)::bigint,
         (t.tokens_entrada + t.tokens_salida)::bigint, t.id::text, null, null
    from trabajo t where t.estado in ('listo', 'requiere_revision', 'error')
  union all
  select m.sincronizada, 'silabo:' || md5(m.correo || '|' || m.id_sga) || ':' || (extract(epoch from m.sincronizada) * 1000000)::bigint,
         'silabo', null, null, null, m.estado, null, 0, 0, null, m.fallos, m.codigo_pf
    from materia_sga m where m.estado in ('importada', 'invalida', 'no_disponible')
)
select * from eventos where (ts, id) > (%s, %s) order by ts, id limit %s
"""


def _evento(agente: str, f: dict) -> dict:
    ts, herramienta = f["ts"], NOMBRES.get(f["herramienta"] or "", f["herramienta"])
    base = {"id": f["id"], "agentId": agente, "timestamp": ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}
    if f["clase"] == "silabo":
        fallos = "; ".join(str(x) for x in (f["fallos"] or []))[:1500]
        tipo, estado, sev, msj = {
            "importada": ("silabo.importado", "ok", "info", f"Sílabo de la materia {f['codigo']} importado del SGA."),
            "invalida": ("silabo.invalido", "failed", "warning",
                         f"Sílabo de la materia {f['codigo']} rechazado: {fallos or 'no cumple el contrato'}."),
            "no_disponible": ("silabo.no_disponible", "unavailable", "warning",
                              f"El SGA no entregó el sílabo de la materia {f['codigo']}; se conserva la versión anterior."),
        }[f["estado"]]
        return {**base, "severity": sev, "type": tipo, "status": estado, "message": msj}
    ambito = nombre_ambito(f["ambito_id"]) if f["ambito_id"] else ""
    if f["clase"] == "solicitado":
        return {**base, "severity": "info", "type": "recurso.solicitado", "status": "queued",
                "message": f"Se solicitó {herramienta} ({ambito}).", "executionId": f["ejecucion"]}
    metadata = {"durationMs": int(f["dur_ms"]), "count": int(f["tokens"]), "success": f["estado"] != "error"}
    if f["tipo"] == "chat":
        ok = f["estado"] != "error"
        return {**base, "severity": "info" if ok else "error", "type": "chat.atendido" if ok else "chat.fallido",
                "status": "ok" if ok else "failed", "executionId": f["ejecucion"], "metadata": metadata,
                "message": "Pedido del chat de ajustes atendido." if ok else
                f"Pedido del chat de ajustes fallido: {f['error'] or 'sin detalle'}."}
    tipo, estado, sev, msj = {
        "listo": ("recurso.generado", "ok", "info", f"{herramienta} generado ({ambito})."),
        "requiere_revision": ("recurso.revision_requerida", "needs_review", "warning",
                              f"{herramienta} generado con observaciones del control de calidad ({ambito})."),
        "error": ("recurso.fallido", "failed", "error", f"{herramienta} no se pudo generar ({ambito}): {f['error'] or 'sin detalle'}."),
    }[f["estado"]]
    return {**base, "severity": sev, "type": tipo, "status": estado, "message": msj, "executionId": f["ejecucion"],
            "metadata": metadata}


@router.get("/events")
def eventos(request: Request, limit: int = Query(100, ge=1, le=100), cursor: str | None = None):
    agente = _autorizar(request)
    desde, desde_id = _leer_cursor(cursor)
    with _conexion(request) as conn:
        filas = list(conn.execute(_SQL, (desde, desde_id, limit + 1)))
    inicio = {"ts": INICIO_SERVICIO, "id": f"servicio:{INICIO_SERVICIO.isoformat()}", "clase": "servicio"}
    if (inicio["ts"], inicio["id"]) > (desde, desde_id):
        filas.append(inicio)
        filas.sort(key=lambda f: (f["ts"], f["id"]))
    pagina, hay_mas = filas[:limit], len(filas) > limit
    salida = []
    for f in pagina:
        if f["clase"] == "servicio":
            salida.append({"id": f["id"], "agentId": agente, "severity": "info", "type": "servicio.iniciado", "status": "ok",
                           "timestamp": f["ts"].isoformat().replace("+00:00", "Z"),
                           "message": "Servicio del Generador de Recursos iniciado."})
        else:
            salida.append(_evento(agente, f))
    siguiente = _cursor(pagina[-1]["ts"], pagina[-1]["id"]) if pagina else (cursor or _cursor(_EPOCA, "inicio"))
    return {"agentId": agente, "events": salida, "nextCursor": siguiente, "hasMore": hay_mas}
