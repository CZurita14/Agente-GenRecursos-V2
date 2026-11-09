"""Cliente único del servidor de IA local (vLLM, API compatible con OpenAI)."""
import logging
import re
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
                 transporte: httpx.BaseTransport | None = None):
        self._raiz = base_url.rstrip("/").removesuffix("/v1")
        self._modelo = modelo
        self._timeout_s = timeout_s
        self._registrar = registrar
        self._semaforo = threading.BoundedSemaphore(max_concurrencia)
        self._http = httpx.Client(transport=transporte, timeout=timeout_s)
        self._sdk = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s,
                                  max_retries=0, http_client=self._http)

    def contar_tokens(self, mensajes: list[dict]) -> int:
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
                entrada = self.contar_tokens(mensajes)
                permitido = min(max_tokens, CONTEXTO_MAXIMO - entrada - MARGEN_SEGURIDAD)
                if permitido < MINIMO_SALIDA:
                    raise ContextoExcedido(
                        f"entrada de {entrada} tokens; quedan {permitido} para la respuesta")
                extra = {"chat_template_kwargs": {"enable_thinking": pensar}}
                parametros: dict = {}
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
