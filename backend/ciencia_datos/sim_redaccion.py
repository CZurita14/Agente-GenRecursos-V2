"""Redacción por etapas y ensamblado de sílabos simulados.

Qwen redacta solo textos; la estructura (ids, RA por momento, fechas, horas, numeración)
la pone el código a partir del esqueleto. Cada sílabo cuesta 5 llamadas: una general y una
por momento. Los prompts solo reciben facultad, carrera, nombre y nivel del proyecto y
conteos: nunca texto de sílabos reales. Nada de este módulo imprime texto del sílabo, y
`SimulacionInvalida` nunca lo lleva en el mensaje.
"""
from datetime import date

from pydantic import BaseModel, Field, ValidationError

from app.agentes.facultades import normalizar
from app.llm.cliente import ClienteLLM
from app.llm.json import pedir_json
from app.silabo.modelo import (
    Actividad, ActividadDocente, FilaRubrica, HorasPF, Momento, Pis, Problema,
    ProyectoFormativo, ResultadoAprendizaje, Sesion, SilaboUTI,
)
from ciencia_datos.corpus import fragmentos, tiene_datos_personales
from ciencia_datos.sim_esqueleto import N_MOMENTOS, Esqueleto
from ciencia_datos.sim_plan import Cupo

VERSION_PROMPTS = "2"
TEMPERATURA = 0.7
SALIDA_MAX = 3500
MINIMO_FRAGMENTOS = 20
APROBADO = date(2026, 1, 15)
VERSION_SILABO = "SIM"
MODALIDAD = "Presencial"
HORAS_POR_CREDITO = 48


class SimulacionInvalida(Exception):
    """El sílabo redactado no sirve. El mensaje nunca lleva texto del sílabo."""


# --- Modelos de salida de Qwen ------------------------------------------------------------

class Niveles(BaseModel):
    """Una clave por nivel de la rúbrica; el esquema guiado las exige todas."""
    receptivo: str
    resolutivo: str
    reflexivo: str
    critico: str
    cocreativo: str


class FilaRedactada(BaseModel):
    indicador: str
    niveles: Niveles


class ResultadoRedactado(BaseModel):
    texto: str
    evidencia: str


class ProblemaRedactado(BaseModel):
    descripcion: str
    reto: str
    producto_final: str


class PisRedactado(BaseModel):
    nombre: str
    aporte: str


class ProyectoPropuesto(BaseModel):
    nombre: str = Field(min_length=1)
    nivel: int = Field(ge=1, le=8)


class ProyectosPropuestos(BaseModel):
    proyectos: list[ProyectoPropuesto]


class GeneralRedactado(BaseModel):
    competencia_perfil: str
    competencia_pf: str
    metacompetencia: str
    resultados: list[ResultadoRedactado]
    problema: ProblemaRedactado
    pis: PisRedactado
    metodologias: list[str]
    titulos_momentos: list[str]
    rubrica_producto_final: list[FilaRedactada]


class SesionRedactada(BaseModel):
    contenidos: list[str]
    docente: str
    practico: str
    autonomo: str
    entregables: list[str]


class MomentoRedactado(BaseModel):
    evidencia: str
    recursos: str
    politica_ia: str
    rubrica: list[FilaRedactada]
    sesiones: list[SesionRedactada]


# --- Prompts ------------------------------------------------------------------------------

_REGLAS = (
    "Escribe en español. El sílabo es ficticio y sirve solo para pruebas: no menciones personas, "
    "instituciones reales, correos, teléfonos, cédulas ni citas bibliográficas, y no copies texto "
    "de ningún documento real. No uses títulos ni nombres propios de personas. "
    "Responde solo con el objeto JSON pedido."
)


def _mensajes(instruccion: str) -> list[dict]:
    return [{"role": "system", "content": _REGLAS}, {"role": "user", "content": instruccion}]


def _fijar(campo: dict, minimo: int, maximo: int | None = None) -> None:
    """Fija el tamaño de una lista en el esquema (el modelo de validación no cambia)."""
    campo.update(minItems=minimo, maxItems=minimo if maximo is None else maximo)


def _pedir(cliente: ClienteLLM, instruccion: str, modelo: type[BaseModel], rol: str,
           esquema: dict | None = None):
    salida, _ = pedir_json(
        cliente, _mensajes(instruccion), modelo, esquema or modelo.model_json_schema(),
        rol=rol, temperatura=TEMPERATURA, max_tokens=SALIDA_MAX, pensar=False,
    )
    return salida


def proponer_proyectos(cliente: ClienteLLM, sigla: str, facultad: str, carrera: str,
                       n: int) -> list[ProyectoPropuesto]:
    """Hasta `n` proyectos formativos distintos para la carrera, en el orden propuesto."""
    instruccion = (
        f"Propón {n} nombres de proyectos formativos distintos y realistas para la carrera "
        f"de {carrera}, de la facultad {facultad} ({sigla}). Cada uno lleva su nombre y su nivel "
        "de la carrera, un entero de 1 a 8. Los nombres describen un producto o problema "
        "concreto de la carrera, sin repetirse."
    )
    propuesta = _pedir(cliente, instruccion, ProyectosPropuestos, "sim_proyectos")
    vistos: set[str] = set()
    salida: list[ProyectoPropuesto] = []
    for p in propuesta.proyectos:
        clave = normalizar(p.nombre)
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(p)
    return salida[:n]


