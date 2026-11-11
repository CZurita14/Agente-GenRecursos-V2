"""Imágenes de las diapositivas: Unsplash, Pexels, Wikimedia, respaldo en Openverse, guardado por hash y exportación."""
import io
import json
from uuid import uuid4

import httpx
import pytest
from PIL import Image as PIL

from app.agentes.workers import clase
from app.herramientas.imagenes import Imagen, crear_buscador, guardar, hashes, leer
from app.recursos.validacion import EdicionInvalida, validar_contenido
from app.silabo.contexto import contexto_clase


def _png(color=(58, 20, 103), tam=(64, 40)) -> bytes:
    salida = io.BytesIO()
    PIL.new("RGB", tam, color).save(salida, format="PNG")
    return salida.getvalue()


PNG = _png()


def _transporte(pexels=True, openverse=True, tipo="image/png", datos=PNG, llamadas=None, unsplash=True,
                wikimedia=False, licencia_wikimedia="CC BY-SA 4.0"):
    def manejar(r: httpx.Request):
        if llamadas is not None:
            llamadas.append(str(r.url))
        if r.url.host == "api.unsplash.com":
            if r.url.path.endswith("/download"):
                return httpx.Response(200, json={"url": "registrado"})
            assert r.headers["Authorization"] == "Client-ID clave-unsplash"
            fotos = [{"id": "foto1", "urls": {"regular": f"https://images.unsplash.com/photo-1?ixid={len(llamadas or [])}"},
                      "links": {"download_location": "https://api.unsplash.com/photos/1/download"},
                      "user": {"name": "Eva", "links": {"html": "https://unsplash.com/@eva"}}}]
            return httpx.Response(200, json={"results": fotos if unsplash else []})
        if r.url.host == "commons.wikimedia.org":
            assert "Etiquette" in r.headers["User-Agent"]
            pags = {"1": {"index": 1, "title": "File:Diagrama.png", "imageinfo": [{
                "mime": "image/png", "thumburl": "https://upload.wikimedia.test/d.png",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Diagrama.png",
                "extmetadata": {"LicenseShortName": {"value": licencia_wikimedia},
                                "Artist": {"value": '<a href="//x">Rosa &amp; Co</a>'}}}]}}
            return httpx.Response(200, json={"query": {"pages": pags}} if wikimedia else {})
        if r.url.host == "api.pexels.com":
            assert r.headers["Authorization"] == "clave-pexels"
            fotos = [{"src": {"large": "https://images.pexels.test/1.png"}, "photographer": "Ana", "url": "https://pexels.test/1"}]
            return httpx.Response(200, json={"photos": fotos if pexels else []})
        if r.url.host == "api.openverse.org":
            assert r.url.params["license"] == "by,by-sa,cc0,pdm" and r.url.params["mature"] == "false"
            res = [{"url": "https://cdn.test/2.png", "thumbnail": "https://cdn.test/2t.png", "creator": "Luis",
                    "license": "by-sa", "foreign_landing_url": "https://flickr.test/2"}]
            return httpx.Response(200, json={"results": res if openverse else []})
        return httpx.Response(200, content=datos, headers={"content-type": tipo})
    return httpx.MockTransport(manejar)


def test_pexels_primero_con_clave():
    llamadas = []
    imagen = crear_buscador(pexels_clave="clave-pexels", transporte=_transporte(llamadas=llamadas))("network security", set())
    assert (imagen.fuente, imagen.autor, imagen.licencia) == ("Pexels", "Ana", "Licencia Pexels")
    assert imagen.datos == PNG and not any("openverse" in u for u in llamadas)


def test_sin_clave_o_sin_resultado_usa_openverse():
    for clave, pexels in ((None, True), ("clave-pexels", False)):
        imagen = crear_buscador(pexels_clave=clave, transporte=_transporte(pexels=pexels))("data", set())
        assert (imagen.fuente, imagen.autor, imagen.licencia) == ("Openverse", "Luis", "CC BY-SA")


def test_no_repite_ni_acepta_archivos_que_no_son_imagen():
    usadas = {"https://cdn.test/2.png", "https://cdn.test/2t.png"}
    assert crear_buscador(pexels_clave=None, transporte=_transporte())("data", usadas) is None
    assert crear_buscador(pexels_clave=None, transporte=_transporte(tipo="text/html"))("data", set()) is None
    assert crear_buscador(pexels_clave=None, transporte=_transporte())("   ", set()) is None


def test_un_fallo_de_red_no_lanza():
    def caida(r):
        raise httpx.ConnectError("sin red")
    assert crear_buscador(pexels_clave="x", transporte=httpx.MockTransport(caida))("data", set()) is None


def test_guardar_y_leer_por_hash(conn):
    imagen = Imagen(PNG, "image/png", "Ana", "Licencia Pexels", "Pexels", "")
    guardar(conn, imagen)
    guardar(conn, imagen)  # Idempotente.
    assert leer(conn, imagen.hash) == (PNG, "image/png") and leer(conn, "0" * 64) is None


def _presentacion(silabo, con_imagen=True):
    d = {"titulo": "Diapositiva", "puntos": ["Uno", "Dos"], "notas": "Notas suficientes para el docente.",
         "imagen_busqueda": "computer code"}
    datos = {"titulo": "Presentación de prueba", "diapositivas": [dict(d) for _ in range(6)]}
    return datos


