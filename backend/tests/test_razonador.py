import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import app.razonador as modulo
from app.razonador import UMBRAL_DESARROLLO, Razonador, RazonadorInvalido

BASE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BACKEND = Path(__file__).resolve().parents[1]


def _falso(tabla: dict[str, list[float]] | None = None, umbral: float = 0.6, llamadas: list | None = None):
    """Razonador cuyos vectores salen de una tabla (o de un hash fijo) y se cuentan las corridas."""

    def codificar(textos):
        if llamadas is not None:
            llamadas.append(list(textos))
        filas = []
        for t in textos:
            v = np.array(tabla[t] if tabla and t in tabla else [1.0 + len(t) % 5, 1.0 + hash_estable(t) % 7, 0.5], float)
            filas.append(v / np.linalg.norm(v))
        return np.vstack(filas)

    return Razonador(codificar, version="v-falsa", umbral=umbral)


def hash_estable(t: str) -> int:
    return sum(ord(c) * (i + 1) for i, c in enumerate(t))


@pytest.fixture
def falso():
    return _falso()


@pytest.fixture
def falso_sinonimos():
    return _falso({"intrusión informática": [1, 0.1, 0], "ataque a la red": [1, 0.0, 0], "ventas de pan": [0, 0.2, 1]})


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_pocos_textos_no_se_agrupan(n):
    llamadas = []
    r = _falso(llamadas=llamadas)
    assert r.temas([f"t{i}" for i in range(n)]) == [[i] for i in range(n)]
    assert llamadas == []


def test_temas_son_deterministas_y_no_pierden_textos(falso):
    t = [f"t{i}" for i in range(8)]
    assert falso.temas(t) == falso.temas(t)
    assert sorted(i for g in falso.temas(t) for i in g) == list(range(8))


def test_temas_separan_grupos_obvios_en_orden_estable():
    tabla = {f"a{i}": [1, 0.01 * i, 0] for i in range(4)} | {f"b{i}": [0, 0.01 * i, 1] for i in range(4)}
    textos = ["b0", "a0", "b1", "a1", "a2", "b2", "a3", "b3"]
    assert _falso(tabla).temas(textos) == [[0, 2, 5, 7], [1, 3, 4, 6]]


def test_temas_con_textos_repetidos_no_falla():
    assert _falso().temas(["x", "x", "x", "x", "x"]) == [[0, 1, 2, 3, 4]]


def test_descarta_el_caso_parecido_aunque_no_comparta_palabras(falso_sinonimos):
    assert falso_sinonimos.casos_libres(["intrusión informática", "ventas de pan"], ["ataque a la red"]) == ["ventas de pan"]


def test_casos_libres_sin_entregables_devuelve_todo_sin_correr_el_modelo():
    llamadas = []
    r = _falso(llamadas=llamadas)
    assert r.casos_libres(["b", "a", "c"], []) == ["b", "a", "c"]
    assert llamadas == []


def test_casos_libres_vacio_y_orden_de_entrada(falso_sinonimos):
    assert falso_sinonimos.casos_libres([], ["ataque a la red"]) == []
    casos = ["ventas de pan", "intrusión informática", "ventas de pan"]
    assert falso_sinonimos.casos_libres(casos, ["ataque a la red"]) == ["ventas de pan", "ventas de pan"]


def test_vectores_vacios(falso):
    assert falso.vectores([]).shape[0] == 0


def test_vectores_por_lotes_conservan_el_orden():
    llamadas = []
    r = _falso(llamadas=llamadas)
    textos = [f"texto {i}" for i in range(70)]
    v = r.vectores(textos)
    assert v.shape[0] == 70 and [len(x) for x in llamadas] == [32, 32, 6]
    assert np.allclose(v[40], r.vectores([textos[40]])[0])


def _carpeta(tmp_path, meta, *, onnx=True, tokenizer=True):
    c = tmp_path / "v1"
    (c / "onnx").mkdir(parents=True)
    if onnx:
        (c / "onnx" / "model.onnx").write_bytes(b"x")
    if tokenizer:
        (c / "tokenizer.json").write_text("{}", encoding="utf-8")
    if meta is not None:
        if meta.get("aprobado") is True:  # Un aprobado de verdad siempre lleva la huella de sus pesos.
            meta = {"huella_pesos": modulo.huella_pesos(c), **meta}
        (c / "metadatos.json").write_text(json.dumps(meta), encoding="utf-8")
    return c