def _contexto(cupo: Cupo, proyecto: ProyectoPropuesto) -> str:
    return (f"Facultad: {cupo.facultad}. Carrera: {cupo.carrera}. "
            f"Proyecto formativo: {proyecto.nombre} (nivel {proyecto.nivel} de 8).")


def _niveles_de_la_rubrica() -> str:
    return "receptivo, resolutivo, reflexivo, critico y cocreativo"


def _pedir_general(cliente: ClienteLLM, cupo: Cupo, proyecto: ProyectoPropuesto,
                   esq: Esqueleto) -> GeneralRedactado:
    instruccion = (
        f"Redacta la parte general de un sílabo ficticio por proyectos formativos. "
        f"{_contexto(cupo, proyecto)} "
        f"Entrega exactamente: {esq.n_resultados} resultados de aprendizaje, cada uno con su evidencia; "
        f"{esq.n_metodologias} metodologías; {N_MOMENTOS} títulos de momentos, en orden; "
        f"{esq.n_filas_rubrica_pf} filas de rúbrica del producto final, con un indicador y un texto "
        f"para cada nivel ({_niveles_de_la_rubrica()}). Incluye la competencia del perfil, la "
        "competencia del proyecto formativo, la metacompetencia, el problema (descripción, reto y "
        "producto final) y el proyecto integrador (nombre y aporte)."
    )
    esquema = GeneralRedactado.model_json_schema()
    campos = esquema["properties"]
    _fijar(campos["resultados"], esq.n_resultados)
    _fijar(campos["metodologias"], esq.n_metodologias)
    _fijar(campos["titulos_momentos"], N_MOMENTOS)
    _fijar(campos["rubrica_producto_final"], esq.n_filas_rubrica_pf)
    return _pedir(cliente, instruccion, GeneralRedactado, "sim_general", esquema)


def _pedir_momento(cliente: ClienteLLM, cupo: Cupo, proyecto: ProyectoPropuesto, esq: Esqueleto,
                   general: GeneralRedactado, indice: int) -> MomentoRedactado:
    n_sesiones = len(esq.momentos[indice].sesiones)
    resultados = "; ".join(f"RA{i}: {r.texto}" for i, r in enumerate(general.resultados[:esq.n_resultados], 1))
    titulo = general.titulos_momentos[indice]
    instruccion = (
        f"Redacta el momento {indice + 1} de {N_MOMENTOS} de un sílabo ficticio por proyectos "
        f"formativos. {_contexto(cupo, proyecto)} Título del momento: {titulo}. "
        f"Problema: {general.problema.descripcion} Reto: {general.problema.reto} "
        f"Resultados de aprendizaje: {resultados}. "
        f"Entrega exactamente: la evidencia del momento, los recursos y la política de uso de IA; "
        f"{esq.n_filas_rubrica} filas de rúbrica, con un indicador y un texto para cada nivel "
        f"({_niveles_de_la_rubrica()}); y {n_sesiones} sesiones. Cada sesión lleva "
        f"{esq.contenidos_por_sesion} contenidos, un texto de actividad docente, uno de actividad "
        "práctica y uno de trabajo autónomo, y sus entregables."
    )
    esquema = MomentoRedactado.model_json_schema()
    campos = esquema["properties"]
    _fijar(campos["rubrica"], esq.n_filas_rubrica)
    _fijar(campos["sesiones"], n_sesiones)
    # Los contenidos por sesión son uniformes en el esqueleto; si variaran, mínimo y máximo del momento.
    _fijar(esquema["$defs"]["SesionRedactada"]["properties"]["contenidos"],
           esq.contenidos_por_sesion, esq.contenidos_por_sesion)
    return _pedir(cliente, instruccion, MomentoRedactado, "sim_momento", esquema)


# --- Ensamblado ---------------------------------------------------------------------------

def _uoc(nivel: int) -> str:
    if nivel <= 3:
        return "Básica"
    return "Profesional" if nivel <= 6 else "Integración curricular"


def _exigir(lista: list, n: int, que: str) -> list:
    """Recorta lo que sobra; con menos de `n` elementos, el sílabo no sirve."""
    if len(lista) < n:
        raise SimulacionInvalida(f"{que}: se esperaban {n} elementos y llegaron {len(lista)}")
    return lista[:n]


def _fila(f: FilaRedactada) -> FilaRubrica:
    return FilaRubrica(indicador=f.indicador, niveles=f.niveles.model_dump())


