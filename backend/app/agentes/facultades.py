"""Perfiles de facultad, estilo por carrera y enrutamiento (spec §4.1-§4.3).

Cada facultad tiene una configuración YAML en `agentes/` con su estilo. Las
carreras solo escriben lo que cambia; el coordinador usa siempre `estilo_para`
para armar la `TareaLote`. Un sílabo se enruta por el nombre de su facultad y
las facultades no reconocidas van al agente `general`.
"""
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from app.agentes.mensajes import EstiloFacultad
from app.silabo.modelo import BaseInmutable


class PerfilFacultad(BaseInmutable):
    id: str
    facultad: str | None
    estilo: EstiloFacultad
    carreras: dict[str, EstiloFacultad] = {}
    herramientas_recomendadas: dict[str, list[str]]


def normalizar(texto: str) -> str:
    """Mayúsculas, sin tildes y con espacios colapsados."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.upper().split())


def _estilo_carrera(datos: dict[str, Any] | None) -> EstiloFacultad:
    # Lo omitido queda vacío: así hereda el estilo de la facultad.
    base = {"tipos_de_caso": [], "software_habitual": [], "vocabulario": "", "escenarios": []}
    return EstiloFacultad(**(base | (datos or {})))


def _perfil_desde(datos: dict[str, Any]) -> PerfilFacultad:
    carreras = {
        normalizar(nombre): _estilo_carrera(ajuste)
        for nombre, ajuste in (datos.get("carreras") or {}).items()
    }
    return PerfilFacultad(
        id=datos["id"],
        facultad=datos.get("facultad"),
        estilo=datos["estilo"],
        carreras=carreras,
        herramientas_recomendadas=datos["herramientas_recomendadas"],
    )


def cargar_perfiles(directorio: Path) -> dict[str, PerfilFacultad]:
    """Carga los perfiles `*.yaml` indexados por `id`. Exige el agente `general`."""
    perfiles: dict[str, PerfilFacultad] = {}
    for ruta in sorted(directorio.glob("*.yaml")):
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        perfil = _perfil_desde(datos)
        perfiles[perfil.id] = perfil
    if "general" not in perfiles:
        raise ValueError(f"Falta el agente general (general.yaml) en {directorio}")
    return perfiles


def cargar_catalogo(ruta: Path) -> dict[str, str]:
    """Mapea cada nombre normalizado de facultad (y sus alternos) a su sigla."""
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    catalogo: dict[str, str] = {}
    for facultad in datos["facultades"]:
        nombres = [facultad["nombre"], *facultad.get("nombres_alt", [])]
        for nombre in nombres:
            catalogo[normalizar(nombre)] = facultad["sigla"]
    return catalogo


def estilo_para(perfil: PerfilFacultad, carrera: str) -> EstiloFacultad:
    """Estilo de la carrera: sus listas no vacías y su `vocabulario` reemplazan a los de la facultad."""
    ajuste = perfil.carreras.get(normalizar(carrera))
    if ajuste is None:
        return perfil.estilo
    base = perfil.estilo
    return EstiloFacultad(
        tipos_de_caso=ajuste.tipos_de_caso or base.tipos_de_caso,
        software_habitual=ajuste.software_habitual or base.software_habitual,
        vocabulario=ajuste.vocabulario or base.vocabulario,
        escenarios=ajuste.escenarios or base.escenarios,
    )


def enrutar(
    nombre_facultad: str,
    catalogo: dict[str, str],
    perfiles: dict[str, PerfilFacultad],
) -> str:
    """Devuelve el `id` del perfil de la facultad; si no la reconoce, `general`."""
    sigla = catalogo.get(normalizar(nombre_facultad))
    if sigla is not None:
        for perfil in perfiles.values():
            if perfil.facultad == sigla:
                return perfil.id
    return "general"
