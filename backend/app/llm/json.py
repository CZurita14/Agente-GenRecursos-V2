"""Extracción y validación de JSON de las salidas del modelo."""
import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.cliente import ClienteLLM, JsonInvalido, Respuesta

T = TypeVar("T", bound=BaseModel)

REINTENTOS_JSON = 2

__all__ = ["JsonInvalido", "pedir_json", "ultimo_json"]


def ultimo_json(texto: str) -> dict:
    """Devuelve el último objeto JSON completo del texto, ignorando los bloques <think>."""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.S)
    decodificador = json.JSONDecoder()
    ultimo = None
    i = texto.find("{")
    while i != -1:
        try:
            objeto, fin = decodificador.raw_decode(texto, i)
        except ValueError:
            i = texto.find("{", i + 1)
            continue
        ultimo = objeto
        i = texto.find("{", fin)
    if ultimo is None:
        raise ValueError("no hay ningún objeto JSON en el texto")
    return ultimo


def pedir_json(cliente: ClienteLLM, mensajes: list[dict], modelo: type[T], esquema: dict,
               **kw) -> tuple[T, Respuesta]:
    """Pide una salida guiada por esquema y la valida con Pydantic.

    Ante JSON inválido (incluida una salida cortada por `length`, que queda truncada) o un
    `ValidationError`, reintenta hasta 2 veces; después lanza `JsonInvalido`.
    """
    kw.setdefault("temperatura", 0.4)
    kw.setdefault("max_tokens", 3500)
    kw.setdefault("pensar", False)
    kw.setdefault("trabajo_id", None)
    kw.setdefault("asignatura_id", None)
    ultimo_error: Exception | None = None
    for _ in range(1 + REINTENTOS_JSON):
        respuesta = cliente.completar(mensajes, esquema=esquema, **kw)
        if respuesta.finish_reason == "length":
            ultimo_error = ValueError("salida cortada por límite de tokens")
            continue
        try:
            return modelo.model_validate(ultimo_json(respuesta.texto)), respuesta
        except (ValueError, IndexError) as error:  # JSONDecodeError y ValidationError son ValueError
            ultimo_error = error
    raise JsonInvalido(f"JSON inválido tras {1 + REINTENTOS_JSON} intentos: {ultimo_error}")
