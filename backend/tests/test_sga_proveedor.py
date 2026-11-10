"""Proveedor SGA: interfaz, traductor de lista blanca y SGA simulado (Tarea 2)."""
import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.sga import (CredencialesInvalidas, IdentidadSGA, MateriaSGA, SGANoDisponible,
                     SilaboNoDisponible, a_contrato, crear_proveedor, separar_codigo)
from app.sga.simulado import ProveedorSimulado
from app.sga.traductor import arbol_esquema
from app.silabo.integridad import cargar_silabo

RAIZ = Path(__file__).resolve().parents[2]
DOCS = RAIZ / "docs" / "api-silabo"
SGA = Path(__file__).parent / "fixtures" / "sga"

# Claves de prueba (solo existen aquí; los fixtures guardan su sha256).
CLAVES = {"docente.uno": "clave-prueba-uno", "docente.dos": "clave-prueba-dos"}


def _json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


@pytest.fixture
def sga() -> ProveedorSimulado:
    return ProveedorSimulado(SGA)


def test_simulado_autentica_y_lista(sga):
    ident, permiso = sga.autenticar("docente.uno", CLAVES["docente.uno"])
    assert isinstance(ident, IdentidadSGA) and ident.usuario == "docente.uno"
    esperadas = [MateriaSGA(**m) for m in _json(SGA / "materias" / "docente.uno.json")]
    assert sga.listar_materias(permiso) == esperadas
    assert len(esperadas) == 3
    assert esperadas[0].codigo_pf == esperadas[1].codigo_pf
    assert {esperadas[0].paralelo, esperadas[1].paralelo} == {"1", "2"}
    _, p2 = sga.autenticar("docente.dos", CLAVES["docente.dos"])
    assert len(sga.listar_materias(p2)) == 1


def test_clave_erronea_y_usuario_inexistente_mismo_mensaje(sga):
    with pytest.raises(CredencialesInvalidas) as a:
        sga.autenticar("docente.uno", "otra-clave")
    with pytest.raises(CredencialesInvalidas) as b:
        sga.autenticar("no.existe", "otra-clave")
    assert str(a.value) == str(b.value)
    assert "docente.uno" not in str(a.value) and "no.existe" not in str(b.value)


def test_permiso_y_identidad_no_guardan_la_clave(sga):
    ident, permiso = sga.autenticar("docente.uno", CLAVES["docente.uno"])
    clave = CLAVES["docente.uno"]
    assert clave not in repr(ident) and clave not in repr(permiso) and clave not in repr(vars(sga))
    assert clave not in repr(getattr(permiso, "__dict__", {}))


def test_obtener_silabo_entrega_crudo_con_privados_y_se_traduce(sga):
    _, permiso = sga.autenticar("docente.uno", CLAVES["docente.uno"])
    for m in sga.listar_materias(permiso):
        crudo = sga.obtener_silabo(permiso, m)
        assert {"docente", "correo", "firmas", "cedula"} <= crudo.keys()
        limpio = a_contrato(crudo)
        assert cargar_silabo(limpio).proyecto_formativo.codigo == m.codigo_pf


def test_silabo_inexistente(sga):
    _, permiso = sga.autenticar("docente.uno", CLAVES["docente.uno"])
    m = MateriaSGA("1", "Z99-ZZZZ-9-99999-9999", "1", "n", "c", "ACTIVA")
    with pytest.raises(SilaboNoDisponible):
        sga.obtener_silabo(permiso, m)


def test_traductor_descarta_privados():
    crudo = _json(SGA / "sga_silabos" / "S91-SIMU-3-90001-9001.json")
    assert {"docente", "correo", "firmas", "cedula"} <= crudo.keys()
    # También dentro de objetos anidados y de elementos de listas.
    crudo["proyecto_formativo"]["cedula"] = "0000000000"
    crudo["momentos"][0]["docente"] = "MARCA-PRIVADA"
    crudo["momentos"][0]["sesiones"][0]["correo"] = "MARCA-PRIVADA"
    limpio = a_contrato(crudo)
    assert not {"docente", "correo", "firmas", "cedula"} & limpio.keys()
    assert "cedula" not in limpio["proyecto_formativo"]
    assert "docente" not in limpio["momentos"][0]
    assert "correo" not in limpio["momentos"][0]["sesiones"][0]
    salida = json.dumps(limpio)
    for marca in ("MARCA-PRIVADA", "FIRMA-FALSA", "falso.privado", "Docente Falso", "0000000000"):
        assert marca not in salida
    cargar_silabo(limpio)
    assert "docente" in crudo  # no muta la entrada


def test_traductor_no_inventa_claves_ausentes():
    assert a_contrato({"facultad": "X", "docente": "falso"}) == {"facultad": "X"}


def test_arbol_esquema_es_el_del_archivo():
    esquema = _json(DOCS / "silabo-api.schema.json")
    assert arbol_esquema() == arbol_esquema(esquema)
    assert "proyecto_formativo" in arbol_esquema()


@pytest.mark.parametrize("texto,esperado", [
    ("[12345] A99-AAAA-9-99999-9999 PARALELO 1".replace("A99-AAAA-9-99999-9999", "B26-SOFT-3-56146-1727"),
     ("12345", "B26-SOFT-3-56146-1727", "1")),
    ("[7] S91-SIMU-3-90001-9001 PARALELO 12", ("7", "S91-SIMU-3-90001-9001", "12")),
])
def test_separar_codigo(texto, esperado):
    assert separar_codigo(texto) == esperado


