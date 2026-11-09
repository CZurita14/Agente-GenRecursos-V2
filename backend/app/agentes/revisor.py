"""Revisor con IA (spec §10.2): resuelve cada ítem sin ver la clave y vigila la integridad.

Trabaja de a 1 ítem por llamada con modo razonamiento (R1). El prompt nunca muestra la
clave, las justificaciones, los errores declarados ni el razonamiento del worker. Si la
herramienta resuelve un entregable del momento (§9.4), la devuelve aunque el ítem esté bien.
"""
from uuid import UUID

from pydantic import BaseModel, ValidationError, field_validator

from app.agentes.mensajes import EstiloFacultad, ResultadoItem
from app.config import ajustes
from app.herramientas.esquemas import ItemCuestionario
from app.llm.cliente import ClienteLLM
from app.llm.json import ultimo_json
from app.llm.prompts import Sello, construir_prompt
from app.silabo.contexto import ContextoClase

# El prompt reserva 3 500 tokens (tope del constructor); el razonamiento necesita más,
# así que se pide más salida y el cliente la ajusta a lo que quede de los 8 192 (H4).
SALIDA_PROMPT = 3500
MAX_SALIDA_REVISOR = 7000
INTENTOS = 2  # 1 + 1 reintento ante veredicto inválido o incompleto
SIN_VEREDICTO = "revisor sin veredicto"
_SIN_ESTILO = EstiloFacultad(tipos_de_caso=[], software_habitual=[])

INSTRUCCIONES = (
    "Eres un evaluador universitario estricto. Juzgas herramientas de estudio generadas a "
    "partir del sílabo. Razona paso a paso y al final responde SOLO un objeto JSON. "
    "Redacta cada campo \"motivo\" en español, porque lo lee el docente."
)

FORMATO_ITEM = (
    'Formato del JSON final: {"veredictos": [{"opcion": 0, "valida": true|false, "motivo": "..."}, '
    '... una entrada por opción, 4 en total], "resuelve_entregable": true|false, '
    '"entregable": "nombre del entregable o vacío", "motivo": "..."}'
)
FORMATO_FICHA = (
    'Formato del JSON final: {"resuelve_entregable": true|false, '
    '"entregable": "nombre del entregable o vacío", "motivo": "..."}'
)


# §9.4 regla 1: trabajar los mismos contenidos con otros casos y datos es lo esperado.
# Sin esta precisión, Qwen marcaba cualquier pregunta sobre la técnica del entregable (humo T15).
CRITERIO_INTEGRIDAD = (
    "Solo responde true si entrega la solución o un borrador de un entregable del momento: "
    "su caso o sus datos propios resueltos, el análisis o el resultado que el estudiante debe "
    "producir, o un texto que podría copiar en él. Practicar los mismos contenidos o técnicas "
    "con otros casos y datos es el propósito de la herramienta y NO resuelve el entregable."
)


class _VeredictoOpcion(BaseModel):
    opcion: int
    valida: bool
    motivo: str = ""


class _Integridad(BaseModel):
    resuelve_entregable: bool
    entregable: str = ""
    motivo: str = ""


class _VeredictoItem(_Integridad):
    veredictos: list[_VeredictoOpcion]

    @field_validator("veredictos")
    @classmethod
    def validar_opciones(cls, veredictos: list[_VeredictoOpcion]) -> list[_VeredictoOpcion]:
        if len(veredictos) != 4 or {v.opcion for v in veredictos} != {0, 1, 2, 3}:
            raise ValueError("Se exige un único veredicto por opción: 0, 1, 2 y 3")
        return veredictos


def _pedido_item(item: ItemCuestionario) -> str:
    opciones = "\n".join(f"{k}) {o.texto}" for k, o in enumerate(item.opciones))
    return (
        f"Situación: {item.contexto}\nPregunta: {item.pregunta}\nOpciones:\n{opciones}\n\n"
        "1. Juzga CADA opción por separado: ¿es una respuesta válida y técnicamente exacta a la "
        "pregunta? Sé estricto con la redacción; puede haber cero, una o varias válidas.\n"
        "2. ¿Este ítem resuelve alguno de los entregables del momento indicados en el sílabo? "
        f"{CRITERIO_INTEGRIDAD}\n"
        f"Redacta los motivos en español.\n{FORMATO_ITEM}"
    )


def _pedido_ficha(ficha: dict) -> str:
    secciones = "\n".join(f"- {k}: {v}" for k, v in ficha.items())
    return (
        f"Sección de la ficha de estudio:\n{secciones}\n\n"
        "¿Esta ficha resuelve alguno de los entregables del momento indicados en el sílabo, "
        f"o contradice su política de uso de IA? {CRITERIO_INTEGRIDAD}\n"
        f"Redacta el motivo en español.\n{FORMATO_FICHA}"
    )


