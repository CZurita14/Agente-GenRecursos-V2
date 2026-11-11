"""Exportación de la presentación de clase a PowerPoint (.pptx) con python-pptx."""
from io import BytesIO

from app.exportar.presentacion import credito_imagen, legible, nombre_ambito
from app.silabo.contexto import ContextoClase

PIE = "Recurso generado con asistencia de IA y revisado por el docente"
_ANCHO, _ALTO = 12192000, 6858000  # 16:9 en EMU
_MARGEN = 457200  # 0,5 pulgadas
_PULGADA = 914400
# Colores de la plantilla institucional (los mismos del HTML).
_MORADO, _NARANJA, _GRIS = (0x3A, 0x14, 0x67), (0xF3, 0x71, 0x21), (0x59, 0x59, 0x59)
# Las posiciones de la plantilla base de python-pptx son para 4:3; en 16:9 se fijan aquí.
_TITULO_Y, _TITULO_ALTO = int(0.35 * _PULGADA), int(1.0 * _PULGADA)
_CUERPO_Y = int(1.5 * _PULGADA)
_SANGRIA = 91440  # Margen interno del cuadro de texto: las líneas naranjas arrancan con el texto.


def _ubicar(forma, x: int, y: int, ancho: int, alto: int) -> None:
    """Fija las cuatro medidas juntas: con solo algunas, python-pptx deja las demás en 0."""
    forma.left, forma.top, forma.width, forma.height = int(x), int(y), int(ancho), int(alto)


def _color(rgb):
    from pptx.dml.color import RGBColor
    return RGBColor(*rgb)


def _barra(diapositiva, x: int, y: int, ancho: int, alto: int, rgb) -> None:
    from pptx.enum.shapes import MSO_SHAPE
    barra = diapositiva.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, ancho, alto)
    barra.fill.solid()
    barra.fill.fore_color.rgb = _color(rgb)
    barra.line.fill.background()
    barra.shadow.inherit = False


def _titulo(diapositiva, texto: str) -> None:
    """Título de diapositiva alineado con el cuerpo, a lo ancho de 16:9 y en el morado institucional."""
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Pt
    titulo = diapositiva.shapes.title
    _ubicar(titulo, _MARGEN, _TITULO_Y, _ANCHO - 2 * _MARGEN, _TITULO_ALTO)
    marco = titulo.text_frame
    marco.word_wrap, marco.vertical_anchor = True, MSO_ANCHOR.MIDDLE
    marco.text = texto
    for p in marco.paragraphs:
        p.alignment = PP_ALIGN.LEFT
        p.font.size, p.font.bold, p.font.color.rgb = Pt(30 if len(texto) <= 55 else 26), True, _color(_MORADO)
    _barra(diapositiva, _MARGEN + _SANGRIA, _TITULO_Y + _TITULO_ALTO, int(1.2 * _PULGADA), int(0.05 * _PULGADA), _NARANJA)


def _cuerpo(diapositiva):
    cuerpo = diapositiva.placeholders[1]
    _ubicar(cuerpo, _MARGEN, _CUERPO_Y, _ANCHO - 2 * _MARGEN, _ALTO - _CUERPO_Y - _MARGEN)
    cuerpo.text_frame.word_wrap = True
    return cuerpo


def _portada(diapositiva, titulo: str, asignatura: str, detalle: str) -> None:
    """Franja morada a la izquierda; título grande, línea naranja y debajo la asignatura y la sesión."""
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Pt
    _barra(diapositiva, 0, 0, int(0.35 * _PULGADA), _ALTO, _MORADO)
    x, ancho = int(1.0 * _PULGADA), _ANCHO - int(1.8 * _PULGADA)
    forma = diapositiva.shapes.title
    _ubicar(forma, x, int(1.2 * _PULGADA), ancho, int(2.9 * _PULGADA))
    marco = forma.text_frame
    marco.word_wrap, marco.vertical_anchor = True, MSO_ANCHOR.BOTTOM
    marco.text = titulo
    tam = 40 if len(titulo) <= 50 else 34 if len(titulo) <= 90 else 28
    for p in marco.paragraphs:
        p.alignment = PP_ALIGN.LEFT
        p.font.size, p.font.bold, p.font.color.rgb = Pt(tam), True, _color(_MORADO)
    _barra(diapositiva, x + _SANGRIA, int(4.25 * _PULGADA), int(1.6 * _PULGADA), int(0.07 * _PULGADA), _NARANJA)
    sub = diapositiva.placeholders[1]
    _ubicar(sub, x, int(4.5 * _PULGADA), ancho, int(1.4 * _PULGADA))
    marco = sub.text_frame
    marco.word_wrap, marco.vertical_anchor = True, MSO_ANCHOR.TOP
    marco.text = asignatura
    marco.add_paragraph().text = detalle
    for k, p in enumerate(marco.paragraphs):
        p.alignment = PP_ALIGN.LEFT
        p.font.size, p.font.bold, p.font.color.rgb = Pt(22 if k == 0 else 18), k == 0, _color(_GRIS)


