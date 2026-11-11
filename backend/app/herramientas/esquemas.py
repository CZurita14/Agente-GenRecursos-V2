"""Esquemas de las herramientas (spec §8.2): lo que el modelo llena y el código valida.

Cada herramienta tiene dos formas: el esquema JSON que se envía al servidor (salida
guiada) y el modelo Pydantic que valida lo recibido. El `item_id` nunca lo decide
el modelo: lo asigna el código según el plan.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Nivel = Literal["receptivo", "resolutivo", "reflexivo", "critico"]
NIVELES = ["receptivo", "resolutivo", "reflexivo", "critico"]


# --- Cuestionario -------------------------------------------------------------

class Opcion(BaseModel):
    texto: str
    justificacion: str
    error_que_representa: str


class _ItemSalida(BaseModel):
    """Ítem tal como lo entrega el modelo (sin `item_id`)."""
    nivel: Nivel
    ra: str
    contenido: str
    foco: str
    contexto: str
    pregunta: str = Field(min_length=25)
    opciones: list[Opcion] = Field(min_length=4, max_length=4)
    correcta: int = Field(ge=0, le=3)
    razonamiento: list[str]


class ItemCuestionario(_ItemSalida):
    item_id: str


class LoteCuestionario(BaseModel):
    items: list[_ItemSalida]


def esquema_cuestionario(n: int, ras: list[str], contenidos: list[str]) -> dict:
    """Esquema de un lote de `n` ítems; `ra` y `contenido` solo admiten los de la clase."""
    opcion = {"type": "object", "properties": {
        "texto": {"type": "string"}, "justificacion": {"type": "string"},
        "error_que_representa": {"type": "string"}},
        "required": ["texto", "justificacion", "error_que_representa"]}
    item = {"type": "object", "properties": {
        "nivel": {"type": "string", "enum": NIVELES},
        "ra": {"type": "string", "enum": list(ras)},
        "contenido": {"type": "string", "enum": list(contenidos)},
        "foco": {"type": "string"}, "contexto": {"type": "string"},
        "pregunta": {"type": "string", "minLength": 25},
        "opciones": {"type": "array", "minItems": 4, "maxItems": 4, "items": opcion},
        "correcta": {"type": "integer", "minimum": 0, "maximum": 3},
        "razonamiento": {"type": "array", "items": {"type": "string"}}},
        "required": ["nivel", "ra", "contenido", "foco", "contexto", "pregunta",
                     "opciones", "correcta", "razonamiento"]}
    return {"type": "object", "properties": {
        "items": {"type": "array", "minItems": n, "maxItems": n, "items": item}},
        "required": ["items"]}


# --- Ficha de clase -------------------------------------------------------------

class FichaConceptual(BaseModel):
    ideas_clave: list[str] = Field(min_length=3, max_length=6)
    relacion_ra: str
    errores_frecuentes: list[str] = Field(min_length=1)


class Ejemplo(BaseModel):
    enunciado: str
    pasos: list[str] = Field(min_length=1)
    resultado: str


class FichaAplicacion(BaseModel):
    ejemplo: Ejemplo
    autocomprobacion: list[str] = Field(min_length=3, max_length=5)


_LISTA = {"type": "array", "items": {"type": "string"}}

ESQUEMA_FICHA_CONCEPTUAL = {"type": "object", "properties": {
    "ideas_clave": {**_LISTA, "minItems": 3, "maxItems": 6},
    "relacion_ra": {"type": "string"},
    "errores_frecuentes": {**_LISTA, "minItems": 1}},
    "required": ["ideas_clave", "relacion_ra", "errores_frecuentes"]}

ESQUEMA_FICHA_APLICACION = {"type": "object", "properties": {
    "ejemplo": {"type": "object", "properties": {
        "enunciado": {"type": "string"}, "pasos": {**_LISTA, "minItems": 1},
        "resultado": {"type": "string"}},
        "required": ["enunciado", "pasos", "resultado"]},
    "autocomprobacion": {**_LISTA, "minItems": 3, "maxItems": 5}},
    "required": ["ejemplo", "autocomprobacion"]}


# --- Herramientas de momento y asignatura (P3b) -----------------------------------
# Esquemas cerrados; las listas cerradas (ids, indicadores, RA) van como enum en el JSON
# pedido al modelo y el verificador vuelve a comprobar la pertenencia.

class _Cerrado(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepasoSesion(_Cerrado):
    clase_id: str
    ideas_clave: list[str] = Field(min_length=3, max_length=5)


class RepasoMomento(_Cerrado):
    sesiones: list[RepasoSesion] = Field(min_length=1)
    conexion_ra: str = Field(min_length=40)
    preguntas_repaso: list[str] = Field(min_length=3, max_length=5)


class CriterioGuia(_Cerrado):
    indicador: str
    que_observar: str = Field(min_length=20)


class GuiaEvidencia(_Cerrado):
    que_se_pide: str = Field(min_length=40, max_length=600)
    como_se_valora: list[CriterioGuia] = Field(min_length=1)
    errores_comunes: list[str] = Field(min_length=3, max_length=5)
    autochequeo: list[str] = Field(min_length=3, max_length=5)


class PreguntaCaso(_Cerrado):
    nivel: Literal["receptivo", "resolutivo", "reflexivo", "critico"]
    pregunta: str = Field(min_length=15)
    respuesta_orientativa: str = Field(min_length=20)


class EstudioCaso(_Cerrado):
    escenario: str = ""  # Lo asigna el código (C9), no el modelo.
    caso: str = Field(min_length=300)
    preguntas: list[PreguntaCaso] = Field(min_length=3, max_length=6)
    ra: str


def _enum(valores) -> dict:
    return {"type": "string", "enum": list(valores)}


def esquema_repaso(clase_ids: list[str]) -> dict:
    return {"type": "object", "properties": {
        "sesiones": {"type": "array", "minItems": 1, "maxItems": len(clase_ids), "items": {
            "type": "object", "properties": {"clase_id": _enum(clase_ids),
                                             "ideas_clave": {**_LISTA, "minItems": 3, "maxItems": 5}},
            "required": ["clase_id", "ideas_clave"]}},
        "conexion_ra": {"type": "string"},
        "preguntas_repaso": {**_LISTA, "minItems": 3, "maxItems": 5}},
        "required": ["sesiones", "conexion_ra", "preguntas_repaso"]}


def esquema_guia_evidencia(indicadores: list[str]) -> dict:
    return {"type": "object", "properties": {
        "que_se_pide": {"type": "string"},
        "como_se_valora": {"type": "array", "minItems": 1, "maxItems": len(indicadores), "items": {
            "type": "object", "properties": {"indicador": _enum(indicadores), "que_observar": {"type": "string"}},
            "required": ["indicador", "que_observar"]}},
        "errores_comunes": {**_LISTA, "minItems": 3, "maxItems": 5},
        "autochequeo": {**_LISTA, "minItems": 3, "maxItems": 5}},
        "required": ["que_se_pide", "como_se_valora", "errores_comunes", "autochequeo"]}


def esquema_estudio_caso(ras: list[str]) -> dict:
    return {"type": "object", "properties": {
        "caso": {"type": "string"},
        "preguntas": {"type": "array", "minItems": 3, "maxItems": 6, "items": {
            "type": "object", "properties": {
                "nivel": _enum(["receptivo", "resolutivo", "reflexivo", "critico"]),
                "pregunta": {"type": "string"}, "respuesta_orientativa": {"type": "string"}},
            "required": ["nivel", "pregunta", "respuesta_orientativa"]}},
        "ra": _enum(ras)},
        "required": ["caso", "preguntas", "ra"]}


class PasoRuta(_Cerrado):
    momento: str
    aporte: str = Field(min_length=30)


class CriterioFinal(_Cerrado):
    indicador: str
    como_prepararse: str = Field(min_length=20)


class GuiaProductoFinal(_Cerrado):
    ruta: list[PasoRuta] = Field(min_length=1)
    criterios: list[CriterioFinal] = Field(min_length=1)
    recomendaciones: list[str] = Field(min_length=3, max_length=5)


def esquema_guia_producto_final(momentos: list[str], indicadores: list[str]) -> dict:
    return {"type": "object", "properties": {
        "ruta": {"type": "array", "minItems": len(momentos), "maxItems": len(momentos), "items": {
            "type": "object", "properties": {"momento": _enum(momentos), "aporte": {"type": "string"}},
            "required": ["momento", "aporte"]}},
        "criterios": {"type": "array", "minItems": 1, "maxItems": len(indicadores), "items": {
            "type": "object", "properties": {"indicador": _enum(indicadores), "como_prepararse": {"type": "string"}},
            "required": ["indicador", "como_prepararse"]}},
        "recomendaciones": {**_LISTA, "minItems": 3, "maxItems": 5}},
        "required": ["ruta", "criterios", "recomendaciones"]}


# --- Herramientas de clase de la V2 (JSON de trabajo) ---

class EjercicioGuiado(_Cerrado):
    enunciado: str = Field(min_length=40)
    pasos: list[str] = Field(min_length=2, max_length=8)
    resultado_esperado: str = Field(min_length=10)


class PracticaGuiada(_Cerrado):
    objetivo: str = Field(min_length=20)
    ejercicios: list[EjercicioGuiado] = Field(min_length=2, max_length=4)
    errores_a_evitar: list[str] = Field(min_length=1, max_length=5)


class Tarjeta(_Cerrado):
    frente: str = Field(min_length=5, max_length=300)
    reverso: str = Field(min_length=5, max_length=300)
    contenido: str


class Tarjetas(_Cerrado):
    tarjetas: list[Tarjeta] = Field(min_length=8, max_length=15)


class GuiaAutonoma(_Cerrado):
    objetivo: str = Field(min_length=20)
    actividad: str = Field(min_length=20, max_length=500)
    pasos: list[str] = Field(min_length=3, max_length=8)
    tiempo_estimado: str = Field(min_length=3)
    para_la_siguiente_clase: str = Field(min_length=10)
    autochequeo: list[str] = Field(min_length=3, max_length=5)
    conexion_pis: str = ""


class FaseClase(_Cerrado):
    fase: str
    minutos: int = Field(ge=5, le=240)
    docente: str = Field(min_length=10)
    estudiantes: str = Field(min_length=10)


class GuionClase(_Cerrado):
    objetivo: str = Field(min_length=20)
    fases: list[FaseClase] = Field(min_length=3, max_length=6)
    preguntas_detonantes: list[str] = Field(min_length=2, max_length=5)
    conexion_pis: str = ""


def _cerrado(propiedades: dict, opcionales: tuple[str, ...] = ()) -> dict:
    return {"type": "object", "additionalProperties": False, "properties": propiedades,
            "required": [k for k in propiedades if k not in opcionales]}


def _textos(minimo: int, maximo: int) -> dict:
    return {"type": "array", "items": {"type": "string"}, "minItems": minimo, "maxItems": maximo}


def esquema_practica_guiada() -> dict:
    ejercicio = _cerrado({"enunciado": {"type": "string"}, "pasos": _textos(2, 8),
                          "resultado_esperado": {"type": "string"}})
    return _cerrado({"objetivo": {"type": "string"},
                     "ejercicios": {"type": "array", "items": ejercicio, "minItems": 2, "maxItems": 4},
                     "errores_a_evitar": _textos(1, 5)})


def esquema_tarjetas(contenidos: list[str]) -> dict:
    contenido = {"type": "string", "enum": list(contenidos)} if contenidos else {"type": "string"}
    tarjeta = _cerrado({"frente": {"type": "string"}, "reverso": {"type": "string"}, "contenido": contenido})
    return _cerrado({"tarjetas": {"type": "array", "items": tarjeta, "minItems": 8, "maxItems": 15}})


def esquema_guia_autonoma() -> dict:
    return _cerrado({"objetivo": {"type": "string"}, "actividad": {"type": "string"}, "pasos": _textos(3, 8),
                     "tiempo_estimado": {"type": "string"}, "para_la_siguiente_clase": {"type": "string"},
                     "autochequeo": _textos(3, 5), "conexion_pis": {"type": "string"}}, ("conexion_pis",))


def esquema_guion_clase() -> dict:
    fase = _cerrado({"fase": {"type": "string", "enum": ["inicio", "desarrollo", "cierre"]},
                     "minutos": {"type": "integer"}, "docente": {"type": "string"},
                     "estudiantes": {"type": "string"}})
    return _cerrado({"objetivo": {"type": "string"},
                     "fases": {"type": "array", "items": fase, "minItems": 3, "maxItems": 6},
                     "preguntas_detonantes": _textos(2, 5), "conexion_pis": {"type": "string"}},
                    ("conexion_pis",))


class CreditoImagen(_Cerrado):
    hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    autor: str
    licencia: str
    fuente: str
    enlace: str = ""


class Diapositiva(_Cerrado):
    titulo: str = Field(min_length=3, max_length=80)
    puntos: list[str] = Field(min_length=2, max_length=6)
    notas: str = Field(min_length=20)
    # Palabras en inglés para buscar la imagen; la imagen y su crédito los agrega el código.
    imagen_busqueda: str = Field(default="", max_length=60)
    imagen: CreditoImagen | None = None


class Presentacion(_Cerrado):
    titulo: str = Field(min_length=5, max_length=120)
    diapositivas: list[Diapositiva] = Field(min_length=6, max_length=12)


def esquema_presentacion() -> dict:
    diapositiva = _cerrado({"titulo": {"type": "string"}, "puntos": _textos(2, 6), "notas": {"type": "string"},
                            "imagen_busqueda": {"type": "string"}})
    return _cerrado({"titulo": {"type": "string"},
                     "diapositivas": {"type": "array", "items": diapositiva, "minItems": 6, "maxItems": 12}})
