"""Ciencia de datos fuera de línea: corpus, entrenamiento y evaluación del razonador."""


def consola_utf8() -> None:
    """Las herramientas (torch.onnx imprime emojis) fallan en una consola cp1252: fuerza UTF-8."""
    import sys

    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