@pytest.fixture
def carpeta_con(tmp_path):
    cuenta = iter(range(100))
    return lambda meta, **kw: _carpeta(tmp_path / f"c{next(cuenta)}", meta, **kw)


@pytest.mark.parametrize("meta", [{"humo": True, "aprobado": False}, {"humo": False, "aprobado": False}])
def test_no_carga_modelo_sin_aprobar(carpeta_con, meta):
    with pytest.raises(RazonadorInvalido):
        Razonador.cargar(carpeta_con(meta), exigir_aprobado=True)


@pytest.mark.parametrize("meta", [
    {"humo": True, "aprobado": True, "umbral": 0.7},
    {"humo": False, "aprobado": False, "umbral": 0.7},
    {"humo": False, "aprobado": True, "umbral": None},
    {"aprobado": True, "umbral": 0.7},
])
def test_exigir_aprobado_rechaza_humo_no_aprobado_o_sin_umbral(carpeta_con, meta):
    with pytest.raises(RazonadorInvalido):
        Razonador.cargar(carpeta_con(meta), exigir_aprobado=True)


def test_carpeta_incompleta_o_ilegible(tmp_path, carpeta_con):
    bueno = {"humo": False, "aprobado": True, "umbral": 0.7}
    for nombre, kw in (("sin_onnx", {"onnx": False}), ("sin_tokenizer", {"tokenizer": False})):
        with pytest.raises(RazonadorInvalido):
            Razonador.cargar(_carpeta(tmp_path / nombre, bueno, **kw), exigir_aprobado=True)
    with pytest.raises(RazonadorInvalido, match="no existe"):
        Razonador.cargar(tmp_path / "nada", exigir_aprobado=False)
    with pytest.raises(RazonadorInvalido, match="metadatos"):
        Razonador.cargar(carpeta_con(None), exigir_aprobado=False)
    c = carpeta_con(bueno)
    (c / "metadatos.json").write_text("{no es json", encoding="utf-8")
    with pytest.raises(RazonadorInvalido, match="metadatos"):
        Razonador.cargar(c, exigir_aprobado=False)


def test_carga_aprobada_usa_umbral_y_longitud_de_metadatos(carpeta_con, monkeypatch):
    visto = {}
    monkeypatch.setattr(modulo, "_abrir", lambda ruta, longitud: visto.setdefault("l", longitud) and (lambda t: np.eye(len(t))))
    r = Razonador.cargar(carpeta_con({"version": "v9", "humo": False, "aprobado": True, "umbral": 0.73, "longitud_maxima": 64}),
                         exigir_aprobado=True)
    assert (r.version, r.umbral, visto["l"]) == ("v9", 0.73, 64)


@pytest.mark.parametrize("umbral", [float("nan"), float("inf"), float("-inf"), 1.5, -1.01, "0.7", True])
def test_umbral_fuera_de_rango_o_no_finito_se_rechaza(carpeta_con, umbral):
    meta = {"humo": False, "aprobado": True, "umbral": umbral}
    for exigir in (True, False):
        with pytest.raises(RazonadorInvalido, match="umbral"):
            Razonador.cargar(carpeta_con(meta), exigir_aprobado=exigir)


@pytest.mark.parametrize("longitud", [0, -5, 513, 1000000, 64.5, "128", True, None])
def test_longitud_maxima_invalida_se_rechaza(carpeta_con, longitud):
    meta = {"humo": False, "aprobado": True, "umbral": 0.7, "longitud_maxima": longitud}
    with pytest.raises(RazonadorInvalido, match="longitud_maxima"):
        Razonador.cargar(carpeta_con(meta), exigir_aprobado=True)


def test_caso_con_coseno_igual_al_umbral_se_descarta():
    r = _falso({"caso": [1, 0], "entregable": [1, 0], "lejano": [0, 1]}, umbral=1.0)
    assert np.isclose(float(r.vectores(["caso"])[0] @ r.vectores(["entregable"])[0]), 1.0)
    assert r.casos_libres(["caso", "lejano"], ["entregable"]) == ["lejano"]


