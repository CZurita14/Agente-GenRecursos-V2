"""Error del lector: el sílabo no se pudo leer (P4 lo traduce a 422)."""


class SilaboIlegible(ValueError):
    """El motivo es un texto para el docente; nunca incluye contenido del PDF."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo
