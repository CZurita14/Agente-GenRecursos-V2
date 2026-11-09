"""Interfaz del proveedor del SGA: tipos, errores y el protocolo que implementan los adaptadores."""
import re
from dataclasses import dataclass
from typing import Protocol


class SGAError(Exception):
    """Base de los errores del SGA. Los mensajes nunca llevan usuario, clave ni datos del sílabo."""


class CredencialesInvalidas(SGAError):
    """Usuario o clave rechazados (mismo mensaje para ambos casos)."""


class SGANoDisponible(SGAError):
    """El SGA no responde o el adaptador no está configurado."""


class SilaboNoDisponible(SGAError):
    """El SGA no entrega el sílabo de la materia pedida."""


@dataclass(frozen=True)
class IdentidadSGA:
    usuario: str
    correo: str
    nombre: str


@dataclass(frozen=True)
class MateriaSGA:
    id_sga: str
    codigo_pf: str
    paralelo: str
    nombre: str
    carrera: str
    estado: str


class ProveedorSGA(Protocol):
    def autenticar(self, usuario: str, clave: str) -> tuple[IdentidadSGA, object]:
        """Valida las credenciales. El segundo valor es un permiso opaco que vive solo
        durante la sincronización; nunca contiene la clave."""
        ...

    def listar_materias(self, permiso: object) -> list[MateriaSGA]: ...

    def obtener_silabo(self, permiso: object, materia: MateriaSGA) -> dict:
        """Sílabo crudo del SGA; pasa por `a_contrato` antes de validarse."""
        ...


_CODIGO = re.compile(r"^\[(\d+)\]\s+([A-Z]\d{2}-[A-Z]{4}-\d-\d{5}-\d{4})\s+PARALELO\s+(\d+)$")


def separar_codigo(texto: str) -> tuple[str, str, str]:
    """`"[12345] A99-AAAA-9-99999-9999 PARALELO 1"` -> `("12345", "A99-AAAA-9-99999-9999", "1")`."""
    m = _CODIGO.match(texto.strip())
    if not m:
        raise ValueError("texto de materia con formato inesperado")
    return m.group(1), m.group(2), m.group(3)
