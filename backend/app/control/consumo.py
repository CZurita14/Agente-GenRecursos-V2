"""Consumo de tokens de la IA por proyecto formativo, herramienta y trabajo. Sin texto del contenido."""
from datetime import datetime


def _redondeo(x: float | None, n: int) -> float:
    return round(float(x or 0), n)


def resumen(conn, asignaturas: list, inicio: datetime, fin: datetime, precios: tuple[float, float] | None) -> dict:
    """`asignaturas`: ids a los que la cuenta tiene acceso (ya filtrados). Todo dentro de [inicio, fin)."""
    p = (asignaturas, inicio, fin)
    base = ("from llamada_llm l left join trabajo t on t.id=l.trabajo_id "
            "where l.asignatura_id=any(%s) and l.creado>=%s and l.creado<%s")
    t = conn.execute("select count(*) llamadas, coalesce(sum(l.tokens_entrada),0) tokens_entrada, "
                     "coalesce(sum(l.tokens_salida),0) tokens_salida, coalesce(sum(l.segundos),0) segundos, "
                     "count(*) filter (where not l.ok) fallos " + base, p).fetchone()
    totales = {"llamadas": t["llamadas"], "tokens_entrada": int(t["tokens_entrada"]),
               "tokens_salida": int(t["tokens_salida"]), "segundos": _redondeo(t["segundos"], 1), "fallos": t["fallos"]}
    por_herramienta = []
    for f in conn.execute("select t.herramienta, count(distinct l.trabajo_id) recursos, "
                          "sum(l.tokens_entrada+l.tokens_salida) tokens, "
                          "sum(l.tokens_entrada+l.tokens_salida) filter (where l.rol='revisor') revision "
                          + base + " and coalesce(t.tipo,'generacion')<>'chat' and t.herramienta is not null "
                          "group by 1 order by 3 desc", p):
        tokens = int(f["tokens"])
        por_herramienta.append({"herramienta": f["herramienta"], "recursos": f["recursos"], "tokens": tokens,
                                "por_recurso": round(tokens / f["recursos"]) if f["recursos"] else 0,
                                "parte_revision": _redondeo((f["revision"] or 0) / tokens if tokens else 0, 2)})
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
    costo = None
    if precios is not None:
        costo = round(totales["tokens_entrada"] / 1e6 * precios[0] + totales["tokens_salida"] / 1e6 * precios[1], 4)
    return {"totales": totales, "por_herramienta": por_herramienta,
            "chat": {"pedidos": chat["pedidos"], "tokens": int(chat["tokens"])}, "proyectos": proyectos,
            "recientes": recientes, "costo_usd": costo}