@pytest.mark.parametrize("texto", [
    "12345 B26-SOFT-3-56146-1727 PARALELO 1",      # sin corchetes
    "[12345] B26-SOFT-3-56146 PARALELO 1",         # código incompleto
    "[12345] B26-SOFT-3-56146-1727",               # sin paralelo
    "",
])
def test_separar_codigo_invalido(texto):
    with pytest.raises(ValueError) as e:
        separar_codigo(texto)
    assert texto not in str(e.value) or texto == ""


def test_real_pendiente():
    with pytest.raises(SGANoDisponible, match="pendiente de TI"):
        crear_proveedor(SimpleNamespace(sga_proveedor="real", sga_simulado_dir=None))


def test_crear_simulado_requiere_directorio():
    with pytest.raises(SGANoDisponible):
        crear_proveedor(SimpleNamespace(sga_proveedor="simulado", sga_simulado_dir=None))
    assert isinstance(crear_proveedor(SimpleNamespace(sga_proveedor="simulado", sga_simulado_dir=SGA)),
                      ProveedorSimulado)


def test_directorio_inexistente_no_disponible(tmp_path):
    with pytest.raises(SGANoDisponible):
        ProveedorSimulado(tmp_path / "nada").autenticar("a", "b")


def test_config_tiene_los_campos_del_sga():
    from app.config import Ajustes
    c = Ajustes(database_url="x", llm_base_url="x", llm_model="x", entorno="desarrollo",
                _env_file=None)
    assert c.sga_proveedor == "real" and c.sga_simulado_dir is None and c.sga_timeout_s == 15


# --- Esquemas de materias y autenticación (sin `jsonschema`: se leen las propias claves) ---

def _verifica(esquema: dict, elementos: list[dict], campos: set[str]):
    props = esquema["properties"]
    assert esquema["additionalProperties"] is False
    assert set(esquema["required"]) <= set(props)
    assert set(props) == campos
    for e in elementos:
        assert set(esquema["required"]) <= e.keys()
        assert not e.keys() - props.keys()
        for k, v in e.items():
            assert isinstance(v, str) and v
            patron = props[k].get("pattern")
            if patron:
                import re
                assert re.search(patron, v), k


def test_esquema_materias():
    esquema = _json(DOCS / "materias-api.schema.json")
    assert esquema["type"] == "array"
    campos = {f.name for f in dataclasses.fields(MateriaSGA)}
    ejemplo = _json(DOCS / "ejemplo-materias.json")
    fixtures = [m for f in (SGA / "materias").glob("*.json") for m in _json(f)]
    assert ejemplo and fixtures
    _verifica(esquema["items"], ejemplo + fixtures, campos)
    assert esquema["items"]["required"] and set(esquema["items"]["required"]) == campos


def test_esquema_autenticacion():
    esquema = _json(DOCS / "auth-sga.schema.json")
    campos = {f.name for f in dataclasses.fields(IdentidadSGA)}
    ejemplo = _json(DOCS / "ejemplo-auth.json")
    usuarios = [{k: u[k] for k in campos} for u in _json(SGA / "usuarios.json")["usuarios"]]
    _verifica(esquema, [ejemplo] + usuarios, campos)
    assert set(esquema["required"]) == campos
    assert "clave" not in esquema["properties"]


def test_silabos_del_simulado_cumplen_contrato():
    for f in (SGA / "sga_silabos").glob("*.json"):
        crudo = _json(f)
        s = cargar_silabo(a_contrato(crudo))
        assert s.proyecto_formativo.codigo == f.stem
        assert s.proyecto_formativo.codigo.startswith("S91-SIMU")


def test_usuarios_guardan_hash_no_clave():
    for u in _json(SGA / "usuarios.json")["usuarios"]:
        assert set(u) == {"usuario", "sha256", "correo", "nombre"}
        assert len(u["sha256"]) == 64
        assert CLAVES[u["usuario"]] not in json.dumps(u)


def test_traductor_filtra_claves_extra_en_nodos_antes_libres():
    """pis, bibliografia, horas y horario[] traen una clave privada: se descarta y el sílabo carga."""
    crudo = _json(SGA / "sga_silabos" / "S91-SIMU-3-90001-9001.json")
    pf = crudo["proyecto_formativo"]
    crudo["pis"] = {"nombre": "PIS simulado", "aporte": "aporte simulado", "contacto": "MARCA-PRIVADA"}
    crudo["bibliografia"] = {"basica": ["libro"], "complementaria": [], "cedula": "MARCA-PRIVADA"}
    pf["horas"]["docente"] = "MARCA-PRIVADA"
    pf["horario"] = [{"dia": "lunes", "inicio": "08:00", "fin": "09:00", "correo": "MARCA-PRIVADA"}]
    limpio = a_contrato(crudo)
    assert "MARCA-PRIVADA" not in json.dumps(limpio)
    assert limpio["pis"] == {"nombre": "PIS simulado", "aporte": "aporte simulado"}
    assert limpio["bibliografia"] == {"basica": ["libro"], "complementaria": []}
    assert "docente" not in limpio["proyecto_formativo"]["horas"]
    assert limpio["proyecto_formativo"]["horario"] == [{"dia": "lunes", "inicio": "08:00", "fin": "09:00"}]
    cargar_silabo(limpio)