def _con_imagen(diapositiva, datos: bytes) -> bool:
    """Texto a la izquierda e imagen a la derecha, sin deformarla. False si la imagen no se puede leer."""
    from pptx.util import Emu
    cuerpo = diapositiva.placeholders[1]
    izquierda, arriba = cuerpo.left, cuerpo.top
    alto = _ALTO - arriba - _MARGEN
    ancho_texto = int((_ANCHO - 2 * _MARGEN) * 0.55)
    x_imagen = _MARGEN + ancho_texto + _MARGEN // 2
    ancho_max = _ANCHO - x_imagen - _MARGEN
    try:
        foto = diapositiva.shapes.add_picture(BytesIO(datos), Emu(x_imagen), Emu(arriba))
    except Exception:  # Formato que python-pptx no lee (p. ej. webp): la diapositiva queda sin imagen.
        return False
    escala = min(ancho_max / foto.width, alto / foto.height)
    foto.width, foto.height = int(foto.width * escala), int(foto.height * escala)
    foto.left = x_imagen + (ancho_max - foto.width) // 2
    _ubicar(cuerpo, izquierda, arriba, ancho_texto - (izquierda - _MARGEN), alto)
    return True


def exportar_pptx(recurso: dict, contexto: ContextoClase, imagenes: dict[str, bytes] | None = None) -> bytes:
    """Portada, una diapositiva por cada una del recurso (con notas e imagen) y cierre con los datos."""
    from pptx import Presentation
    from pptx.util import Pt

    imagenes = imagenes or {}
    datos = recurso["contenido"]["presentacion"]
    prs = Presentation()
    prs.slide_width, prs.slide_height = _ANCHO, _ALTO
    portada, contenido = prs.slide_layouts[0], prs.slide_layouts[1]

    s = prs.slides.add_slide(portada)
    _portada(s, legible(datos["titulo"]), contexto.asignatura,
             f"{nombre_ambito(contexto.clase_id)} · {contexto.fecha:%d/%m/%Y}")

    for d in datos["diapositivas"]:
        s = prs.slides.add_slide(contenido)
        _titulo(s, legible(d["titulo"]))
        cuerpo = _cuerpo(s).text_frame
        for k, punto in enumerate(d["puntos"]):
            parrafo = cuerpo.paragraphs[0] if k == 0 else cuerpo.add_paragraph()
            parrafo.text = legible(punto)
            parrafo.font.size = Pt(20)
        notas = [legible(d["notas"])] if d.get("notas", "").strip() else []
        imagen = d.get("imagen") or {}
        if imagen.get("hash") in imagenes and _con_imagen(s, imagenes[imagen["hash"]]):
            notas.append(credito_imagen(imagen))
        if notas:
            s.notes_slide.notes_text_frame.text = "\n\n".join(notas)

    s = prs.slides.add_slide(contenido)
    _titulo(s, "Datos del recurso")
    cuerpo = _cuerpo(s).text_frame
    cuerpo.text = f"{contexto.asignatura} · {nombre_ambito(contexto.clase_id)} · {contexto.fecha:%d/%m/%Y}"
    lineas = [legible(f"{r.id}: {r.texto}") for r in contexto.ra]
    lineas.append(f"Política de IA: {contexto.politica_ia or 'No indicada en el sílabo'}")
    creditos = sorted({credito_imagen(d["imagen"]) for d in datos["diapositivas"]
                       if (d.get("imagen") or {}).get("hash") in imagenes})
    lineas += creditos + [PIE]
    for linea in lineas:
        cuerpo.add_paragraph().text = linea
    for p in cuerpo.paragraphs:  # Incluye la primera línea (asignatura y sesión), que no tenía tamaño.
        p.font.size = Pt(12 if len(lineas) > 8 else 14)

    salida = BytesIO()
    prs.save(salida)
    return salida.getvalue()