def test_el_worker_agrega_imagen_y_credito(monkeypatch, silabo):
    guardadas = []
    imagen = Imagen(PNG, "image/png", "Ana", "Licencia Pexels", "Pexels", "https://pexels.test/1")
    monkeypatch.setattr(clase, "BUSCADOR", lambda: (lambda q, usadas: imagen, guardadas.append))
    datos = clase.con_imagenes(_presentacion(silabo), None)
    assert all(d["imagen"] == imagen.credito() for d in datos["diapositivas"]) and len(guardadas) == 6


def test_sin_resultado_la_diapositiva_queda_sin_imagen(monkeypatch, silabo):
    monkeypatch.setattr(clase, "BUSCADOR", lambda: (lambda q, usadas: None, lambda i: None))
    assert all(d["imagen"] is None for d in clase.con_imagenes(_presentacion(silabo), None)["diapositivas"])


def test_pptx_con_imagen_y_credito(silabo):
    from pptx import Presentation
    from app.exportar.pptx import exportar_pptx
    ctx = contexto_clase(silabo, "M2-S1")
    imagen = Imagen(PNG, "image/png", "Ana", "Licencia Pexels", "Pexels", "https://pexels.test/1")
    datos = _presentacion(silabo)
    datos["diapositivas"][0]["imagen"] = imagen.credito()
    binario = exportar_pptx({"contenido": {"presentacion": datos}}, ctx, {imagen.hash: PNG})
    prs = Presentation(io.BytesIO(binario))
    primera = list(prs.slides)[1]
    assert sum(1 for f in primera.shapes if f.shape_type == 13) == 1  # 13 = imagen
    assert "Imagen: Ana · Licencia Pexels · Pexels" in primera.notes_slide.notes_text_frame.text
    assert all(f.left + f.width <= prs.slide_width for f in primera.shapes)
    cuerpo, titulo = primera.placeholders[1], primera.shapes.title
    assert cuerpo.height > 0 and cuerpo.top >= titulo.top + titulo.height  # El texto no tapa el título.
    assert sum(1 for f in list(prs.slides)[2].shapes if f.shape_type == 13) == 0


def test_editar_puede_quitar_una_imagen_pero_no_poner_otra(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    imagen = Imagen(PNG, "image/png", "Ana", "Licencia Pexels", "Pexels", "")
    original = {"presentacion": _presentacion(silabo)}
    original["presentacion"]["diapositivas"][0]["imagen"] = imagen.credito()
    sin = json.loads(json.dumps(original))
    sin["presentacion"]["diapositivas"][0]["imagen"] = None
    canonico, _ = validar_contenido("presentacion", sin, original, ctx, uuid4())
    assert not hashes(canonico)
    otra = json.loads(json.dumps(original))
    otra["presentacion"]["diapositivas"][1]["imagen"] = {**imagen.credito(), "hash": "a" * 64}
    with pytest.raises(EdicionInvalida):
        validar_contenido("presentacion", otra, original, ctx, uuid4())


def test_agotado_el_presupuesto_no_busca_mas(monkeypatch, silabo):
    llamadas = []
    monkeypatch.setattr(clase, "PRESUPUESTO_IMAGENES_S", 0)
    monkeypatch.setattr(clase, "BUSCADOR", lambda: (lambda q, u: llamadas.append(q), lambda i: None))
    clase.con_imagenes(_presentacion(silabo), None)
    assert llamadas == []


def test_unsplash_primero_registra_el_uso_y_da_credito():
    llamadas = []
    imagen = crear_buscador(unsplash_clave="clave-unsplash", pexels_clave="clave-pexels",
                            transporte=_transporte(llamadas=llamadas))("code", set())
    assert (imagen.fuente, imagen.autor, imagen.licencia) == ("Unsplash", "Eva", "Licencia Unsplash")
    assert imagen.vista.startswith("https://images.unsplash.com/") and "utm_source=" in imagen.enlace
    assert any(u.endswith("/photos/1/download") for u in llamadas)  # Exigido por Unsplash.
    assert not any("pexels" in u or "wikimedia" in u for u in llamadas)


def test_sin_unsplash_usa_wikimedia_con_licencia_libre():
    imagen = crear_buscador(unsplash_clave="clave-unsplash", transporte=_transporte(unsplash=False, wikimedia=True))(
        "flowchart", set())
    assert (imagen.fuente, imagen.autor, imagen.licencia) == ("Wikimedia Commons", "Rosa & Co", "CC BY-SA 4.0")
    assert imagen.vista == "" and imagen.enlace.endswith("File:Diagrama.png")


def test_wikimedia_descarta_licencias_no_libres():
    for licencia in ("CC BY-NC 2.0", "Fair use", "All rights reserved"):
        imagen = crear_buscador(transporte=_transporte(wikimedia=True, licencia_wikimedia=licencia))("x", set())
        assert imagen.fuente == "Openverse", licencia


def test_la_vista_web_solo_usa_el_cdn_de_unsplash():
    from app.exportar.presentacion import _imagen
    base = Imagen(PNG, "image/png", "Eva", "Licencia Unsplash", "Unsplash", "", "https://images.unsplash.com/p").credito()
    assert _imagen(base)[0]["vista"] == "https://images.unsplash.com/p"
    assert "vista" not in _imagen({**base, "vista": "https://malicioso.test/x.png"})[0]


def test_unsplash_no_repite_la_misma_foto_aunque_cambie_la_url():
    usadas, llamadas = set(), []
    buscar = crear_buscador(unsplash_clave="clave-unsplash", transporte=_transporte(llamadas=llamadas))
    assert buscar("aula", usadas).fuente == "Unsplash"
    assert buscar("aula", usadas).fuente != "Unsplash"