def _cadenas(valor):
    """Todas las cadenas de una estructura anidada."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _cadenas(v)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            yield from _cadenas(v)


def _ra_del_momento(indice: int, ids: list[str]) -> list[str]:
    """Dos resultados por momento, en rotación: así todos aparecen al menos una vez."""
    n = len(ids)
    return list(dict.fromkeys([ids[indice % n], ids[(indice + 1) % n]]))


def _momento(esq: Esqueleto, indice: int, titulo: str, ids: list[str],
             red: MomentoRedactado) -> Momento:
    base = esq.momentos[indice]
    sesiones_red = _exigir(red.sesiones, len(base.sesiones), f"sesiones del momento {indice + 1}")
    sesiones = []
    for b, s in zip(base.sesiones, sesiones_red):
        sesiones.append(Sesion(
            id=b.id, numero=b.numero, fecha=b.fecha, semana_periodo=b.semana_periodo,
            docente=ActividadDocente(texto=s.docente, horas=b.horas_docente),
            practico=Actividad(texto=s.practico, horas=b.horas_practico),
            autonomo=Actividad(texto=s.autonomo, horas=b.horas_autonomo),
            contenidos=_exigir(s.contenidos, esq.contenidos_por_sesion,
                               f"contenidos del momento {indice + 1}"),
            entregables=s.entregables,
        ))
    return Momento(
        numero=base.numero, titulo=titulo, fecha_inicio=base.fecha_inicio, fecha_fin=base.fecha_fin,
        ra=_ra_del_momento(indice, ids), evidencia=red.evidencia, recursos=red.recursos,
        politica_ia=red.politica_ia,
        rubrica=[_fila(f) for f in _exigir(red.rubrica, esq.n_filas_rubrica,
                                           f"rúbrica del momento {indice + 1}")],
        sesiones=sesiones,
    )


def _ensamblar(cupo: Cupo, proyecto: ProyectoPropuesto, esq: Esqueleto, general: GeneralRedactado,
               momentos: list[MomentoRedactado]) -> SilaboUTI:
    resultados = _exigir(general.resultados, esq.n_resultados, "resultados de aprendizaje")
    ids = [f"RA{i}" for i in range(1, len(resultados) + 1)]
    titulos = _exigir(general.titulos_momentos, N_MOMENTOS, "títulos de momentos")
    contacto = practico = esq.horas_total // 3
    horas = HorasPF(total=esq.horas_total, contacto=contacto, practico=practico,
                    autonomo=esq.horas_total - contacto - practico)
    return SilaboUTI(
        facultad=cupo.facultad, carrera=cupo.carrera, periodo=esq.periodo,
        proyecto_formativo=ProyectoFormativo(
            nombre=proyecto.nombre, codigo=esq.codigo, version=VERSION_SILABO, aprobado=APROBADO,
            uoc=_uoc(proyecto.nivel), nivel=proyecto.nivel, modalidad=MODALIDAD,
            creditos=esq.horas_total / HORAS_POR_CREDITO, horas=horas, horario=[],
        ),
        competencia_perfil=general.competencia_perfil, competencia_pf=general.competencia_pf,
        metacompetencia=general.metacompetencia,
        resultados_aprendizaje=[
            ResultadoAprendizaje(id=i, texto=r.texto, evidencia=r.evidencia)
            for i, r in zip(ids, resultados)],
        problema=Problema(**general.problema.model_dump()),
        pis=Pis(**general.pis.model_dump()),
        metodologias=_exigir(general.metodologias, esq.n_metodologias, "metodologías"),
        momentos=[_momento(esq, i, titulos[i], ids, m) for i, m in enumerate(momentos)],
        rubrica_producto_final=[_fila(f) for f in _exigir(
            general.rubrica_producto_final, esq.n_filas_rubrica_pf, "rúbrica del producto final")],
    )


def redactar_silabo(cliente: ClienteLLM, cupo: Cupo, proyecto: ProyectoPropuesto,
                    esqueleto: Esqueleto) -> SilaboUTI:
    """Cinco llamadas (una general y una por momento) y el ensamblado del `SilaboUTI`.

    Lanza `SimulacionInvalida` si faltan elementos, si hay datos personales en cualquier texto
    o si quedan menos de 20 fragmentos. `JsonInvalido` se propaga: lo cuenta quien llama.
    """
    general = _pedir_general(cliente, cupo, proyecto, esqueleto)
    _exigir(general.titulos_momentos, N_MOMENTOS, "títulos de momentos")  # antes de gastar 4 llamadas
    momentos = [_pedir_momento(cliente, cupo, proyecto, esqueleto, general, i)
                for i in range(N_MOMENTOS)]
    try:
        silabo = _ensamblar(cupo, proyecto, esqueleto, general, momentos)
    except ValidationError:
        raise SimulacionInvalida("el sílabo ensamblado no cumple el contrato") from None
    if any(tiene_datos_personales(t) for t in _cadenas(silabo.model_dump(mode="json"))):
        raise SimulacionInvalida("el sílabo contiene datos personales")
    if len(fragmentos(silabo)) < MINIMO_FRAGMENTOS:
        raise SimulacionInvalida("el sílabo deja menos de 20 fragmentos útiles")
    return silabo
