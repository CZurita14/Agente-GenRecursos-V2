"""Entrada y segmentación del lector (P2, Tarea 1)."""
import re

import pytest

from app.silabo.lector import SilaboIlegible
from app.silabo.lector.entrada import MAX_PAGINAS, SECCIONES_UTILES, abrir, segmentar
from tests.lector.conftest import datos_personales, fugas


def _pdf_en_blanco(paginas: int = 1) -> bytes:
    """PDF válido de `paginas` páginas sin contenido, con su tabla xref calculada."""
    hijos = b" ".join(b"%d 0 R" % (3 + k) for k in range(paginas))
    objetos = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [%s] /Count %d >>" % (hijos, paginas)]
    objetos += [b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"] * paginas
    salida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, cuerpo in enumerate(objetos, 1):
        offsets.append(len(salida))
        salida += b"%d 0 obj\n" % n + cuerpo + b"\nendobj\n"
    xref = len(salida)
    total = len(objetos) + 1
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % total
    salida += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    salida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (total, xref)
    return bytes(salida)


@pytest.mark.parametrize("datos", [
    b"hola",
    b"%PDF" + b"0" * (50 * 1024 * 1024),
    b"%PDF-1.4 roto",
    _pdf_en_blanco(),
    _pdf_en_blanco(MAX_PAGINAS + 1),
], ids=["no_pdf", "grande", "corrupto", "sin_texto", "demasiadas_paginas"])
def test_rechazos_de_entrada(datos):
    with pytest.raises(SilaboIlegible) as e:
        abrir(datos)
    assert "Traceback" not in str(e.value) and e.value.motivo


def test_ignora_el_indice(pdf_real):
    with abrir(pdf_real("datos")) as pdf:
        assert segmentar(pdf)["II"][0].page_number == 2


@pytest.mark.parametrize("nombre", ["datos", "tic"])
def test_secciones_presentes(pdf_real, nombre):
    with abrir(pdf_real(nombre)) as pdf:
        secciones = segmentar(pdf)
    assert set(secciones) == set(SECCIONES_UTILES)
    assert all(secciones[s] for s in SECCIONES_UTILES)


@pytest.mark.parametrize("nombre", ["datos", "tic"])
def test_segmenta_por_posicion_no_por_pagina(pdf_real, nombre):
    # La portada muestra el nombre del docente (spec §7 lo permite para mostrar); que no
    # llegue al SilaboUTI lo prueba el criterio 5. Aquí: II-VI sin nada de la sección I.
    datos = pdf_real(nombre)
    personales = datos_personales(datos)
    assert len(personales) >= 3, "el helper no encontró los datos de la sección I"
    cuerpo = [s for s in SECCIONES_UTILES if s != "portada"]
    with abrir(datos) as pdf:
        secciones = segmentar(pdf)
        texto = "\n".join(p.extract_text() or "" for s in cuerpo for p in secciones[s])
        tablas = "\n".join(c or "" for s in cuerpo for p in secciones[s]
                           for t in p.extract_tables() for f in t for c in f)
    for fuente in (texto, tablas):
        assert "Nombres y apellidos" not in fuente and "ORCID" not in fuente.upper()
        n = fugas(fuente, personales)
        assert n == 0, f"{n} datos personales de la sección I fuera de ella"


def test_paginas_de_mas_no_se_recorren(monkeypatch):
    # El conteo de caracteres no debe tocar páginas una vez superado el límite.
    import app.silabo.lector.entrada as entrada
    leidas = []
    original = entrada.pdfplumber.page.Page.chars
    monkeypatch.setattr(entrada.pdfplumber.page.Page, "chars",
                        property(lambda self: leidas.append(self.page_number) or original.fget(self)))
    with pytest.raises(SilaboIlegible):
        abrir(_pdf_en_blanco(MAX_PAGINAS + 1))
    assert leidas == []


@pytest.mark.parametrize("nombre", ["datos", "tic"])
def test_sin_pie_de_pagina(pdf_real, nombre):
    # El pie «Generado por <usuario> el <fecha>» identifica a una persona.
    with abrir(pdf_real(nombre)) as pdf:
        secciones = segmentar(pdf)
        texto = "\n".join(p.extract_text() or "" for s in SECCIONES_UTILES for p in secciones[s])
    assert "Generado por" not in texto
    assert "Página " not in texto


@pytest.mark.parametrize("nombre, esperadas", [("datos", 11), ("tic", 6)])
def test_filas_abiertas_al_pie_se_recuperan(pdf_real, nombre, esperadas):
    # Una sesión que empieza al pie de página no tiene borde inferior: debe recuperarse igual.
    from app.silabo.lector.entrada import tablas
    with abrir(pdf_real(nombre)) as pdf:
        primeras = [(f[0] or "") for p in segmentar(pdf)["IV"] for t in tablas(p) for f in t]
    sesiones = [c for c in primeras if re.match(r"Sesión \d+\s+\d{2}/\d{2}/\d{4}", c)]
    assert len(sesiones) == esperadas


def test_pie_se_busca_solo_al_final_y_sin_distinguir_mayusculas():
    from app.silabo.lector.entrada import _es_pie
    assert _es_pie({"text": "GENERADO POR", "top": 790}, 842)
    assert not _es_pie({"text": "Generado por", "top": 300}, 842)
