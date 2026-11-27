"""Consumo de tokens de la IA por proyecto formativo, herramienta y trabajo. Sin texto del contenido.

El costo es el que cada llamada guardó al hacerse (tarifa de su modelo, su hora y su caché, como lo
cobra DeepSeek). Las llamadas anteriores a ese registro (modelo nulo) se estiman como entrada sin
caché en horario pico de deepseek-v4-pro, el máximo posible, y se cuentan aparte.
"""
from datetime import datetime

from app.llm import precios

_ESTIMACION = precios.tarifa("deepseek-v4-pro")
# Costo SQL de una fila: el guardado, o la estimación máxima si es anterior al registro de costo.
_COSTO = (f"coalesce(l.costo_usd, case when l.modelo is null then (l.tokens_entrada*{_ESTIMACION[1]} "
          f"+ l.tokens_salida*{_ESTIMACION[2]})/1000000.0 else 0 end)")


def _redondeo(x: float | None, n: int) -> float:
    return round(float(x or 0), n)


def busqueda_web(conn, p) -> dict:
    """Consultas a SearchAPI de la guía de estudio: una consulta es un crédito, también si falló."""
    t = conn.execute("select count(*) creditos, count(*) filter (where not ok) fallidas, coalesce(sum(segundos),0) "
                     "segundos, count(distinct (asignatura_id, momento)) momentos from busqueda_web "
                     "where asignatura_id=any(%s) and creado>=%s and creado<%s", p).fetchone()
    por_momento = [{"codigo_pf": f["codigo_pf"], "nombre": f["nombre"], "momento": f["momento"],
                    "creditos": f["creditos"], "segundos": _redondeo(f["segundos"], 1), "fuentes": f["fuentes"] or 0}
                   for f in conn.execute(
                       "select a.codigo_pf, a.silabo#>>'{proyecto_formativo,nombre}' nombre, b.momento, "
                       "count(*) creditos, sum(b.segundos) segundos, (select jsonb_array_length(m.fuentes) "
                       "from fuente_momento m where m.asignatura_id=b.asignatura_id and m.momento=b.momento) fuentes "
                       "from busqueda_web b join asignatura a on a.id=b.asignatura_id "
                       "where b.asignatura_id=any(%s) and b.creado>=%s and b.creado<%s "
                       "group by a.codigo_pf, a.silabo, b.asignatura_id, b.momento order by 1, 3", p)]
    return {"proveedor": "SearchAPI", "creditos": t["creditos"], "fallidas": t["fallidas"],
            "segundos": _redondeo(t["segundos"], 1), "momentos": t["momentos"], "por_momento": por_momento,
            "saldo": None}


def resumen(conn, asignaturas: list, inicio: datetime, fin: datetime) -> dict:
    """`asignaturas`: ids a los que la cuenta tiene acceso (ya filtrados). Todo dentro de [inicio, fin)."""
    p = (asignaturas, inicio, fin)
    base = ("from llamada_llm l left join trabajo t on t.id=l.trabajo_id "
            "where l.asignatura_id=any(%s) and l.creado>=%s and l.creado<%s")
    t = conn.execute("select count(*) llamadas, coalesce(sum(l.tokens_entrada),0) tokens_entrada, "
                     "coalesce(sum(l.tokens_salida),0) tokens_salida, coalesce(sum(l.segundos),0) segundos, "
                     "count(*) filter (where not l.ok) fallos, coalesce(sum(l.tokens_cache),0) tokens_cache, "
                     f"coalesce(sum({_COSTO}),0) costo, count(*) filter (where l.modelo is null and "
                     "l.tokens_entrada+l.tokens_salida>0) estimadas " + base, p).fetchone()
    totales = {"llamadas": t["llamadas"], "tokens_entrada": int(t["tokens_entrada"]),
               "tokens_salida": int(t["tokens_salida"]), "segundos": _redondeo(t["segundos"], 1), "fallos": t["fallos"],
               "tokens_cache": int(t["tokens_cache"])}
    por_herramienta = []
    for f in conn.execute("select t.herramienta, count(distinct l.trabajo_id) recursos, "
                          "sum(l.tokens_entrada+l.tokens_salida) tokens, coalesce(sum(l.segundos),0) segundos, "
                          "sum(l.tokens_entrada+l.tokens_salida) filter (where l.rol='revisor') revision, "
                          f"sum({_COSTO}) costo "
                          + base + " and coalesce(t.tipo,'generacion')<>'chat' and t.herramienta is not null "
                          "group by 1 order by 3 desc", p):
        tokens = int(f["tokens"])
        por_herramienta.append({"herramienta": f["herramienta"], "recursos": f["recursos"], "tokens": tokens,
                                "por_recurso": round(tokens / f["recursos"]) if f["recursos"] else 0,
                                "parte_revision": _redondeo((f["revision"] or 0) / tokens if tokens else 0, 2),
                                "costo_usd": _redondeo(f["costo"], 4),
                                # Tiempo de IA por recurso (suma de sus llamadas, sin la espera en cola).
                                "segundos_por_recurso": _redondeo(f["segundos"] / f["recursos"] if f["recursos"] else 0, 1)})
    chat = conn.execute("select count(distinct l.trabajo_id) pedidos, coalesce(sum(l.tokens_entrada+l.tokens_salida),0) tokens "
                        + base + " and t.tipo='chat'", p).fetchone()
    proyectos = [{"id": str(f["id"]), "codigo_pf": f["codigo_pf"], "nombre": f["nombre"], "tokens": int(f["tokens"] or 0),
                  "recursos": f["recursos"]}
                 for f in conn.execute(
                     "select a.id, a.codigo_pf, a.silabo#>>'{proyecto_formativo,nombre}' nombre, "
                     "sum(l.tokens_entrada+l.tokens_salida) tokens, "
                     "count(distinct l.trabajo_id) filter (where coalesce(t.tipo,'generacion')<>'chat') recursos "
                     "from asignatura a left join llamada_llm l on l.asignatura_id=a.id and l.creado>=%s and l.creado<%s "
                     "left join trabajo t on t.id=l.trabajo_id where a.id=any(%s) group by a.id order by 4 desc nulls last, 3",
                     (inicio, fin, asignaturas))]
    recientes = [{"herramienta": f["herramienta"], "ambito_id": f["ambito_id"], "estado": f["estado"],
                  "tokens": int(f["tokens_entrada"] + f["tokens_salida"]),
                  "segundos": _redondeo((f["actualizado"] - f["creado"]).total_seconds(), 0), "creado": f["creado"]}
                 for f in conn.execute("select herramienta, ambito_id, estado, tokens_entrada, tokens_salida, creado, actualizado "
                                       "from trabajo where asignatura_id=any(%s) and tipo='generacion' "
                                       "and creado>=%s and creado<%s order by creado desc limit 20", p)]
    return {"totales": totales, "por_herramienta": por_herramienta, "busqueda_web": busqueda_web(conn, p),
            "chat": {"pedidos": chat["pedidos"], "tokens": int(chat["tokens"])}, "proyectos": proyectos,
            "recientes": recientes, "costo_usd": _redondeo(t["costo"], 4),
            "costo_estimado_llamadas": t["estimadas"], "tarifa": {"vigencia": precios.VIGENCIA, "fuente": precios.FUENTE}}
