"""HTML autónomo para Canvas (spec §13): un solo archivo, sin CDN ni recursos externos.

Seguridad: el contenido viene del modelo y del docente, así que TODO texto pasa por
`html.escape`. El JavaScript es fijo (no lleva datos del recurso): lee atributos del DOM ya
escapados. Lo que el estudiante marca o escribe no se guarda: al recargar vuelve a empezar.

Este archivo es para el estudiante: no lleva claves ni respuestas orientativas, ni ocultas.
Las respuestas se descargan aparte, solo para el docente (app.exportar.documento).
"""
from html import escape
import re
import unicodedata
from urllib.parse import quote

from app.exportar.presentacion import NIVELES, SIN_POLITICA, es_quiz, legible, nombre_ambito, presentar
from app.silabo.contexto import ContextoClase
from app.exportar.institucional import documento, en_linea, lista

PIE = "Recurso generado con asistencia de IA y revisado por el docente"

NOMBRES = {
    "cuestionario": "Cuestionario", "simulacro": "Simulacro", "ficha_clase": "Ficha de clase",
    "repaso_momento": "Repaso integrador", "guia_evidencia": "Guía de la evidencia",
    "estudio_caso": "Estudio de caso", "guia_producto_final": "Guía del producto final",
    "hoja_ruta": "Hoja de ruta del Proyecto Formativo", "autoevaluacion_rubrica": "Autoevaluación con la rúbrica",
    "autoevaluacion_final": "Autoevaluación final", "lista_evidencia": "Lista de verificación de la evidencia",
    "rubrica_momento": "Rúbrica del momento", "rubrica_final": "Rúbrica del producto final",
    "practica_guiada": "Práctica guiada", "tarjetas": "Tarjetas de estudio",
    "guia_autonoma": "Guía de trabajo autónomo", "guion_clase": "Guion de clase (docente)",
    "presentacion": "Presentación (PowerPoint)",
}
# Listas de la presentación que el estudiante va marcando, y textos que descubre cuando quiere.
# Las que tienen una versión con respuestas, solo para el docente.
CON_RESPUESTAS = {"cuestionario", "simulacro", "estudio_caso"}
LISTAS_MARCABLES = {"Autocomprobación", "Autochequeo", "Preguntas de repaso", "Recomendaciones"}
TEXTOS_OCULTABLES = {"Resultado": "Ver el resultado"}
ESTILO = """
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;max-width:860px;margin:0 auto;padding:24px;
color:#2C1547;background:#F4F0F9;line-height:1.5}
header{border-bottom:4px solid #F57021;margin-bottom:24px}h1{margin:0 0 4px}h2{margin-top:28px}
.sub{color:#6E5987;margin:0 0 12px}section,fieldset{background:#fff;border:1px solid #E2D9EE;border-radius:12px;
padding:16px;margin:12px 0}legend{float:left;width:100%;font-weight:700;padding:0;margin:0 0 8px}legend+*{clear:both}label{display:block;padding:6px;border-radius:8px;
cursor:pointer}label:hover{background:#F4F0F9}.fb{display:none;margin-top:8px;padding:8px;border-radius:8px}
.ok{background:#E2F6ED;color:#046446}.mal{background:#FFE7EC;color:#B41437}.ctx{color:#6E5987;font-style:italic}
.tabla{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #E2D9EE;
padding:6px 8px;text-align:left;vertical-align:top}th{background:#F4F0F9}
footer{margin-top:32px;border-top:1px solid #E2D9EE;padding-top:12px;font-size:13px;color:#6E5987}
.chk{display:flex;gap:8px;align-items:flex-start}.chk input{margin-top:5px}.avance{font-weight:700;color:#6E5987}
details{margin:8px 0;padding:8px;background:#F4F0F9;border-radius:8px}summary{cursor:pointer;font-weight:600}
textarea{width:100%;min-height:80px;box-sizing:border-box;padding:8px;border:1px solid #E2D9EE;border-radius:8px;font:inherit}
.nivel{font-weight:700}button{font:inherit;padding:6px 12px;border:1px solid #6E5987;border-radius:8px;background:#fff;cursor:pointer}
@media print{button,textarea{display:none}details{background:none}section,fieldset{break-inside:avoid}}
"""
# Autocorrección, autoevaluación, listas marcables e impresión; todo sale de atributos del DOM.
SCRIPT = """
function resumen() {
  var p = document.querySelector('[data-resumen]');
  if (!p) return;
  var todos = document.querySelectorAll('fieldset[data-autoev]');
  var hechos = document.querySelectorAll('fieldset[data-autoev] input:checked');
  var cuenta = {};
  hechos.forEach(function (i) { var n = i.closest('label').getAttribute('data-nivel'); cuenta[n] = (cuenta[n] || 0) + 1; });
  var partes = Object.keys(cuenta).map(function (n) { return n + ': ' + cuenta[n]; });
  p.textContent = 'Marcaste ' + hechos.length + ' de ' + todos.length + ' indicadores' + (partes.length ? ' · ' + partes.join(' · ') : '');
}
document.querySelectorAll('fieldset[data-autoev]').forEach(function (f) {
  f.addEventListener('change', function (e) {
    var fb = f.querySelector('.fb');
    var subir = e.target.closest('label').getAttribute('data-subir');
    fb.className = 'fb ok';
    fb.textContent = subir ? 'Para subir al siguiente nivel: ' + subir : 'Es el nivel más alto de este indicador.';
    fb.style.display = 'block';
    resumen();
  });
});
document.querySelectorAll('[data-lista]').forEach(function (l) {
  var p = l.querySelector('[data-avance]');
  function contar() {
    var c = l.querySelectorAll('input[type=checkbox]');
    p.textContent = l.querySelectorAll('input[type=checkbox]:checked').length + ' de ' + c.length + ' listos';
  }
  l.addEventListener('change', contar);
  contar();
});
document.querySelectorAll('[data-imprimir]').forEach(function (b) {
  b.addEventListener('click', function () { window.print(); });
});
resumen();
"""
IMPRIMIR = '<p><button type="button" data-imprimir>Imprimir o guardar en PDF</button></p>'


