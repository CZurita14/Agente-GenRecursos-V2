"""SGA simulado para pruebas y desarrollo: lee fixtures de una carpeta.

Estructura de `base`:
  usuarios.json             {"usuarios": [{usuario, sha256, correo, nombre}]}  (sha256 de la clave de prueba)
  materias/<usuario>.json   lista de materias (materias-api.schema.json)
  sga_silabos/<codigo_pf>.json  sílabo crudo (puede traer claves privadas falsas)
"""
import hashlib
import hmac
import json
from pathlib import Path

from app.sga.proveedor import (CredencialesInvalidas, IdentidadSGA, MateriaSGA,
                               SGANoDisponible, SilaboNoDisponible)

_MENSAJE = "Usuario o clave incorrectos"


class _Permiso:
    """Permiso opaco: solo recuerda quién se autenticó (nunca la clave)."""
    __slots__ = ("usuario",)

    def __init__(self, usuario: str):
        self.usuario = usuario

    def __repr__(self) -> str:
        return "<PermisoSimulado>"


class ProveedorSimulado:
    def __init__(self, base: Path):
        self._base = Path(base)

    def _leer(self, ruta: Path):
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise SGANoDisponible("SGA simulado no disponible") from None

    def autenticar(self, usuario: str, clave: str) -> tuple[IdentidadSGA, object]:
        datos = self._leer(self._base / "usuarios.json")
        encontrado = next((u for u in datos["usuarios"] if u["usuario"] == usuario), None)
        # Siempre se compara un hash, exista o no el usuario.
        esperado = encontrado["sha256"] if encontrado else "0" * 64
        hash_clave = hashlib.sha256(clave.encode()).hexdigest()
        if not hmac.compare_digest(hash_clave, esperado) or encontrado is None:
            raise CredencialesInvalidas(_MENSAJE)
        ident = IdentidadSGA(encontrado["usuario"], encontrado["correo"], encontrado["nombre"])
        return ident, _Permiso(ident.usuario)

    def listar_materias(self, permiso: object) -> list[MateriaSGA]:
        if not isinstance(permiso, _Permiso):
            raise CredencialesInvalidas(_MENSAJE)
        datos = self._leer(self._base / "materias" / f"{permiso.usuario}.json")
        return [MateriaSGA(**m) for m in datos]

    def obtener_silabo(self, permiso: object, materia: MateriaSGA) -> dict:
        if not isinstance(permiso, _Permiso):
            raise CredencialesInvalidas(_MENSAJE)
        codigo = materia.codigo_pf
        if not codigo or "/" in codigo or "\\" in codigo or ".." in codigo:
            raise SilaboNoDisponible("Sílabo no disponible")
        ruta = self._base / "sga_silabos" / f"{codigo}.json"
        if not ruta.is_file():
            raise SilaboNoDisponible("Sílabo no disponible")
        return self._leer(ruta)
