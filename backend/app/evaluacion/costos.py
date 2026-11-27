"""Costo estimado de cada herramienta, para avisar antes de preparar un parcial (V5-1, medido en V5-2).

Medición real del 2026-11-27 (DeepSeek `deepseek-v4-pro`, horario normal, de punta a punta con verificador y revisor,
4 sílabos piloto):
- herramienta de una sección: de US$ 0,012 a 0,018 (promedio ≈ 0,016); el insumo de respaldo llegó a 0,039;
- cuestionario o simulacro de 12 preguntas: ≈ US$ 0,22 (unos 0,018 por pregunta), porque el revisor juzga cada una.

El horario de descuento cuesta ≈ 1/1,81 del normal (razón del informe general). Es una estimación para decidir, no
una factura: el costo real queda en el panel de consumo.
"""
from app.herramientas.sin_ia import HERRAMIENTAS_SIN_IA

FACTOR_HORARIO_NORMAL = 1.81
POR_HERRAMIENTA = 0.009        # Una sección, horario de descuento (≈ 0,016 en horario normal).
POR_PREGUNTA = 0.010           # Cuestionario o simulacro, por pregunta, horario de descuento (≈ 0,018 normal).
PREGUNTAS_POR_OMISION = 12     # Lo que encola «Preparar el parcial».
_CUESTIONARIOS = {"cuestionario", "simulacro"}


def costo_estimado(herramienta: str, preguntas: int = PREGUNTAS_POR_OMISION) -> float:
    """US$ en horario de descuento; 0 si la herramienta sale del sílabo sin IA."""
    if herramienta in HERRAMIENTAS_SIN_IA:
        return 0.0
    return round(POR_PREGUNTA * preguntas, 3) if herramienta in _CUESTIONARIOS else POR_HERRAMIENTA
