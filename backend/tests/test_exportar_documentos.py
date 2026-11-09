from io import BytesIO
from zipfile import ZipFile

import pdfplumber
import pytest

from app.exportar.documento import exportar_documento, FormulaInvalida
from app.silabo.contexto import contexto_clase
from tests.test_exportar_html import _item, _recurso
from tests.test_exportar_html import entorno  # noqa: F401
from tests.acceso import dar_acceso
from tests.test_generacion_api import HEADERS


@pytest.mark.parametrize('formato', ['pdf', 'docx'])
def test_documento_del_docente_con_respuestas_y_formula(silabo, formato):
    r = _recurso('cuestionario', [_item(1, 'Calcula $x^2 + \\frac{1}{2}$')])
    datos = exportar_documento(r, contexto_clase(silabo, 'M2-S1'), formato, docente=True)
    if formato == 'pdf':
        with pdfplumber.open(BytesIO(datos)) as pdf:
            texto = '\n'.join(p.extract_text() or '' for p in pdf.pages)
    else:
        with ZipFile(BytesIO(datos)) as z:
            texto = z.read('word/document.xml').decode()
            assert any(n.startswith('word/media/') for n in z.namelist())
            assert not any(b'TargetMode="External"' in z.read(n) for n in z.namelist() if n.endswith('.rels'))
    assert 'solo para el docente' in texto and 'Respuesta correcta: B' in texto and 'Porque 1' in texto
    assert 'Momento 2' in texto and 'M2-S1' not in texto and 'revisado por el docente' in texto
    assert 'item_id' not in texto


def test_formula_invalida_controlada(silabo):
    r = _recurso('cuestionario', [_item(1, '$\\comandoNoPermitido{x}$')])
    with pytest.raises(FormulaInvalida):
        exportar_documento(r, contexto_clase(silabo, 'M2-S1'), 'pdf')


@pytest.mark.parametrize('expresion', ['x'*501, '{'*41+'x'+'}'*41, r'\input{secreto}'])
def test_limites_formulas(silabo, expresion):
    r = _recurso('cuestionario', [_item(1, '$'+expresion+'$')])
    with pytest.raises(FormulaInvalida):
        exportar_documento(r, contexto_clase(silabo, 'M2-S1'), 'docx')


def test_preguntas_no_dejan_opciones_solas(silabo):
    r = _recurso('cuestionario', [_item(n, r'Calcula $\sqrt{x}$ e interpreta.') for n in range(1, 9)])
    with pdfplumber.open(BytesIO(exportar_documento(r, contexto_clase(silabo, 'M2-S1'), 'pdf'))) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ''
            if 'Respuestas y justificaciones' in texto:
                break
            assert texto.count('Pregunta ') == texto.count('D) Opción 3')


@pytest.mark.parametrize('formato', ['pdf', 'docx'])
def test_marcado_se_exporta_como_texto(silabo, formato):
    marca = '<img src="https://example.invalid/privado">'
    datos = exportar_documento(_recurso('cuestionario', [_item(1, marca)]), contexto_clase(silabo, 'M2-S1'), formato)
    if formato == 'pdf':
        with pdfplumber.open(BytesIO(datos)) as pdf:
            assert marca in '\n'.join(p.extract_text() or '' for p in pdf.pages)
    else:
        with ZipFile(BytesIO(datos)) as z:
            assert '&lt;img' in z.read('word/document.xml').decode()
            assert not any(b'TargetMode="External"' in z.read(n) for n in z.namelist() if n.endswith('.rels'))


