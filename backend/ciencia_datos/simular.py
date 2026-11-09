"""Comando `simular`: genera sílabos simulados con Qwen y los guarda como JSON de `SilaboUTI`.

Es reanudable: un cupo cuyo JSON ya existe y valida se salta, y uno dañado se regenera. Los
archivos de trabajo (`proyectos.json`, `manifiesto.json`) van fuera de la carpeta de sílabos,
porque el lector recorre subcarpetas y los contaría como rechazados.
Nada de este módulo imprime texto de los sílabos: la consola solo recibe conteos y segundos.
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import openai
from pydantic import ValidationError

from app.agentes.facultades import normalizar
from app.config import Ajustes
from app.llm.cliente import (
    ClienteLLM, ClienteVLLM, ContextoExcedido, ErrorDelServidor, JsonInvalido, ServidorNoDisponible,
)
from app.silabo.modelo import SilaboUTI
from ciencia_datos.sim_esqueleto import crear_esqueleto
from ciencia_datos.sim_plan import RAIZ, Cupo, cupos
from ciencia_datos.sim_redaccion import (
    TEMPERATURA, VERSION_PROMPTS, ProyectoPropuesto, SimulacionInvalida, proponer_proyectos,
    redactar_silabo,
)

CATALOGO = RAIZ / "kb" / "catalogo.yaml"
CARPETA_SILABOS = "silabos_simulados"
CARPETA_TRABAJO = "simulacion"
# Fallos de una sola respuesta: el cupo se descarta y la corrida sigue.
_DESCARTABLES = (JsonInvalido, SimulacionInvalida, ValidationError, ContextoExcedido)
CAIDO, RECHAZO, INESPERADO = "caido", "rechazo", "inesperado"
MENSAJES = {
    CAIDO: "el servidor de IA no está disponible",
    RECHAZO: "el servidor de IA rechazó el pedido: revisa el modelo, la clave y la URL configurados",
    INESPERADO: "error inesperado durante la simulación",
}


def _motivo(error: Exception) -> str:
    """Por qué una excepción detiene la corrida. Nunca se usa su texto."""
    if isinstance(error, ServidorNoDisponible):
        return CAIDO
    if isinstance(error, (ErrorDelServidor, openai.APIStatusError)):
        return RECHAZO
    return INESPERADO


@dataclass(frozen=True)
class Resumen:
    generados: int
    existentes: int
    descartados: int
    segundos: float


class ServidorCaido(ServidorNoDisponible):
    """La corrida se detuvo (servidor caído, pedido rechazado o fallo inesperado).

    Lleva el resumen de lo terminado y el motivo; su mensaje es fijo.
    """

    def __init__(self, resumen: Resumen, motivo: str = CAIDO):
        super().__init__(MENSAJES[motivo])
        self.resumen = resumen
        self.motivo = motivo


def _crear_cliente(ajustes: Ajustes) -> ClienteVLLM:
    return ClienteVLLM(
        base_url=ajustes.llm_base_url, modelo=ajustes.llm_model, timeout_s=ajustes.llm_timeout_s,
        max_concurrencia=ajustes.llm_max_concurrencia, registrar=lambda _llamada: None,
        api_key=ajustes.llm_api_key,
    )


def ruta_silabo(carpeta_silabos: Path, cupo: Cupo) -> Path:
    slug = normalizar(cupo.carrera).replace(" ", "-")
    return carpeta_silabos / cupo.sigla / slug / f"{cupo.codigo}.json"


def _escribir_atomico(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=ruta.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            f.write(contenido)
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise


def _valido(ruta: Path) -> bool:
    try:
        SilaboUTI.model_validate_json(ruta.read_bytes())
    except (OSError, ValueError):  # ValidationError es ValueError
        return False
    return True


def _clave(c: Cupo) -> str:
    return f"{c.sigla}|{c.carrera}"


class _Proyectos:
    """`proyectos.json`: la lista de proyectos de cada carrera, que se reutiliza al repetir."""

    def __init__(self, ruta: Path):
        self._ruta = ruta
        self._candado = threading.Lock()
        try:
            self._datos: dict[str, list[dict]] = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._datos = {}

    def de(self, cupo: Cupo) -> list[ProyectoPropuesto]:
        try:
            return [ProyectoPropuesto(**p) for p in self._datos.get(_clave(cupo), [])]
        except (TypeError, ValidationError):
            return []

    def guardar(self, cupo: Cupo, proyectos: list[ProyectoPropuesto]) -> None:
        with self._candado:
            self._datos[_clave(cupo)] = [p.model_dump() for p in proyectos]
            _escribir_atomico(self._ruta, json.dumps(self._datos, ensure_ascii=False, indent=2))


def _completar_proyectos(cliente: ClienteLLM, cupo: Cupo, total: int,
                         actuales: list[ProyectoPropuesto]) -> list[ProyectoPropuesto]:
    """Pide hasta `total` proyectos; si tras quitar repetidos faltan, pide una vez más lo que falta."""
    lista = list(actuales)
    for _ in range(2):
        faltan = total - len(lista)
        if faltan <= 0:
            break
        vistos = {normalizar(p.nombre) for p in lista}
        for p in proponer_proyectos(cliente, cupo.sigla, cupo.facultad, cupo.carrera, faltan):
            if normalizar(p.nombre) not in vistos:
                vistos.add(normalizar(p.nombre))
                lista.append(p)
    return lista[:total]


def _manifiesto(carpeta_trabajo: Path, modelo: str, semilla: int, r: Resumen) -> None:
    _escribir_atomico(carpeta_trabajo / "manifiesto.json", json.dumps({
        "modelo": modelo, "semilla": semilla, "temperatura": TEMPERATURA,
        "version_prompts": VERSION_PROMPTS, **asdict(r),
    }, ensure_ascii=False, indent=2))


def generar(cliente: ClienteLLM, cupos_a_generar: list[Cupo], carpeta_silabos: Path,
            carpeta_trabajo: Path, hilos: int = 2, semilla: int = 42, *,
            cupos_totales: list[Cupo] | None = None, modelo: str = "") -> Resumen:
    """Genera los sílabos que falten. `cupos_totales` (por defecto, los mismos) fija cuántos
    proyectos se piden por carrera, para que un piloto y la corrida completa usen los mismos.

    Con `ServidorNoDisponible` no se envían cupos nuevos, se guarda lo terminado y se lanza
    `ServidorCaido` con el resumen parcial.
    """
    inicio = time.monotonic()
    totales = cupos_totales if cupos_totales is not None else cupos_a_generar
    por_carrera: dict[str, int] = {}
    for c in totales:
        por_carrera[_clave(c)] = por_carrera.get(_clave(c), 0) + 1
    proyectos = _Proyectos(carpeta_trabajo / "proyectos.json")
    contadores = {"generados": 0, "existentes": 0, "descartados": 0}
    candado = threading.Lock()
    detener = threading.Event()
    motivo_fatal: list[str] = []

    def parar(error: Exception) -> None:
        with candado:
            if not motivo_fatal:
                motivo_fatal.append(_motivo(error))
        detener.set()

    def contar(que: str, n: int = 1) -> None:
        with candado:
            contadores[que] += n

    pendientes = []
    for c in cupos_a_generar:
        if _valido(ruta_silabo(carpeta_silabos, c)):
            contar("existentes")
        else:
            pendientes.append(c)

    # Los proyectos de cada carrera se piden antes de redactar sus cupos.
    asignados: list[tuple[Cupo, ProyectoPropuesto]] = []
    try:
        for clave in dict.fromkeys(_clave(c) for c in pendientes):
            de_la_carrera = [c for c in pendientes if _clave(c) == clave]
            lista = proyectos.de(de_la_carrera[0])
            total = por_carrera.get(clave, max(c.indice for c in de_la_carrera))
            if len(lista) < total:
                try:
                    lista = _completar_proyectos(cliente, de_la_carrera[0], total, lista)
                    proyectos.guardar(de_la_carrera[0], lista)
                except _DESCARTABLES:
                    pass
            for c in de_la_carrera:
                if c.indice <= len(lista):
                    asignados.append((c, lista[c.indice - 1]))
                else:
                    contar("descartados")
    except Exception as error:  # noqa: BLE001 - se clasifica por tipo, sin leer su texto
        parar(error)

    def redactar(par: tuple[Cupo, ProyectoPropuesto]) -> None:
        if detener.is_set():
            return
        cupo, proyecto = par
        try:
            silabo = redactar_silabo(cliente, cupo, proyecto, crear_esqueleto(cupo, semilla))
            _escribir_atomico(ruta_silabo(carpeta_silabos, cupo),
                              silabo.model_dump_json(indent=2))
        except _DESCARTABLES:
            contar("descartados")
        except Exception as error:  # noqa: BLE001 - fatal: no se envían cupos nuevos
            parar(error)
        else:
            contar("generados")

    if not detener.is_set():
        with ThreadPoolExecutor(max_workers=max(1, hilos)) as pool:
            list(pool.map(redactar, asignados))

    resumen = Resumen(**contadores, segundos=round(time.monotonic() - inicio, 1))
    _manifiesto(carpeta_trabajo, modelo, semilla, resumen)
    if detener.is_set():
        raise ServidorCaido(resumen, motivo_fatal[0])
    return resumen


def _imprimir(r: Resumen) -> None:
    print(f"generados={r.generados} existentes={r.existentes} descartados={r.descartados} "
          f"segundos={r.segundos}")


def _entero_desde(minimo: int):
    def convertir(texto: str) -> int:
        valor = int(texto)
        if valor < minimo:
            raise argparse.ArgumentTypeError(f"debe ser al menos {minimo}")
        return valor
    return convertir


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ciencia_datos.simular", description=__doc__)
    p.add_argument("--salida", type=Path, required=True, help="carpeta de datos (p. ej. datos_cd)")
    p.add_argument("--limite", type=_entero_desde(0), default=None, help="solo los primeros N cupos (piloto)")
    p.add_argument("--hilos", type=_entero_desde(1), default=2)
    a = p.parse_args(argv)
    try:
        ajustes = Ajustes().model_copy(update={"llm_max_concurrencia": a.hilos})
    except ValidationError:
        print("configuración inválida: faltan ajustes del servidor de IA o de la base", file=sys.stderr)
        return 2
    todos = cupos(CATALOGO)
    elegidos = todos[:a.limite] if a.limite is not None else todos
    cliente = _crear_cliente(ajustes)
    try:
        r = generar(cliente, elegidos, a.salida / CARPETA_SILABOS, a.salida / CARPETA_TRABAJO,
                    hilos=a.hilos, cupos_totales=todos, modelo=ajustes.llm_model)
    except ServidorCaido as caido:
        _imprimir(caido.resumen)
        print(f"{MENSAJES[caido.motivo]}; lo ya guardado se conserva", file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001 - sin str() ni traceback: podrían traer texto simulado
        print(f"{MENSAJES[INESPERADO]}; lo ya guardado se conserva", file=sys.stderr)
        return 2
    finally:
        cierre = getattr(cliente, "close", None)
        if cierre:
            cierre()
    _imprimir(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