def _consultar(cliente: ClienteLLM, contexto: ContextoClase, pedido: str, modelo: type[BaseModel],
               trabajo_id: UUID, asignatura_id: UUID, timeout_s: float | None) -> BaseModel | None:
    """Reintenta una vez ante un veredicto inválido o incompleto. None = sin veredicto."""
    mensajes = construir_prompt(
        sello=Sello(codigo_pf=contexto.codigo_pf, clase_id=contexto.clase_id, fecha=contexto.fecha),
        instrucciones=INSTRUCCIONES, contexto=contexto, estilo=_SIN_ESTILO, ya_generado=[],
        pedido=pedido, salida_max=SALIDA_PROMPT, contar=cliente.contar_tokens,
    )
    timeout = timeout_s if timeout_s is not None else ajustes().llm_timeout_revisor_s
    for _ in range(INTENTOS):
        respuesta = cliente.completar(
            mensajes, rol="revisor", esquema=None, temperatura=0, max_tokens=MAX_SALIDA_REVISOR,
            pensar=True, trabajo_id=trabajo_id, asignatura_id=asignatura_id, timeout_s=timeout,
        )
        if respuesta.finish_reason == "length":
            continue
        try:
            return modelo.model_validate(ultimo_json(respuesta.texto))
        except (ValueError, ValidationError):
            continue
    return None


def _numeros(indices: list[int]) -> str:
    """Opciones en numeración del docente (1-4): "1", "1 y 3", "1, 2 y 4"."""
    n = [str(i + 1) for i in indices]
    return n[0] if len(n) == 1 else ", ".join(n[:-1]) + " y " + n[-1]


def _motivo_integridad(v: _Integridad) -> str:
    nombre = v.entregable.strip() or "un entregable del momento"
    return f"resuelve el entregable {nombre}" + (f": {v.motivo}" if v.motivo else "")


def revisar_items(items: list[ItemCuestionario], contexto: ContextoClase, cliente: ClienteLLM, *,
                  trabajo_id: UUID, asignatura_id: UUID,
                  timeout_s: float | None = None) -> list[ResultadoItem]:
    resultados = []
    for item in items:
        v = _consultar(cliente, contexto, _pedido_item(item), _VeredictoItem,
                       trabajo_id, asignatura_id, timeout_s)
        if v is None:
            resultados.append(ResultadoItem(item_id=item.item_id, fallos_verificacion=[],
                                            revisor="sin_veredicto", motivo=SIN_VEREDICTO))
            continue
        validas = sorted({x.opcion for x in v.veredictos if x.valida})
        if validas == [item.correcta]:
            estado, motivo = "ok", ""
        elif not validas:
            estado, motivo = "devuelto", "el revisor no considera válida ninguna opción"
        elif len(validas) > 1:
            estado, motivo = "devuelto", f"el revisor considera correctas las opciones {_numeros(validas)}"
        else:
            estado, motivo = "devuelto", (f"el revisor considera correcta la opción {_numeros(validas)}, "
                                          f"no la {item.correcta + 1}")
        if v.resuelve_entregable:
            # La integridad manda, pero el veredicto de la clave se conserva para el worker.
            estado, motivo = "devuelto", _motivo_integridad(v) + (f"; además, {motivo}" if motivo else "")
        resultados.append(ResultadoItem(item_id=item.item_id, fallos_verificacion=[],
                                        revisor=estado, motivo=motivo))
    return resultados


def revisar_ficha(ficha: dict, contexto: ContextoClase, cliente: ClienteLLM, *,
                  trabajo_id: UUID, asignatura_id: UUID,
                  timeout_s: float | None = None, item_id: str = "ficha") -> ResultadoItem:
    """Solo integridad académica (§10.2, 2.º punto): la ficha no tiene clave que resolver."""
    v = _consultar(cliente, contexto, _pedido_ficha(ficha), _Integridad,
                   trabajo_id, asignatura_id, timeout_s)
    if v is None:
        return ResultadoItem(item_id=item_id, fallos_verificacion=[], revisor="sin_veredicto",
                             motivo=SIN_VEREDICTO)
    if v.resuelve_entregable:
        return ResultadoItem(item_id=item_id, fallos_verificacion=[], revisor="devuelto",
                             motivo=_motivo_integridad(v))
    return ResultadoItem(item_id=item_id, fallos_verificacion=[], revisor="ok")