def _sin_prohibidos(texto: str) -> str:
    return re.sub(r'[\x00-\x1f\x7f\\/:*?"<>|;]+', " ", texto)


def nombre_archivo(herramienta: str, ambito_id: str, proyecto: str, formato: str, docente: bool = False) -> str:
    """«Ficha de clase - Momento 2, sesión 1 - Analisis de datos.pdf», sin códigos internos."""
    partes = ["Respuestas"] if docente else []
    partes.append(NOMBRES.get(herramienta, herramienta))
    if ambito_id != "asignatura":
        partes.append(nombre_ambito(ambito_id))
    partes.append(proyecto.strip().capitalize()[:60].strip())
    # El nombre del proyecto viene del sílabo: sin caracteres que el sistema de archivos o la cabecera rechacen.
    limpio = _sin_prohibidos(" - ".join(partes))
    return re.sub(r"\s+", " ", limpio).strip(" .") + "." + formato


def cabecera_descarga(nombre: str) -> str:
    """Content-Disposition con acentos (RFC 6266) y una alternativa ASCII para clientes antiguos."""
    # Se limpia después de normalizar: NFKD convierte, p. ej., «＂» (U+FF02) en una comilla real.
    ascii_ = _sin_prohibidos(unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode())
    return f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nombre, safe='')}"


def _marcable(titulo: str, items, nivel: int) -> str:
    casillas = "".join(f'<label class="chk"><input type="checkbox"> <span>{escape(str(x))}</span></label>' for x in items)
    return (f'<section data-lista><h{nivel}>{escape(titulo)}</h{nivel}><p class="avance" data-avance role="status"></p>'
            f'{casillas}</section>')