def test_sin_umbral_en_desarrollo_usa_el_de_desarrollo(carpeta_con, monkeypatch):
    monkeypatch.setattr(modulo, "_abrir", lambda ruta, longitud: lambda t: np.eye(len(t)))
    r = Razonador.cargar(carpeta_con({"humo": True, "aprobado": False, "umbral": None}), exigir_aprobado=False)
    assert r.umbral == UMBRAL_DESARROLLO == 0.6


APROBADO = {"version": "v1", "humo": False, "aprobado": True, "umbral": 0.7}


def _sin_abrir(monkeypatch):
    monkeypatch.setattr(modulo, "_abrir", lambda ruta, longitud: lambda t: np.eye(len(t), 3))


def _con_pesos(carpeta_con, pesos: bytes = b"pesos originales"):
    c = carpeta_con(None)
    (c / "onnx" / "model.onnx.data").write_bytes(pesos)
    (c / "metadatos.json").write_text(json.dumps({**APROBADO, "huella_pesos": modulo.huella_pesos(c)}), encoding="utf-8")
    return c


def test_cambiar_un_byte_de_los_pesos_impide_cargar_una_carpeta_aprobada(carpeta_con, monkeypatch):
    _sin_abrir(monkeypatch)
    c = _con_pesos(carpeta_con)
    assert Razonador.cargar(c, exigir_aprobado=True).version == "v1"
    (c / "onnx" / "model.onnx.data").write_bytes(b"pesos 0riginales")
    with pytest.raises(RazonadorInvalido, match="huella"):
        Razonador.cargar(c, exigir_aprobado=True)
    assert Razonador.cargar(c, exigir_aprobado=False).version == "v1"  # Solo el aprobado la exige.


def test_cambiar_el_grafo_o_quitar_los_pesos_tambien_impide_cargar(carpeta_con, monkeypatch):
    _sin_abrir(monkeypatch)
    grafo, sin_pesos = _con_pesos(carpeta_con), _con_pesos(carpeta_con)
    (grafo / "onnx" / "model.onnx").write_bytes(b"y")
    (sin_pesos / "onnx" / "model.onnx.data").unlink()
    for c in (grafo, sin_pesos):
        with pytest.raises(RazonadorInvalido, match="huella"):
            Razonador.cargar(c, exigir_aprobado=True)


def test_un_aprobado_sin_huella_no_carga(carpeta_con, monkeypatch):
    _sin_abrir(monkeypatch)
    c = _con_pesos(carpeta_con)
    (c / "metadatos.json").write_text(json.dumps(APROBADO), encoding="utf-8")
    with pytest.raises(RazonadorInvalido, match="huella"):
        Razonador.cargar(c, exigir_aprobado=True)


def test_igual_grafo_y_distintos_pesos_tienen_huellas_distintas(carpeta_con):
    a, b, sin = _con_pesos(carpeta_con, b"pesos a"), _con_pesos(carpeta_con, b"pesos b"), carpeta_con(None)
    assert (a / "onnx" / "model.onnx").read_bytes() == (b / "onnx" / "model.onnx").read_bytes()
    assert len({modulo.huella_pesos(a), modulo.huella_pesos(b), modulo.huella_pesos(sin)}) == 3
    assert modulo.huella_pesos(a) == modulo.huella_pesos(_con_pesos(carpeta_con, b"pesos a"))


@pytest.mark.parametrize("exigir", [True, False])
def test_inferencia_de_prueba_que_falla_invalida_la_carga(carpeta_con, monkeypatch, exigir):
    pedidos = []

    def roto(textos):
        pedidos.append(textos)
        raise RuntimeError("dimensiones del texto secreto")

    monkeypatch.setattr(modulo, "_abrir", lambda ruta, longitud: roto)
    with pytest.raises(RazonadorInvalido, match="inferencia de prueba") as error:
        Razonador.cargar(carpeta_con(APROBADO), exigir_aprobado=exigir)
    assert pedidos == [["prueba"]] and "secreto" not in str(error.value)


def test_inferencia_de_prueba_con_valores_no_finitos_invalida_la_carga(carpeta_con, monkeypatch):
    monkeypatch.setattr(modulo, "_abrir", lambda ruta, longitud: lambda t: np.full((len(t), 3), np.nan))
    with pytest.raises(RazonadorInvalido, match="inferencia de prueba"):
        Razonador.cargar(carpeta_con(APROBADO), exigir_aprobado=True)


