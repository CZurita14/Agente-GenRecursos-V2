"""Trazabilidad académica del recurso, separada de su presentación."""
from pydantic import BaseModel, Field


class PaqueteEvidencia(BaseModel):
    clase_id: str
    momento: str
    ra: list[str]
    contenidos: list[str]
    agente: str
    perfil_dificultad: str
    tabla_planificada: dict[str, int]
    tabla_real: dict[str, int]
    verificaciones: dict[str, list[str]]
    veredictos: dict[str, str]
    devoluciones: int
    tokens: tuple[int, int]
    borrador: bool = False
    motivos_revision: list[str] = Field(default_factory=list)
    razonador_version: str | None = None  # La del plan usado; None si el plan no pasó por el razonador.

    def resumen(self) -> str:
        total = sum(self.tabla_real.values())
        verificados = sum(not f for f in self.verificaciones.values())
        return f"{total} ítems · {verificados} verificados · {self.devoluciones} devoluciones"