def _bloque(b: dict, nivel: int) -> str:
    """Un bloque de la presentación (app.exportar.presentacion); todo texto escapado."""
    titulo = f"<h{nivel}>{escape(b['titulo'])}</h{nivel}>" if b.get("titulo") else ""
    if b["tipo"] == "imagen":  # Sin imágenes externas en el HTML: solo el crédito.
        return f'<p style="font-size: 12px; color: #6b4a96;"><em>{escape(b["credito"])}</em></p>'
    if b["tipo"] == "texto":
        if b.get("titulo") in TEXTOS_OCULTABLES:
            return f"<details><summary>{escape(TEXTOS_OCULTABLES[b['titulo']])}</summary><p>{escape(b['texto'])}</p></details>"
        return f"{titulo}<p>{escape(b['texto'])}</p>"
    if b["tipo"] == "lista" and b.get("titulo") in LISTAS_MARCABLES:
        return _marcable(b["titulo"], b["items"], nivel)
    if b["tipo"] == "lista":
        etiqueta = "ol" if b.get("numerada") else "ul"
        return f"{titulo}<{etiqueta}>" + "".join(f"<li>{escape(x)}</li>" for x in b["items"]) + f"</{etiqueta}>"
    if b["tipo"] == "tabla":
        cabecera = "".join(f'<th scope="col">{escape(c)}</th>' for c in b["columnas"])
        filas = "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in f) + "</tr>" for f in b["filas"])
        return f"{titulo}<div class=\"tabla\"><table><thead><tr>{cabecera}</tr></thead><tbody>{filas}</tbody></table></div>"
    return f"<section>{titulo}{''.join(_bloque(x, min(nivel + 1, 6)) for x in b['bloques'])}</section>"


def _autoevaluacion(c: dict) -> str:
    """Una pregunta por indicador: el estudiante marca su nivel y ve qué le falta para subir."""
    partes = [f"<p>{escape(c['instrucciones'])}</p>"]
    if c.get("titulo"):
        partes.append(f"<h2>Momento {escape(str(c['momento']))} · {escape(c['titulo'])}</h2>")
    partes.append(f"<p><strong>Evidencia:</strong> {escape(c['evidencia'])}</p>"
                  '<p class="avance" data-resumen role="status"></p>')
    for n, f in enumerate(c["indicadores"], 1):
        opciones = "".join(
            f'<label data-nivel="{escape(NIVELES.get(k, k), quote=True)}" '
            f'data-subir="{escape(f["para_subir"].get(k) or "", quote=True)}">'
            f'<input type="radio" name="ind{n}"> <span class="nivel">{escape(NIVELES.get(k, k))}:</span> {escape(f["descriptores"][k])}</label>'
            for k in c["niveles"] if f["descriptores"].get(k))
        partes.append(f'<fieldset data-autoev><legend>{escape(f["indicador"])}</legend>{opciones}'
                      '<div class="fb" role="status"></div></fieldset>')
    return "".join(partes)


def _lista_evidencia(c: dict) -> str:
    """Lista que se va marcando antes de entregar."""
    entregables = "".join(f'<label class="chk"><input type="checkbox"> <span>Tengo listo: {escape(e)}</span></label>'
                          for e in c["entregables"])
    criterios = "".join(
        f'<label class="chk"><input type="checkbox"> <span><strong>{escape(x["indicador"])}:</strong> '
        f'{escape(x["referencia_resolutivo"])}</span></label>' for x in c["items"])
    return (f"<h2>Momento {escape(str(c['momento']))} · {escape(c['titulo'])}</h2>"
            f"<p><strong>Evidencia:</strong> {escape(c['evidencia'])}</p>"
            f'<section data-lista><h2>Antes de entregar, verifica</h2><p class="avance" data-avance role="status"></p>'
            f"{entregables}{criterios}</section>"
            f"<p><strong>Política de IA:</strong> {escape(c.get('politica_ia') or SIN_POLITICA)}</p>")


def _estudio_caso(c: dict) -> str:
    """El estudiante escribe su respuesta; la orientativa va solo en la versión del docente."""
    caso = c["caso"]
    partes = [f"<h2>Caso</h2><p>{escape(caso['caso'])}</p><p><strong>Se relaciona con:</strong> {escape(caso['ra'])}</p>"]
    for n, p in enumerate(caso["preguntas"], 1):
        partes.append(
            f"<section><h3>Pregunta {n} · {escape(NIVELES.get(p['nivel'], p['nivel']))}</h3><p>{escape(p['pregunta'])}</p>"
            f'<textarea aria-label="Tu respuesta a la pregunta {n}" placeholder="Escribe aquí tu respuesta"></textarea></section>')
    return "".join(partes)


