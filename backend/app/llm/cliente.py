"""Cliente único del modelo de IA: vLLM local o DeepSeek (las dos con API compatible con OpenAI)."""
import json
import logging
import math
import re
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID

import httpx
import openai

CONTEXTO_MAXIMO = 8192
MARGEN_SEGURIDAD = 300
MINIMO_SALIDA = 256
PENALIZACION_REPETICION = 1.05
# DeepSeek admite hasta 1M de tokens; el presupuesto de los prompts sigue en 8192 (prompts.py).
CONTEXTO_DEEPSEEK = 1_000_000
PROVEEDORES = ("vllm", "deepseek")


def contexto_tls(estricto: bool = True) -> ssl.SSLContext:
    """Certificados del sistema operativo. `estricto=False` acepta raíces sin Authority Key Identifier,
    como la de un antivirus que inspecciona HTTPS en un equipo de desarrollo (Python 3.13 las rechaza)."""
    ctx = ssl.create_default_context()
    if not estricto:
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def instruccion_esquema(esquema: dict) -> dict:
    """DeepSeek no acepta `json_schema`: el esquema va en el prompt y Pydantic valida la salida."""
    return {"role": "system", "content": (
        "Responde únicamente con un objeto JSON válido, sin texto antes ni después, "
        "que cumpla exactamente este JSON Schema:\n" + json.dumps(esquema, ensure_ascii=False))}

registro = logging.getLogger("app.llm")


@dataclass(frozen=True)
class Respuesta:
    texto: str
    razonamiento: str
    tokens_entrada: int
    tokens_salida: int
    segundos: float
    finish_reason: str = "stop"


class ServidorNoDisponible(Exception):
    """El servidor no responde (red o 5xx) tras el reintento."""


class ErrorDelServidor(Exception):
    """Error no reintentable: respuesta 4xx o cuerpo mal formado."""


class JsonInvalido(Exception):
    """El modelo no produjo un JSON válido tras los reintentos (lo lanza `pedir_json`)."""


class ContextoExcedido(Exception):
    """El prompt no deja espacio suficiente para la respuesta."""


class ClienteLLM(Protocol):
    def contar_tokens(self, mensajes: list[dict]) -> int: ...

    def completar(self, mensajes: list[dict], *, rol: str, esquema: dict | None,
                  temperatura: float, max_tokens: int, pensar: bool,
                  trabajo_id: UUID | None, asignatura_id: UUID | None,
                  timeout_s: float | None = None) -> Respuesta: ...


_BLOQUE_THINK = re.compile(r"<think>(.*?)</think>", re.S)


def separar_razonamiento(contenido: str, campo: str | None) -> tuple[str, str]:
    """Devuelve (texto, razonamiento); admite el campo del servidor o el bloque <think>."""
    bloques = _BLOQUE_THINK.findall(contenido)
    texto = _BLOQUE_THINK.sub("", contenido)
    # Un <think> sin cerrar (salida cortada) tampoco debe llegar al texto.
    if "<think>" in texto:
        antes, _, resto = texto.partition("<think>")
        texto, bloques = antes, bloques + [resto]
    razonamiento = (campo or "").strip() or "\n".join(b.strip() for b in bloques)
    return texto.strip(), razonamiento


class ClienteVLLM:
    def close(self) -> None:
        """Cierra el pool HTTP una vez que terminaron los hilos consumidores."""
        self._sdk.close()

    def __init__(self, base_url: str, modelo: str, timeout_s: float, max_concurrencia: int,
                 registrar: Callable[[dict], None], api_key: str = "no-se-necesita",
                 transporte: httpx.BaseTransport | None = None, proveedor: str = "vllm",
                 tls_estricto: bool = True):
        if proveedor not in PROVEEDORES:
            raise ValueError(f"Proveedor de IA desconocido: {proveedor}")
        self._proveedor = proveedor
        self._raiz = base_url.rstrip("/").removesuffix("/v1")
        self._modelo = modelo
        self._timeout_s = timeout_s
        self._registrar = registrar
        self._semaforo = threading.BoundedSemaphore(max_concurrencia)
        verificar = contexto_tls(tls_estricto) if transporte is None else True
        self._http = httpx.Client(transport=transporte, timeout=timeout_s, verify=verificar)
        self._sdk = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s,
                                  max_retries=0, http_client=self._http)

    @property
    def contexto_max(self) -> int:
        """Ventana del modelo: 1M en DeepSeek, 8192 en el vLLM local."""
        return CONTEXTO_DEEPSEEK if self._proveedor == "deepseek" else CONTEXTO_MAXIMO

    def contar_tokens(self, mensajes: list[dict]) -> int:
        if self._proveedor == "deepseek":
            # DeepSeek no expone /tokenize: estimación conservadora para español (≈3 caracteres por token).
            return math.ceil(sum(len(str(m.get("content") or "")) for m in mensajes) / 3) + 4 * len(mensajes)
        ultimo: Exception | None = None
        for _ in range(2):  # un reintento ante error de red o 5xx
            try:
                respuesta = self._http.post(f"{self._raiz}/tokenize",
                                            json={"model": self._modelo, "messages": mensajes})
            except httpx.TransportError as error:
                ultimo = error
                continue
            if respuesta.status_code >= 500:
                ultimo = ErrorDelServidor(f"HTTP {respuesta.status_code}")
                continue
            if respuesta.status_code >= 400:
                raise ErrorDelServidor(f"/tokenize respondió HTTP {respuesta.status_code}")
            try:
                return int(respuesta.json()["count"])
            except (ValueError, KeyError, TypeError) as error:
                raise ErrorDelServidor(f"/tokenize devolvió un cuerpo inválido: {error}") from error
        raise ServidorNoDisponible(f"/tokenize no responde: {ultimo}") from ultimo

    def completar(self, mensajes: list[dict], *, rol: str, esquema: dict | None,
                  temperatura: float, max_tokens: int, pensar: bool,
                  trabajo_id: UUID | None, asignatura_id: UUID | None,
                  timeout_s: float | None = None) -> Respuesta:
        inicio = time.monotonic()
        tokens_entrada = tokens_salida = 0
        ok = False
        try:
            with self._semaforo:
                deepseek = self._proveedor == "deepseek"
                if deepseek and esquema is not None:
                    mensajes = [*mensajes, instruccion_esquema(esquema)]
                entrada = self.contar_tokens(mensajes)
                contexto = CONTEXTO_DEEPSEEK if deepseek else CONTEXTO_MAXIMO
                permitido = min(max_tokens, contexto - entrada - MARGEN_SEGURIDAD)
                if permitido < MINIMO_SALIDA:
                    raise ContextoExcedido(
                        f"entrada de {entrada} tokens; quedan {permitido} para la respuesta")
                parametros: dict = {}
                if deepseek:
                    extra = {"thinking": {"type": "enabled" if pensar else "disabled"}}
                    if esquema is not None:
                        parametros["response_format"] = {"type": "json_object"}
                else:
                    extra = {"chat_template_kwargs": {"enable_thinking": pensar}}
                    if esquema is not None:
                        extra["repetition_penalty"] = PENALIZACION_REPETICION
                        parametros["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {"name": "salida", "schema": esquema}}
                finalizacion = self._pedir(
                    dict(model=self._modelo, messages=mensajes, max_tokens=permitido,
                         temperature=temperatura, extra_body=extra,
                         timeout=timeout_s if timeout_s is not None else self._timeout_s,
                         **parametros))
            mensaje = finalizacion.choices[0].message
            extras = mensaje.model_extra or {}
            campo = (getattr(mensaje, "reasoning", None) or extras.get("reasoning")
                     or extras.get("reasoning_content"))
            texto, razonamiento = separar_razonamiento(mensaje.content or "", campo)
            uso = finalizacion.usage
            tokens_entrada = uso.prompt_tokens if uso else entrada
            tokens_salida = uso.completion_tokens if uso else 0
            ok = True
            return Respuesta(texto, razonamiento, tokens_entrada, tokens_salida,
                             round(time.monotonic() - inicio, 3),
                             finalizacion.choices[0].finish_reason or "stop")
        finally:
            try:
                self._registrar({
                    "trabajo_id": trabajo_id, "asignatura_id": asignatura_id, "rol": rol,
                    "tokens_entrada": tokens_entrada, "tokens_salida": tokens_salida,
                    "segundos": round(time.monotonic() - inicio, 3), "ok": ok})
            except Exception:  # el registro nunca debe tapar el resultado ni el error original
                registro.exception("no se pudo registrar la llamada al modelo (rol %s)", rol)

    def _pedir(self, argumentos: dict):
        """Una llamada con exactamente un reintento ante error de red o 5xx."""
        ultimo: Exception | None = None
        for _ in range(2):
            try:
                return self._sdk.chat.completions.create(**argumentos)
            except (openai.APIConnectionError, openai.InternalServerError) as error:
                ultimo = error
        raise ServidorNoDisponible(f"el servidor de IA no responde: {ultimo}") from ultimo


class ClienteSimulado:
    """Sustituto del servidor para las pruebas: respuestas por rol (lista o función)."""

    def __init__(self, respuestas: dict[str, list[str] | Callable[[list[dict]], str]]):
        self._respuestas = respuestas
        self.llamadas: list[dict] = []

    def contar_tokens(self, mensajes: list[dict]) -> int:
        return sum(len(m.get("content", "")) for m in mensajes) // 4

    def completar(self, mensajes: list[dict], *, rol: str, esquema: dict | None,
                  temperatura: float, max_tokens: int, pensar: bool,
                  trabajo_id: UUID | None, asignatura_id: UUID | None,
                  timeout_s: float | None = None) -> Respuesta:
        self.llamadas.append({
            "mensajes": mensajes, "rol": rol, "esquema": esquema, "temperatura": temperatura,
            "max_tokens": max_tokens, "pensar": pensar, "trabajo_id": trabajo_id,
            "asignatura_id": asignatura_id, "timeout_s": timeout_s})
        fuente = self._respuestas[rol]
        if callable(fuente):
            texto = fuente(mensajes)
        else:
            assert fuente, f"ClienteSimulado: no quedan respuestas para el rol {rol!r}"
            texto = fuente.pop(0)
        return Respuesta(texto, "", self.contar_tokens(mensajes), len(texto) // 4, 0.0, "stop")
