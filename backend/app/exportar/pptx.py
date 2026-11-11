"""Exportación de la presentación de clase a PowerPoint (.pptx) con python-pptx."""
from io import BytesIO

from app.exportar.presentacion import legible, nombre_ambito
from app.silabo.contexto import ContextoClase

PIE = "Recurso generado con asistencia de IA y revisado por el docente"
_ANCHO, _ALTO = 12192000, 6858000  # 16:9 en EMU


def exportar_pptx(recurso: dict, contexto: ContextoClase) -> bytes:
    """Portada, una diapositiva por cada una del recurso (con notas del docente) y cierre con los datos."""
    from pptx import Presentation
    from pptx.util import Pt

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
        for k, punto in enumerate(d["puntos"]):
            parrafo = cuerpo.paragraphs[0] if k == 0 else cuerpo.add_paragraph()
            parrafo.text = legible(punto)
            parrafo.font.size = Pt(20)
        if d.get("notas", "").strip():
            s.notes_slide.notes_text_frame.text = legible(d["notas"])

    s = prs.slides.add_slide(contenido)
    s.shapes.title.text = "Datos del recurso"
    cuerpo = s.placeholders[1].text_frame
    cuerpo.text = f"{contexto.asignatura} · {nombre_ambito(contexto.clase_id)} · {contexto.fecha:%d/%m/%Y}"
    for linea in ([legible(f"{r.id}: {r.texto}") for r in contexto.ra]
                  + [f"Política de IA: {contexto.politica_ia or 'No indicada en el sílabo'}", PIE]):
        p = cuerpo.add_paragraph()
        p.text = linea
        p.font.size = Pt(14)

    salida = BytesIO()
    prs.save(salida)
    return salida.getvalue()
