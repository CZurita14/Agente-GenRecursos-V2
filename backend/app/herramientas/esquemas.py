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