@pytest.mark.parametrize('formato,mime', [('pdf', 'application/pdf'), ('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')])
def test_api_documentos(entorno, formato, mime):
    _, clientes, d, aid, producir = entorno
    recurso = producir()
    url = f"/asignaturas/{aid}/recursos/{recurso['id']}/exportar?formato={formato}"
    assert d.get(url).status_code == 409
    assert clientes('ajeno@uti.edu.ec').get(url).status_code in (403, 404)
    assert d.post(f"/asignaturas/{aid}/recursos/{recurso['id']}/validar", json={'revision': recurso['revision']}, headers=HEADERS).status_code == 200
    respuesta = d.get(url)
    assert respuesta.status_code == 200
    assert respuesta.headers['content-type'] == mime
    assert f'.{formato}"; filename*=' in respuesta.headers['content-disposition'] and respuesta.headers['content-disposition'].endswith(f'.{formato}')
    assert respuesta.content.startswith(b'%PDF' if formato == 'pdf' else b'PK')
    contenido = recurso['contenido']
    contenido[0]['pregunta'] = '¿Qué procedimiento corresponde al contexto descrito en esta pregunta editada?'
    editado = d.put(f"/asignaturas/{aid}/recursos/{recurso['id']}", json={'revision': recurso['revision'], 'contenido': contenido}, headers=HEADERS)
    assert editado.status_code == 200
    assert d.get(url).status_code == 409


@pytest.mark.parametrize('formato', ['pdf', 'docx'])
def test_tablas_y_texto_literal(silabo, formato):
    from app.herramientas.sin_ia import generar_sin_ia
    from app.silabo.contexto import contexto_por_id
    r = _recurso('hoja_ruta', generar_sin_ia('hoja_ruta', silabo, 'asignatura'), 'asignatura')
    datos = exportar_documento(r, contexto_por_id(silabo, 'asignatura'), formato)
    if formato == 'docx':
        from docx import Document
        assert Document(BytesIO(datos)).tables
    else:
        with pdfplumber.open(BytesIO(datos)) as pdf:
            assert 'Calendario' in '\n'.join(p.extract_text() or '' for p in pdf.pages)


@pytest.mark.parametrize('formato', ['html', 'pdf', 'docx'])
def test_lector_descarga_solo_validado_y_pertenencia(entorno, silabo, formato, conn):
    app, clientes, d, aid, producir = entorno
    recurso = producir()
    lector = clientes('lector@uti.edu.ec')
    dar_acceso(conn, aid, 'lector@uti.edu.ec', 'lector')
    url = f"/asignaturas/{aid}/recursos/{recurso['id']}/exportar?formato={formato}"
    assert lector.get(url).status_code == 409
    assert d.post(f"/asignaturas/{aid}/recursos/{recurso['id']}/validar", json={'revision': recurso['revision']}, headers=HEADERS).status_code == 200
    assert lector.get(url).status_code == 200
    from app.silabo.modelo import SilaboUTI
    datos = silabo.model_dump()
    datos['proyecto_formativo']['codigo'] += '-OTRO'
    otro = app.state.asignaturas.guardar('dueno@uti.edu.ec', SilaboUTI.model_validate(datos))['id']
    assert otro != aid
    assert d.get(f"/asignaturas/{otro}/recursos/{recurso['id']}/exportar?formato={formato}").status_code == 404
    lector.cookies.clear()
    assert lector.get(url).status_code == 401


def _texto_de(datos, formato):
    if formato == 'pdf':
        with pdfplumber.open(BytesIO(datos)) as pdf:
            return '\n'.join(p.extract_text() or '' for p in pdf.pages)
    with ZipFile(BytesIO(datos)) as z:
        return z.read('word/document.xml').decode()


@pytest.mark.parametrize('formato', ['pdf', 'docx'])
def test_documento_del_estudiante_sin_respuestas(silabo, formato):
    texto = _texto_de(exportar_documento(_recurso('cuestionario', [_item(1)]), contexto_clase(silabo, 'M2-S1'), formato), formato)
    assert 'Opción 3' in texto and 'Porque' not in texto and 'Respuesta' not in texto


@pytest.mark.parametrize('formato', ['pdf', 'docx'])
def test_caso_del_estudiante_sin_respuesta_orientativa(silabo, formato):
    c = {'caso': {'caso': 'Un caso', 'ra': 'RA2', 'preguntas': [
        {'nivel': 'critico', 'pregunta': 'Por que ocurre', 'respuesta_orientativa': 'ORIENTATIVA-OCULTA'}]}}
    ctx = contexto_clase(silabo, 'M2-S1')
    estudiante = _texto_de(exportar_documento(_recurso('estudio_caso', c), ctx, formato), formato)
    docente = _texto_de(exportar_documento(_recurso('estudio_caso', c), ctx, formato, docente=True), formato)
    assert 'Por que ocurre' in estudiante and 'ORIENTATIVA-OCULTA' not in estudiante
    assert 'ORIENTATIVA-OCULTA' in docente


