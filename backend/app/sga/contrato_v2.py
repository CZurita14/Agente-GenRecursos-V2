"""Contrato v2.0 del sílabo (docs/api-silabo/silabo-api.v2.schema.json) hacia el formato interno v1.0.

El v2.0 agrega los apartados que valora la escala de evaluación de sílabos. La generación de
recursos sigue usando el formato v1.0: este adaptador convierte las dos claves que cambiaron de
forma (`metodologias` y `pis`) y quita los nulos de `creditos` y `horas`. El resto de claves nuevas
las descarta después la lista blanca del traductor. Nunca muta la entrada ni falla con tipos raros:
lo que no reconoce lo deja igual para que lo informe la validación.
"""
import copy
import unicodedata

VERSION = "2.0"

# III.3: la plantilla de sílabo 2026 ofrece 5 metacompetencias fijas y el docente marca una. El SGA puede
# enviarlas con otra grafía (el PDF dice «e ia»): se comparan sin mayúsculas ni tildes y se guardan así.
METACOMPETENCIAS = (
    "Innovación y emprendimiento sostenible con impacto territorial",
    "Gobernanza ética de tecnologías digitales e IA",
    "Liderazgo colaborativo e intercultural para la transformación territorial",
    "Metacognición estratégica y proyecto ético de vida",
    "Pensamiento sociocrítico y sistémico para la toma de decisiones estratégicas",
)


def _plano(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.upper().split())


_POR_CLAVE = {_plano(m): m for m in METACOMPETENCIAS}


def metacompetencia_oficial(texto) -> str | None:
    """Forma oficial de la metacompetencia; "" si viene vacía (ND); None si no es del catálogo."""
    if not isinstance(texto, str):
        return None
    return "" if not texto.strip() else _POR_CLAVE.get(_plano(texto))

NOMBRE_METODOLOGIA = {
    "aprendizaje_basado_problemas": "Aprendizaje basado en problemas (ABP)",
    "aprendizaje_basado_retos": "Aprendizaje basado en retos (ABR)",
    "aprendizaje_servicio": "Aprendizaje servicio (APS)",
    "aprendizaje_cooperativo": "Aprendizaje cooperativo (AC)",
    "estudio_caso": "Estudio de caso",
    "cocreacion_dialogo_saberes": "Cocreación y diálogo de saberes",
    "rutinas_destrezas_pensamiento": "Rutinas y destrezas de pensamiento",
}
CLASE_INVERTIDA = "Clase invertida"


RAIZ_OBLIGATORIA = (
    "contrato", "facultad", "carrera", "periodo", "proyecto_formativo", "competencia_perfil", "competencia_pf",
    "metacompetencia", "habilidades_blandas", "ejes_transversales", "inclusion", "contribucion_perfil",
    "resultados_aprendizaje", "problema", "pis", "metodologias", "momentos", "rubrica_producto_final",
    "evaluacion", "bibliografia",
)


def reglas(crudo: dict) -> list[str]:
    """Reglas propias del v2.0 que no cubre la validación del v1.0 (rutas, nunca valores).

    1. Las claves obligatorias de la raíz vienen.
    2. Los RA se numeran RA1, RA2, ... en orden y sin saltos (la escala valora RA1 a RA4).
    3. Cada tipo de metodología complementaria aparece una vez, salvo `otra`.
    4. La metacompetencia, si viene, es una de las 5 del catálogo institucional.
    """
    fallos = [f"{k}: falta" for k in RAIZ_OBLIGATORIA if k not in crudo]
    if "metacompetencia" in crudo and metacompetencia_oficial(crudo["metacompetencia"]) is None:
        fallos.append("metacompetencia: no es una de las 5 del catálogo institucional")
    ras = crudo.get("resultados_aprendizaje")
    if isinstance(ras, list):
        for i, r in enumerate(ras):
            if not isinstance(r, dict) or r.get("id") != f"RA{i + 1}":
                fallos.append(f"resultados_aprendizaje[{i}].id: debe ser RA{i + 1}")
    met = crudo.get("metodologias")
    comp = met.get("complementarias") if isinstance(met, dict) else None
    vistos = set()
    for i, m in enumerate(comp if isinstance(comp, list) else []):
        tipo = m.get("tipo") if isinstance(m, dict) else None
        if tipo != "otra" and tipo in vistos:
            fallos.append(f"metodologias.complementarias[{i}].tipo: repetido")
        vistos.add(tipo)
    return fallos


def es_v2(crudo) -> bool:
    return isinstance(crudo, dict) and crudo.get("contrato") == VERSION


def _metodologias(valor):
    if not isinstance(valor, dict):
        return valor
    nombres = [CLASE_INVERTIDA]
    complementarias = valor.get("complementarias")
    for m in complementarias if isinstance(complementarias, list) else []:
        if not isinstance(m, dict):
            continue
        nombre = m.get("nombre") if isinstance(m.get("nombre"), str) and m["nombre"].strip() else None
        nombre = nombre or NOMBRE_METODOLOGIA.get(m.get("tipo"))
        if nombre and nombre not in nombres:
            nombres.append(nombre)
    return nombres


def a_v1(crudo: dict) -> dict:
    """Copia del sílabo v2.0 con la forma del v1.0 en las claves que cambiaron."""
    d = copy.deepcopy(crudo)
    d.pop("contrato", None)
    oficial = metacompetencia_oficial(d.get("metacompetencia"))
    if oficial is not None and "metacompetencia" in d:
        d["metacompetencia"] = oficial
    if "metodologias" in d:
        d["metodologias"] = _metodologias(d["metodologias"])
    pis = d.get("pis")
    if isinstance(pis, dict) and pis.get("aplica") is False:
        d.pop("pis")
    elif isinstance(pis, dict):
        d["pis"] = {k: pis[k] for k in ("nombre", "aporte") if k in pis}
    pf = d.get("proyecto_formativo")
    if isinstance(pf, dict):
        for k in ("creditos", "horas"):
            if k in pf and pf[k] is None:
                pf.pop(k)
    return d
