"""Tarifas de DeepSeek para calcular el costo de cada llamada igual que lo cobra la API.

Fuente: https://api-docs.deepseek.com/quick_start/pricing (revisada el 2026-11-24). Cuando DeepSeek
cambie sus precios se actualiza esta tabla y VIGENCIA; el costo ya guardado de cada llamada no se
recalcula. Precios en USD por millón de tokens, en horario pico. Fuera de pico se cobra la mitad.

Horario pico: lunes a viernes, 01:00-04:00 y 06:00-10:00 UTC, salvo feriados chinos (que no se
conocen de antemano: en esos días el costo calculado puede quedar por encima del cobrado).
"""
from datetime import datetime, timezone
from decimal import Decimal

VIGENCIA = "2026-11-24"
FUENTE = "https://api-docs.deepseek.com/quick_start/pricing"

# modelo -> (entrada en caché, entrada sin caché, salida) en horario pico
_PICO = {
    "deepseek-v4-pro": (Decimal("0.044"), Decimal("1.32"), Decimal("3.96")),
    "deepseek-flash": (Decimal("0.006"), Decimal("0.3"), Decimal("1.2")),
}
# Nombres que DeepSeek sigue aceptando y cobra con la tarifa del modelo actual.
_ALIAS = {"deepseek-v4-flash": "deepseek-flash", "deepseek-v4-flash-vision-exp": "deepseek-flash"}
_FRANJAS_PICO = ((1, 4), (6, 10))  # horas UTC [inicio, fin)
_MILLON = Decimal(1_000_000)


def es_pico(momento: datetime) -> bool:
    utc = momento.astimezone(timezone.utc)
    return utc.weekday() < 5 and any(a <= utc.hour < b for a, b in _FRANJAS_PICO)


def tarifa(modelo: str) -> tuple[Decimal, Decimal, Decimal] | None:
    return _PICO.get(_ALIAS.get(modelo, modelo))


def costo(modelo: str, en_cache: int, sin_cache: int, salida: int, momento: datetime) -> Decimal | None:
    """Costo en USD de una llamada; None si el modelo no tiene tarifa (p. ej. el vLLM local)."""
    t = tarifa(modelo)
    if t is None:
        return None
    total = (en_cache * t[0] + sin_cache * t[1] + salida * t[2]) / _MILLON
    return total if es_pico(momento) else total / 2
