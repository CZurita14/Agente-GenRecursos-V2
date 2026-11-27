"""leer_silabo: PDF institucional → SilaboUTI, sin IA y sin datos personales (spec §7)."""
from pydantic import ValidationError

from ciencia_datos.lector_pdf.cierre import leer_bibliografia, leer_rubrica_final
from ciencia_datos.lector_pdf.entrada import abrir, segmentar, tablas
from ciencia_datos.lector_pdf.errores import SilaboIlegible
from ciencia_datos.lector_pdf.momentos import leer_momentos
from ciencia_datos.lector_pdf.plantilla_2026 import leer_apartados_2026
from ciencia_datos.lector_pdf.presentacion import leer_cabecera
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


def leer_crudo(datos: bytes) -> tuple[dict, dict]:
    """Sílabo como dict (antes de validar el modelo) y los apartados de la plantilla 2026."""
    with abrir(datos) as pdf:
        secciones = segmentar(pdf)

        def tablas_de(nombre: str) -> list:
            return [t for pagina in secciones[nombre] for t in tablas(pagina)]

        def texto_de(nombre: str) -> str:
            return "\n".join(pagina.extract_text() or "" for pagina in secciones[nombre])

        cabecera = leer_cabecera(texto_de("portada"), tablas_de("II"), tablas_de("III"))
        apartados = leer_apartados_2026(tablas_de("II"), tablas_de("III"), texto_de("III"))
        momentos = leer_momentos(tablas_de("IV"), cabecera["periodo"]["inicio"])
        rubrica_final = leer_rubrica_final(tablas_de("V"))
        bibliografia = leer_bibliografia(texto_de("VI"))

    pf = cabecera["proyecto_formativo"]
    faltan = [campo for campo, valor in (("facultad", cabecera["facultad"]), ("carrera", cabecera["carrera"]),
                                         ("nombre del proyecto formativo", pf["nombre"]),
                                         ("código del proyecto formativo", pf["codigo"])) if not valor]
    if not any(s["fecha"] for m in momentos for s in m["sesiones"]):
        faltan.append("un momento con al menos una sesión fechada")
    if faltan:
        raise SilaboIlegible("Falta en el sílabo: " + ", ".join(faltan) + ".")
    return ({**cabecera, "momentos": momentos, "rubrica_producto_final": rubrica_final, "bibliografia": bibliografia},
            apartados)


def _leer(datos: bytes) -> SilaboUTI:
    crudo, _ = leer_crudo(datos)
    try:
        return SilaboUTI.model_validate(crudo)
    except ValidationError as error:
        # Solo los nombres de los campos: el valor podría contener texto del PDF.
        campos = sorted({".".join(str(p) for p in e["loc"]) for e in error.errors()})
        raise SilaboIlegible("Campos que no se pudieron leer: " + ", ".join(campos[:5]) + ".") from None
