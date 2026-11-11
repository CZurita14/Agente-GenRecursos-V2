"""Plantilla HTML institucional (UTI) para las tareas y herramientas que se suben a Canvas.

Canvas descarta <style> y <script> al pegar en una página: todo lo visible lleva estilos en línea.
Las partes interactivas (casillas, autoevaluación) siguen funcionando al abrir el archivo, y al
pegarlo en Canvas queda el contenido sin interacción.
"""
import re
from html import escape

MORADO, MORADO_OSCURO, NARANJA = "#3A1467", "#230C3E", "#F37121"
FUENTE = "Verdana, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

_BOTON = (
    '<table style="width: 100%; max-width: 1000px; margin: 0px auto; border-collapse: separate;"><tbody><tr>'
    '<td style="text-align: center; padding: clamp(14px, 3vw, 20px) 0px;">'
    '<a style="display: inline-block; text-decoration: none; padding: clamp(8px, 2vw, 12px) clamp(16px, 4vw, 24px); '
    f'background-color: #3a1467; color: #ffffff; border-radius: 4px; font-family: LatoExtended, \'Source Sans Pro\', sans-serif; '
    'font-size: clamp(14px, 3vw, 18px); cursor: pointer; border: 1px solid #230c3e;" title="Inicio" '
    # Relativo: desde una página o una tarea del curso en Canvas lleva a la página «inicio» del mismo curso.
    'href="../pages/inicio">Inicio del curso</a></td></tr></tbody></table>'
)
_TH = ("background: #F7F3FB; color: #3a1467; text-align: left; vertical-align: top; "
       "padding: clamp(12px, 2.5vw, 16px) clamp(12px, 3vw, 24px); border-left: 6px solid #3A1467; "
       "border-top: 2px solid #E2E8F0; border-bottom: 1px solid #E4D9F0;")
_TD = ("background: #FCFAFE; vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(12px, 3vw, 24px); "
       "border-bottom: 1px solid #E2E8F0; font-size: clamp(13px, 2.4vw, 14.5px); line-height: 1.75; color: #444444;")
_TD_ULTIMA = _TD.replace("border-bottom: 1px solid #E2E8F0;", "border-radius: 0 0 12px 12px;")

# Estilos en línea para el contenido de la herramienta (Canvas quita la hoja de estilos).
_EN_LINEA = [
    (r"<h2>", '<h2 style="color: #3a1467; font-size: clamp(15px, 3vw, 18px); margin: 18px 0 8px;">'),
    (r"<h3>", '<h3 style="color: #3a1467; font-size: clamp(14px, 2.6vw, 16px); margin: 14px 0 6px;">'),
    (r"<h([4-6])>", r'<h\1 style="color: #6b4a96; margin: 12px 0 6px;">'),
    (r"<section(?=[ >])", '<section style="background: #ffffff; border: 1px solid #E4D9F0; border-radius: 10px; '
                          'padding: 12px 16px; margin: 12px 0;"'),
    (r"<fieldset(?=[ >])", '<fieldset style="background: #ffffff; border: 1px solid #E4D9F0; border-radius: 10px; '
                           'padding: 12px 16px; margin: 12px 0;"'),
    (r"<table>", '<table style="border-collapse: collapse; width: 100%; font-size: 14px;">'),
    (r'<th scope="col">', '<th scope="col" style="background: #F7F3FB; color: #3a1467; border: 1px solid #E4D9F0; '
                          'padding: 6px 8px; text-align: left; vertical-align: top;">'),
    (r"<td>", '<td style="border: 1px solid #E4D9F0; padding: 6px 8px; text-align: left; vertical-align: top;">'),
    (r"<legend>", '<legend style="font-weight: bold; color: #3a1467;">'),
]


def en_linea(html: str) -> str:
    for patron, reemplazo in _EN_LINEA:
        html = re.sub(patron, reemplazo, html)
    return html


def _encabezado(titulo: str) -> str:
    return (f'<tr><th style="{_TH}" scope="row"><span style="display: block; margin-bottom: 4px;">'
            f'<span style="font-size: clamp(15px, 3vw, 18.5px); color: #3a1467;">{escape(titulo)}</span></span></th></tr>')


def _fila(titulo: str, cuerpo_html: str, ultima: bool = False) -> str:
    return _encabezado(titulo) + f'<tr><td style="{_TD_ULTIMA if ultima else _TD}">{cuerpo_html}</td></tr>'


def lista(items: list[str], numerada: bool = False) -> str:
    etiqueta = "ol" if numerada else "ul"
    return (f'<{etiqueta} style="margin: 0; padding-left: 22px;">'
            + "".join(f'<li style="margin: 0 0 6px 0;">{x}</li>' for x in items) + f"</{etiqueta}>")


def documento(*, titulo_pagina: str, nombre_actividad: str, secciones: list[tuple[str, str]], estilo: str,
              script: str) -> str:
    """Página completa con la tabla institucional. `secciones`: (título, HTML ya escapado)."""
    filas = "".join(_fila(t, c, ultima=(k == len(secciones) - 1)) for k, (t, c) in enumerate(secciones))
    tabla = (
        f'<table style="width: 100%; max-width: 1000px; margin: 0px auto 28px; border-collapse: separate; '
        f'table-layout: fixed; border-radius: 12px; font-family: {FUENTE}; color: #252525; line-height: 1.65; '
        f'border: 1px solid #cbd5e0;"><thead><tr><th style="background: linear-gradient(135deg, {MORADO} 0%, '
        f'{MORADO_OSCURO} 100%); color: #ffffff; text-align: left; vertical-align: top; '
        f'padding: clamp(18px, 3.5vw, 30px) clamp(12px, 3vw, 24px); border-bottom: 5px solid {NARANJA}; '
        f'border-radius: 12px 12px 0 0;" scope="col"><span style="display: block; margin-bottom: 10px;">'
        f'<span style="font-size: clamp(18px, 4.2vw, 26px);">{escape(nombre_actividad)}</span></span></th></tr></thead>'
        f"<tbody>{filas}</tbody></table>"
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"es\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{escape(titulo_pagina)}</title><style>{estilo}</style></head>"
        f'<body style="margin: 0; padding: 0 12px; background: #ffffff;">{_BOTON}<main>{tabla}</main>'
        f"<script>{script}</script></body></html>"
    )
