"""Ventanas fijas persistentes sin almacenar identificadores personales."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import math


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MAX_CONTADOR = 2**31 - 1


class LimiteExcedido(Exception):
    reintentar: int

    def __init__(self, reintentar: int):
        super().__init__("Límite de solicitudes excedido")
        self.reintentar = reintentar


def seudonimo(secreto: bytes, clase: str, valor: str) -> str:
    """HMAC con namespace prefijado por longitud para evitar ambigüedades."""
    namespace = clase.encode("utf-8")
    mensaje = str(len(namespace)).encode("ascii") + b":" + namespace + valor.encode("utf-8")
    return hmac.new(secreto, mensaje, hashlib.sha256).hexdigest()


class ControlLimites:
    """La fábrica entrega una conexión exclusiva, cerrada al terminar el consumo."""

    def __init__(self, conexion, secreto: str, reglas: dict[str, tuple[int, int]], *, ahora=None):
        if not isinstance(secreto, str) or len(secreto) < 32:
            raise ValueError("El secreto necesita al menos 32 caracteres")
        if not isinstance(reglas, dict):
            raise ValueError("Las reglas deben ser un diccionario")
        for regla, parametros in reglas.items():
            if (not isinstance(regla, str) or not regla
                    or not isinstance(parametros, tuple) or len(parametros) != 2
                    or any(type(n) is not int or n <= 0 for n in parametros)
                    or parametros[0] > _MAX_CONTADOR):
                raise ValueError("Regla inválida: cupo y período deben ser enteros positivos; cupo <= INT_MAX")
        if ahora is not None and not callable(ahora):
            raise ValueError("El reloj inyectado debe ser invocable")
        self.conexion = conexion
        self.secreto = secreto.encode("utf-8")
        self.reglas = dict(reglas)
        self.ahora = ahora

    def consumir(self, regla: str, valor: str) -> None:
        if not isinstance(regla, str) or regla not in self.reglas:
            raise ValueError("Regla no permitida")
        cupo, periodo = self.reglas[regla]
        clave = seudonimo(self.secreto, regla, valor)
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            with conn.transaction():
                conn.execute("set local lock_timeout to '2s'")
                if self.ahora is not None:
                    ahora = self.ahora()
                else:
                    ahora = conn.execute("select clock_timestamp() as ahora").fetchone()["ahora"]
                    ahora = ahora.astimezone(timezone.utc)
                # No usar timestamp() flotante: preservar el floor incluso antes de epoch.
                if not isinstance(ahora, type(_EPOCH)) or ahora.utcoffset() != timedelta(0):
                    raise ValueError("El reloj debe devolver un datetime consciente en UTC")
                segundos = (ahora - _EPOCH) // timedelta(seconds=1)
                ventana = _EPOCH + timedelta(seconds=segundos // periodo * periodo)
                vence = ventana + timedelta(seconds=2 * periodo)
                fila = conn.execute(
                    "insert into control_limite as actual (regla,clave,ventana,contador,vence) "
                    "values (%s,%s,%s,1,%s) "
                    "on conflict (regla,clave) do update set "
                    "ventana=excluded.ventana, "
                    "contador=case when actual.ventana < excluded.ventana then 1 "
                    "else actual.contador+1 end, vence=excluded.vence "
                    "where actual.ventana < excluded.ventana or "
                    "(actual.ventana=excluded.ventana and actual.contador < %s) "
                    "returning contador",
                    (regla, clave, ventana, vence, cupo),
                ).fetchone()
                if fila is None:
                    # El UPSERT conserva el lock hasta terminar esta transacción.
                    existente = conn.execute(
                        "select ventana from control_limite where regla=%s and clave=%s",
                        (regla, clave),
                    ).fetchone()["ventana"]
                    reintentar = max(1, math.ceil(
                        (existente + timedelta(seconds=periodo) - ahora).total_seconds()))
                else:
                    reintentar = None
        if reintentar is not None:
            raise LimiteExcedido(reintentar)