def test_importar_el_razonador_no_trae_pytorch():
    codigo = "import sys, app.razonador; print(any(m.split('.')[0] in ('torch', 'sentence_transformers') for m in sys.modules))"
    r = subprocess.run([sys.executable, "-c", codigo], cwd=BACKEND, capture_output=True, text=True, check=True)
    assert r.stdout.strip() == "False"


# --- con el modelo real (.venv-ciencia) ------------------------------------------------

FRASES = ["hola", "Analizar los datos de ventas de la empresa y proponer mejoras. " * 20]


@pytest.fixture(scope="module")
def modelo_humo(tmp_path_factory):
    from ciencia_datos.entrenar import entrenar

    return entrenar(["Identificar requisitos de un sistema.", "Analizar datos de ventas."] * 4, BASE,
                    tmp_path_factory.mktemp("m") / "v0", humo=True, ajuste=False)


def _aprobar_copia(modelo_humo, destino) -> Path:
    """Copia real del modelo exportado, con los metadatos que deja `evaluar` al aprobar."""
    shutil.copytree(modelo_humo, destino)
    ruta = destino / "metadatos.json"
    meta = json.loads(ruta.read_text(encoding="utf-8"))
    ruta.write_text(json.dumps({**meta, "humo": False, "aprobado": True, "umbral": 0.7,
                                "huella_pesos": modulo.huella_pesos(destino)}), encoding="utf-8")
    return destino


