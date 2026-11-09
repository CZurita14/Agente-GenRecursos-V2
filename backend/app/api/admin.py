"""Solo métricas agregadas; el rol procede de configuración, nunca del cliente."""
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/admin/consumo")
def consumo(request: Request, desde: date | None = None, hasta: date | None = None):
    if request.state.usuario not in request.app.state.config.administradores:
        raise HTTPException(403, "Solo administradores")
    hasta = hasta or datetime.now(timezone.utc).date()
    if desde is None and hasta < date.min + timedelta(days=6):
        raise HTTPException(422, "Intervalo no válido")
    desde = desde or hasta - timedelta(days=6)
    if hasta < desde or (hasta - desde).days >= 31 or hasta == date.max:
        raise HTTPException(422, "Intervalo máximo de 31 días")
    inicio = datetime.combine(desde, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=timezone.utc)
    with closing(request.app.state.conexion()) as conn:
        conn.autocommit = True
        conn.execute("set statement_timeout to '3s'")
        filas = conn.execute("select case when rol in ('worker','revisor','coordinador') then rol else 'otro' end rol,"
                             "count(*) llamadas,sum(tokens_entrada) tokens_entrada,sum(tokens_salida) tokens_salida,"
                             "sum(segundos) segundos,count(*) filter (where not ok) fallos "
                             "from llamada_llm where creado>=%s and creado<%s group by 1 order by 1", (inicio, fin)).fetchall()
    totales = {k: sum(f[k] for f in filas) for k in ("llamadas", "tokens_entrada", "tokens_salida", "segundos", "fallos")}
    return {"desde": desde, "hasta": hasta, "por_rol": filas, "totales": totales}