INTERACTIVAS = {"autoevaluacion_rubrica": _autoevaluacion, "autoevaluacion_final": _autoevaluacion,
                "lista_evidencia": _lista_evidencia, "estudio_caso": _estudio_caso}


def _cuerpo(herramienta: str, contenido) -> str:
    if es_quiz(contenido):
        return _items(contenido)
    interactiva = INTERACTIVAS.get(herramienta)
    if interactiva and isinstance(contenido, dict):
        try:
            return interactiva(contenido)
        except (KeyError, TypeError, AttributeError):
            pass  # Forma no prevista (p. ej. esquema anterior): se muestra igual, sin interacción.
    return "".join(_bloque(b, 2) for b in presentar(herramienta, contenido))


def _items(items: list[dict]) -> str:
    partes = []
    for n, item in enumerate(items, 1):
        opciones = "".join(f'<label><input type="radio" name="p{n}"> {escape(str(o.get("texto", "")))}</label>'
                           for o in item.get("opciones", []))
        contexto = f'<p class="ctx">{escape(str(item["contexto"]))}</p>' if item.get("contexto") else ""
        partes.append(
            f'<fieldset data-item><legend>Pregunta {n}</legend>{contexto}'
            f'<p><strong>{escape(str(item.get("pregunta", "")))}</strong></p>{opciones}</fieldset>')
    return "".join(partes)


# Para qué sirve cada herramienta e instrucciones de uso (filas de la plantilla institucional).
PROPOSITO = {
    "cuestionario": "Comprobar lo que aprendiste en la clase y detectar qué necesitas repasar.",
    "simulacro": "Practicar con preguntas como las de la evaluación del momento antes de rendirla.",
    "ficha_clase": "Repasar las ideas clave de la clase y aplicarlas en un ejemplo resuelto.",
    "practica_guiada": "Aplicar paso a paso los contenidos de la sesión en ejercicios guiados.",
    "tarjetas": "Memorizar y repasar los conceptos clave de la sesión de forma rápida.",
    "guia_autonoma": "Organizar tu trabajo autónomo de la sesión y llegar preparado a la siguiente clase.",
    "guion_clase": "Guiar al docente en la conducción de la sesión.",
    "presentacion": "Acompañar la exposición de la clase con diapositivas.",
    "repaso_momento": "Integrar lo trabajado en las sesiones del momento con su resultado de aprendizaje.",
    "guia_evidencia": "Entender qué se pide en la evidencia del momento y cómo se valora.",
    "estudio_caso": "Practicar el análisis de un caso con preguntas de menor a mayor complejidad.",
    "guia_producto_final": "Prepararte para el producto final del proyecto formativo.",
}
INSTRUCCIONES = {
    "cuestionario": ["Lee cada pregunta con atención.", "Elige la opción que consideres correcta.",
                     "Revisa los temas de las preguntas en las que dudaste."],
    "simulacro": ["Resuelve el simulacro en un tiempo similar al de la evaluación.",
                  "Elige una opción por pregunta.", "Repasa los contenidos en los que fallaste."],
    "practica_guiada": ["Lee el objetivo de la práctica.", "Resuelve cada ejercicio siguiendo los pasos.",
                        "Compara tu resultado con el resultado esperado.", "Revisa los errores que conviene evitar."],
    "tarjetas": ["Lee el frente de la tarjeta e intenta responder sin mirar.", "Comprueba tu respuesta con el reverso.",
                 "Repite las tarjetas que fallaste hasta dominarlas."],
    "guia_autonoma": ["Lee el objetivo y la actividad.", "Sigue los pasos en el tiempo estimado.",
                      "Responde el autochequeo.", "Lleva lo indicado a la siguiente clase."],
    "estudio_caso": ["Lee el caso completo.", "Responde las preguntas en orden; cada una exige más análisis.",
                     "Argumenta tus respuestas con los contenidos del momento."],
}
INSTRUCCIONES_GENERALES = ["Lee el material completo.", "Desarrolla cada sección en el orden en que aparece.",
                           "Revisa tu trabajo con las preguntas o la lista de verificación, si las hay."]


