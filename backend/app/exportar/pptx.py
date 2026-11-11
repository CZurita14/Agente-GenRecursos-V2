"""Exportación de la presentación de clase a PowerPoint (.pptx) con python-pptx."""
from io import BytesIO

from app.exportar.presentacion import credito_imagen, legible, nombre_ambito
from app.silabo.contexto import ContextoClase

PIE = "Recurso generado con asistencia de IA y revisado por el docente"
_ANCHO, _ALTO = 12192000, 6858000  # 16:9 en EMU
_MARGEN = 457200  # 0,5 pulgadas


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
    # Las cuatro medidas juntas: si solo se fijan left/width, python-pptx deja top y height en 0.
    cuerpo.left, cuerpo.top = izquierda, arriba
    cuerpo.width, cuerpo.height = ancho_texto - (izquierda - _MARGEN), alto
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
    s.shapes.title.text = legible(datos["titulo"])
    s.placeholders[1].text = (f"{contexto.asignatura} · {nombre_ambito(contexto.clase_id)} · "
                              f"{contexto.fecha:%d/%m/%Y}")

    for d in datos["diapositivas"]:
        s = prs.slides.add_slide(contenido)
        s.shapes.title.text = legible(d["titulo"])
        cuerpo = s.placeholders[1].text_frame
        cuerpo.word_wrap = True
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
    s.shapes.title.text = "Datos del recurso"
    cuerpo = s.placeholders[1].text_frame
    cuerpo.text = f"{contexto.asignatura} · {nombre_ambito(contexto.clase_id)} · {contexto.fecha:%d/%m/%Y}"
    lineas = [legible(f"{r.id}: {r.texto}") for r in contexto.ra]
    lineas.append(f"Política de IA: {contexto.politica_ia or 'No indicada en el sílabo'}")
    creditos = sorted({credito_imagen(d["imagen"]) for d in datos["diapositivas"]
                       if (d.get("imagen") or {}).get("hash") in imagenes})
    lineas += creditos + [PIE]
    for linea in lineas:
        p = cuerpo.add_paragraph()
        p.text = linea
        p.font.size = Pt(12 if len(lineas) > 8 else 14)

    salida = BytesIO()
    prs.save(salida)
    return salida.getvalue()