@pytest.mark.modelo
def test_pesos_reales_con_un_byte_cambiado_no_cargan_aunque_el_grafo_sea_igual(modelo_humo, tmp_path):
    c = _aprobar_copia(modelo_humo, tmp_path / "aprobado")
    pesos = c / "onnx" / "model.onnx.data"
    assert pesos.stat().st_size > 1_000_000  # Los pesos van de verdad en el archivo externo.
    assert (c / "onnx" / "model.onnx").stat().st_size < pesos.stat().st_size
    huella_original = modulo.huella_pesos(c)
    assert np.isfinite(Razonador.cargar(c, exigir_aprobado=True).vectores(["texto"])).all()
    with open(pesos, "r+b") as f:
        f.seek(pesos.stat().st_size // 2)
        byte = f.read(1)
        f.seek(-1, 1)
        f.write(bytes([byte[0] ^ 0xFF]))
    assert modulo.huella_pesos(c) != huella_original
    with pytest.raises(RazonadorInvalido, match="huella"):
        Razonador.cargar(c, exigir_aprobado=True)


@pytest.mark.modelo
def test_modelo_real_con_tokenizador_ajeno_falla_en_la_inferencia_de_prueba(modelo_humo, tmp_path):
    """La sesión abre, pero los identificadores no caben en el modelo: antes solo fallaba el primer trabajo."""
    c = tmp_path / "ajeno"
    shutil.copytree(modelo_humo, c)
    tok = json.loads((c / "tokenizer.json").read_text(encoding="utf-8"))
    for especial in tok["post_processor"]["special_tokens"].values():
        especial["ids"] = [i + 10_000_000 for i in especial["ids"]]
    (c / "tokenizer.json").write_text(json.dumps(tok), encoding="utf-8")
    with pytest.raises(RazonadorInvalido, match="inferencia de prueba"):
        Razonador.cargar(c, exigir_aprobado=False)


@pytest.mark.modelo
def test_onnx_da_los_mismos_vectores_que_el_entrenamiento(modelo_humo):
    from sentence_transformers import SentenceTransformer

    meta = json.loads((modelo_humo / "metadatos.json").read_text(encoding="utf-8"))
    assert meta["longitud_maxima"] == 128
    st = SentenceTransformer(BASE, device="cpu")
    st.max_seq_length = meta["longitud_maxima"]
    esperado = st.encode(FRASES, normalize_embeddings=True)
    obtenido = Razonador.cargar(modelo_humo, exigir_aprobado=False).vectores(FRASES)
    assert np.allclose(obtenido, esperado, atol=1e-3)


@pytest.mark.modelo
def test_un_razonador_real_da_lo_mismo_desde_varios_hilos(modelo_humo):
    from concurrent.futures import ThreadPoolExecutor

    r = Razonador.cargar(modelo_humo, exigir_aprobado=False)
    lotes = [[f"frase número {i} sobre análisis de datos", f"otra frase {i} de redes"] for i in range(16)]
    esperado = [r.vectores(lote) for lote in lotes]
    with ThreadPoolExecutor(max_workers=8) as pool:
        obtenido = list(pool.map(r.vectores, lotes * 3))
    for i, v in enumerate(obtenido):
        assert np.allclose(v, esperado[i % 16], atol=1e-5)


@pytest.mark.modelo
def test_un_texto_mas_largo_que_la_longitud_maxima_se_trunca_y_corre(modelo_humo):
    r = Razonador.cargar(modelo_humo, exigir_aprobado=False)
    largo = "Analizar los datos de ventas de la empresa. " * 200
    inicio = r.vectores([largo])
    assert inicio.shape[0] == 1 and np.isfinite(inicio).all()
    # Solo cuenta lo que cabe: añadir texto de más no cambia el vector.
    assert np.allclose(inicio, r.vectores([largo + " palabras sobrantes al final"]), atol=1e-5)


@pytest.mark.modelo
def test_un_modelo_exportado_de_verdad_planifica_de_punta_a_punta(modelo_humo, silabo):
    from app.agentes.facultades import cargar_perfiles, estilo_para
    from app.agentes.planificador import _casos_libres, _focos, estilo_razonado, planificar
    from app.silabo.contexto import contexto_clase

    perfil = cargar_perfiles(BACKEND.parent / "agentes")["ingenierias"]
    ctx = contexto_clase(silabo, "M2-S1")
    r = Razonador.cargar(modelo_humo, exigir_aprobado=False)

    def correr():
        estilo = estilo_razonado(perfil, "SOFTWARE", ctx, r)
        return estilo, planificar(ctx, 12, "profesional", escenarios=estilo.escenarios, razonador=r)

    estilo, lotes = correr()
    plan = [p for lote in lotes for p in lote]
    assert [p.item_id for p in plan] == [f"i{k + 1}" for k in range(12)]
    assert all(p.foco and p.foco in _focos(ctx) for p in plan)
    permitidos = set(_casos_libres(list(estilo_para(perfil, "SOFTWARE").escenarios), ctx.entregables_momento))
    assert set(estilo.escenarios) <= permitidos  # El razonador solo descarta: nunca añade ni afloja el filtro.
    assert all(p.caso in estilo.escenarios for p in plan) or not estilo.escenarios
    assert correr() == (estilo, lotes)


def test_produccion_rechaza_un_preliminar_aunque_diga_aprobado(carpeta_con):
    ruta = carpeta_con({"humo": False, "aprobado": True, "umbral": 0.7, "preliminar": True})
    with pytest.raises(RazonadorInvalido, match="preliminar"):
        Razonador.cargar(ruta, exigir_aprobado=True)


def test_desarrollo_si_carga_un_preliminar(carpeta_con, monkeypatch):
    monkeypatch.setattr(modulo, "_abrir", lambda ruta, longitud: (lambda t: np.eye(len(t))))
    ruta = carpeta_con({"humo": False, "aprobado": False, "umbral": None, "preliminar": True})
    assert Razonador.cargar(ruta, exigir_aprobado=False)


@pytest.mark.parametrize("sep", [
    {"entrenamiento": ["SIM-1"], "prueba": ["PF-2"]},
    {"entrenamiento": ["PF-1"], "prueba": ["SIM-2"]},
])
def test_produccion_rechaza_simulados_sin_la_marca_preliminar(carpeta_con, sep):
    ruta = carpeta_con({"humo": False, "aprobado": True, "umbral": 0.7, "separacion": sep})
    with pytest.raises(RazonadorInvalido, match="simulados"):
        Razonador.cargar(ruta, exigir_aprobado=True)


@pytest.mark.parametrize("sep", [None, "mala", {"entrenamiento": 3}, {"entrenamiento": ["PF-1"], "prueba": ["PF-2"]}])
def test_produccion_acepta_separacion_ausente_mal_formada_o_sin_simulados(carpeta_con, monkeypatch, sep):
    monkeypatch.setattr(modulo, "_abrir", lambda ruta, longitud: (lambda t: np.eye(len(t))))
    meta = {"humo": False, "aprobado": True, "umbral": 0.7}
    if sep is not None:
        meta["separacion"] = sep
    ruta = carpeta_con(meta)
    assert Razonador.cargar(ruta, exigir_aprobado=True)
