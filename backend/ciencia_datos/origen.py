"""Marca de origen: los códigos de los sílabos simulados llevan un prefijo propio."""

PREFIJO_SIMULADO = "SIM-"


def es_simulado(codigo: str) -> bool:
    """Indica si el código pertenece a un sílabo simulado."""
    return codigo.startswith(PREFIJO_SIMULADO)