def _texto(valor: str) -> str:
    return escape(legible(valor))


def _proposito(herramienta: str, contenido) -> str:
    # Si la herramienta trae su propio objetivo (práctica, guía autónoma, guion), se usa ese.
    if isinstance(contenido, dict):
        for seccion in contenido.values():
            if isinstance(seccion, dict) and isinstance(seccion.get("objetivo"), str) and seccion["objetivo"].strip():
                return _texto(seccion["objetivo"])
    return _texto(PROPOSITO.get(herramienta, "Trabajar los contenidos del sílabo con esta herramienta."))


def exportar_html(recurso: dict, contexto: ContextoClase) -> str:
    herramienta = recurso["herramienta"]
    contenido = recurso["contenido"]
    nombre = NOMBRES.get(herramienta, herramienta)
    # En el ámbito de asignatura el título del momento es la propia asignatura: no repetirlo.
    actividad = (f"{nombre} · {contexto.asignatura}" if contexto.momento_titulo == contexto.asignatura
                 else f"{nombre} · {contexto.momento_titulo}")
    problema = [f"<p style=\"margin: 0 0 8px 0;\">{_texto(contexto.problema.descripcion)}</p>",
                f"<p style=\"margin: 0 0 8px 0;\"><strong style=\"color: #3a1467;\">Reto:</strong> "
                f"{_texto(contexto.problema.reto)}</p>"]
    if contexto.pis is not None and contexto.pis.nombre.strip():
        problema.append(f"<p style=\"margin: 0;\"><strong style=\"color: #3a1467;\">Proyecto integrador (PIS):</strong> "
                        f"{_texto(contexto.pis.nombre)}</p>")
    recursos = [f"<strong>Material:</strong> {_texto(nombre)} elaborado a partir del sílabo de {escape(contexto.asignatura)}"]
    if contexto.contenidos:
        recursos.append("<strong>Contenidos:</strong> " + _texto("; ".join(contexto.contenidos)))
    evidencia = (lista([_texto(e) for e in contexto.entregables_momento]) if contexto.entregables_momento
                 else "<p style=\"margin: 0;\">Esta herramienta es de práctica y no tiene entregable propio.</p>")
    evidencia += ("<p style=\"margin: 10px 0 0 0;\"><strong style=\"color: #3a1467;\">Entregable:</strong> "
                  "esta herramienta te prepara para la evidencia del momento; no la reemplaza.</p>")
    condiciones = lista([
        f"<strong>Fecha:</strong> {escape(nombre_ambito(contexto.clase_id))} · {contexto.fecha:%d/%m/%Y}",
        f"<strong>Uso de IA:</strong> {_texto(contexto.politica_ia or SIN_POLITICA)} Declara qué herramienta usaste, "
        "en qué parte del trabajo y cómo verificaste la información.",
        f"<em>{escape(PIE)}</em>",
    ])
    secciones = [
        ("RESULTADO DE APRENDIZAJE RELACIONADO", lista([_texto(f"{r.id}: {r.texto}") for r in contexto.ra])),
        ("¿Para qué realizas esta actividad?", _proposito(herramienta, contenido)),
        ("Caso, problema o reto del territorio", "".join(problema)),
        ("Instrucciones", lista([escape(i) for i in INSTRUCCIONES.get(herramienta, INSTRUCCIONES_GENERALES)],
                                numerada=True)),
        (nombre, en_linea(legible(IMPRIMIR + _cuerpo(herramienta, contenido)))),
        ("Recurso que debes utilizar", lista(recursos)),
        ("Evidencia o producto", evidencia),
        ("Evaluación", lista(["Actividad formativa. La evidencia del momento se valora con la "
                              "<strong>Rúbrica de evaluación Acceder</strong>."])),
        ("Condiciones de entrega", condiciones),
    ]
    return documento(titulo_pagina=f"{nombre} · {contexto.asignatura}", nombre_actividad=legible(actividad),
                     secciones=secciones, estilo=ESTILO, script=SCRIPT)