def test_respuestas_solo_para_quien_edita(entorno, conn):
    _, clientes, d, aid, producir = entorno
    recurso = producir()
    base = f"/asignaturas/{aid}/recursos/{recurso['id']}/exportar?formato=pdf"
    assert d.get(base + '&version=docente').status_code == 409  # Sin validar, tampoco.
    assert d.post(f"/asignaturas/{aid}/recursos/{recurso['id']}/validar", json={'revision': recurso['revision']}, headers=HEADERS).status_code == 200
    r = d.get(base + '&version=docente')
    assert r.status_code == 200 and 'Respuestas%20-%20' in r.headers['content-disposition']
    assert d.get(f"/asignaturas/{aid}/recursos/{recurso['id']}/exportar?formato=html&version=docente").status_code == 422
    lector = clientes('lector@uti.edu.ec')
    dar_acceso(conn, aid, 'lector@uti.edu.ec', 'lector')
    assert lector.get(base).status_code == 200 and lector.get(base + '&version=docente').status_code == 403
    assert d.get(base + '&version=otra').status_code == 422


def test_lector_no_recibe_respuestas_al_abrir_el_recurso(entorno, conn):
    """La misma regla que la descarga: la API no entrega por otra ruta lo que la descarga protege."""
    _, clientes, d, aid, producir = entorno
    recurso = producir()
    url = f"/asignaturas/{aid}/recursos/{recurso['id']}"
    lector = clientes('lector@uti.edu.ec')
    dar_acceso(conn, aid, 'lector@uti.edu.ec', 'lector')
    visto = lector.get(url)
    assert visto.status_code == 200
    item = visto.json()['contenido'][0]
    assert 'correcta' not in item and 'razonamiento' not in item and item['pregunta'] == recurso['contenido'][0]['pregunta']
    assert set(item['opciones'][0]) == {'texto'}
    assert visto.json()['evidencia'] == {} and visto.json()['revision_claves'] == {}
    for rastro in ('justificacion', 'error_que_representa', 'correcta'):
        assert rastro not in visto.text, rastro
    dueno = d.get(url).json()
    assert 'correcta' in dueno['contenido'][0] and 'justificacion' in dueno['contenido'][0]['opciones'][0]


def test_lector_de_caso_sin_respuesta_orientativa():
    from app.exportar.presentacion import presentar
    from app.recursos.servicio import _para_lector
    c = {'caso': {'escenario': 'INTERNO', 'caso': 'Un caso', 'ra': 'RA2', 'preguntas': [
        {'nivel': 'critico', 'pregunta': 'Por que', 'respuesta_orientativa': 'ORIENTATIVA'}]}}
    d = _para_lector({'herramienta': 'estudio_caso', 'contenido': c, 'evidencia': {'x': 1},
                      'presentacion': presentar('estudio_caso', c)})
    assert 'ORIENTATIVA' not in str(d) and 'INTERNO' not in str(d) and 'Por que' in str(d)
    # Veredictos de un ajuste por chat y cualquier campo futuro quedan fuera por omisión.
    revisado = _para_lector({'herramienta': 'cuestionario', 'contenido': [], 'evidencia': {}, 'presentacion': [],
                             'revision_ia': {'veredictos': ['SECRETO']}, 'campo_futuro': 'SECRETO'})
    assert 'SECRETO' not in str(revisado) and revisado['revision_ia'] is None and 'campo_futuro' not in revisado
    otro = {'herramienta': 'ficha_clase', 'contenido': {'a': 1}, 'evidencia': {'x': 1}, 'presentacion': []}
    assert _para_lector(otro) == otro
    assert _para_lector({**d, 'contenido': {'otra': 'ORIENTATIVA'}})['contenido'] == {}
