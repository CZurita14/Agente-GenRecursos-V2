"""leer_silabo: PDF institucional → SilaboUTI, sin IA y sin datos personales (spec §7)."""
from pydantic import ValidationError

from app.silabo.lector.cierre import leer_bibliografia, leer_rubrica_final
from app.silabo.lector.entrada import abrir, segmentar, tablas
from app.silabo.lector.errores import SilaboIlegible
from app.silabo.lector.momentos import leer_momentos
from app.silabo.lector.presentacion import leer_cabecera
from app.silabo.modelo import SilaboUTI


def leer_silabo(datos: bytes) -> SilaboUTI:
    """No escribe el PDF en disco: borrar el archivo subido le corresponde a quien lo recibe (P4).

    Cualquier error interno se convierte en SilaboIlegible sin su mensaje original,
    que podría contener texto del PDF.
    """
    try:
        return _leer(datos)
    except SilaboIlegible:
        raise
    except Exception:
        raise SilaboIlegible("El sílabo tiene un formato que no se pudo leer.") from None


def _leer(datos: bytes) -> SilaboUTI:
    with abrir(datos) as pdf:
        secciones = segmentar(pdf)

        def tablas_de(nombre: str) -> list:
            return [t for pagina in secciones[nombre] for t in tablas(pagina)]

        def texto_de(nombre: str) -> str:
            return "\n".join(pagina.extract_text() or "" for pagina in secciones[nombre])

        cabecera = leer_cabecera(texto_de("portada"), tablas_de("II"), tablas_de("III"))
        momentos = leer_momentos(tablas_de("IV"), cabecera["periodo"]["inicio"])
        rubrica_final = leer_rubrica_final(tablas_de("V"))
        bibliografia = leer_bibliografia(texto_de("VI"))

    pf = cabecera["proyecto_formativo"]
    faltan = [campo for campo, valor in (("facultad", cabecera["facultad"]), ("carrera", cabecera["carrera"]),
                                         ("nombre del proyecto formativo", pf["nombre"]),
                                         ("código del proyecto formativo", pf["codigo"])) if not valor]
    if not any(m["sesiones"] for m in momentos):
        faltan.append("un momento con al menos una sesión fechada")
    if faltan:
        raise SilaboIlegible("Falta en el sílabo: " + ", ".join(faltan) + ".")
    try:
        return SilaboUTI.model_validate({**cabecera, "momentos": momentos,
                                         "rubrica_producto_final": rubrica_final, "bibliografia": bibliografia})
    except ValidationError as error:
        # Solo los nombres de los campos: el valor podría contener texto del PDF.
        campos = sorted({".".join(str(p) for p in e["loc"]) for e in error.errors()})
        raise SilaboIlegible("Campos que no se pudieron leer: " + ", ".join(campos[:5]) + ".") from None
