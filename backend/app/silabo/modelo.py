"""Contrato de datos del sílabo UTI (docs/mapeo-silabo.md §3).

Es el acuerdo entre el lector de PDF (P2) y el núcleo multiagente. Los modelos
son inmutables y rechazan campos desconocidos: por construcción no existe lugar
para el perfil del docente, sus datos de contacto ni las firmas (secciones I y
VII del sílabo), de modo que ningún dato personal puede llegar a la IA.
"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class BaseInmutable(BaseModel):
    """Base común: inmutable y sin campos desconocidos (también en lo anidado)."""
    model_config = ConfigDict(frozen=True, extra="forbid")


_Base = BaseInmutable


class Periodo(_Base):
    codigo: str
    inicio: date
    fin: date


class HorasPF(_Base):
    total: float
    contacto: float
    autonomo: float
    practico: float


class FranjaHorario(_Base):
    dia: str
    inicio: str
    fin: str


class ProyectoFormativo(_Base):
    nombre: str
    codigo: str
    version: str
    aprobado: date
    uoc: str
    nivel: int
    modalidad: str
    creditos: float
    horas: HorasPF
    horario: list[FranjaHorario] = Field(default_factory=list)


class ResultadoAprendizaje(_Base):
    id: str
    texto: str
    evidencia: str


class Problema(_Base):
    descripcion: str
    reto: str
    producto_final: str


class Pis(_Base):
    nombre: str
    aporte: str


class FilaRubrica(_Base):
    indicador: str
    niveles: dict[str, str]


class Actividad(_Base):
    texto: str
    horas: float


class ActividadDocente(_Base):
    texto: str
    horas: float
    asincronica: Actividad | None = None


class Sesion(_Base):
    id: str
    numero: int
    fecha: date
    semana_periodo: int
    docente: ActividadDocente
    practico: Actividad
    autonomo: Actividad
    contenidos: list[str]
    entregables: list[str] = Field(default_factory=list)


class Momento(_Base):
    numero: int
    titulo: str
    fecha_inicio: date
    fecha_fin: date
    ra: list[str]
    evidencia: str
    recursos: str
    politica_ia: str
    rubrica: list[FilaRubrica]
    sesiones: list[Sesion]


class Bibliografia(_Base):
    basica: list[str] = Field(default_factory=list)
    complementaria: list[str] = Field(default_factory=list)


class SilaboUTI(_Base):
    facultad: str
    carrera: str
    periodo: Periodo
    proyecto_formativo: ProyectoFormativo
    competencia_perfil: str = ""
    competencia_pf: str = ""
    metacompetencia: str
    resultados_aprendizaje: list[ResultadoAprendizaje]
    problema: Problema
    pis: Pis
    metodologias: list[str]
    momentos: list[Momento] = Field(min_length=1)
    rubrica_producto_final: list[FilaRubrica] = Field(default_factory=list)
    bibliografia: Bibliografia = Field(default_factory=Bibliografia)
