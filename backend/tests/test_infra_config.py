"""Regresiones de aislamiento del despliegue, sin arrancar Docker."""
from pathlib import Path
import yaml

RAIZ = Path(__file__).resolve().parents[2]


def test_solo_proxy_publica_puertos_y_sin_volumen_de_desarrollo():
    compose = yaml.safe_load((RAIZ/'infra/compose.yaml').read_text(encoding='utf-8'))
    for nombre, servicio in compose['services'].items():
        assert not servicio.get('privileged')
        assert not servicio.get('container_name')
        if nombre != 'proxy':
            assert not servicio.get('ports'), nombre
    assert set(compose['volumes']) == {'datos', 'modelos'}
    assert 'external' not in compose['volumes']['datos']
    assert compose['networks']['datos']['internal']
    for nombre in ('api','worker','web','proxy'):
        s = compose['services'][nombre]
        assert s['read_only'] and s['cap_drop'] == ['ALL']


def test_proxy_alcanzable_y_solo_el():
    """Con solo redes internas Docker no publica puertos; la red pública es exclusiva del proxy."""
    compose = yaml.safe_load((RAIZ/'infra/compose.yaml').read_text(encoding='utf-8'))
    redes = compose['networks']
    for nombre, servicio in compose['services'].items():
        if servicio.get('ports'):
            assert any(not (redes[r] or {}).get('internal') for r in servicio['networks']), nombre
    assert [n for n, s in compose['services'].items() if 'publica' in s.get('networks', [])] == ['proxy']
    assert compose['networks']['borde']['ipam']['config'][0]['ip_range']


def test_copia_imagen_no_incluye_entorno_o_silabos_reales():
    dockerignore = (RAIZ/'.dockerignore').read_text(encoding='utf-8')
    assert dockerignore.splitlines()[1] == '**'
    assert '!Silabos' not in dockerignore and '!docs/**' not in dockerignore
    assert '**/.env*' in dockerignore
    backend = (RAIZ/'infra/Dockerfile.backend').read_text(encoding='utf-8')
    assert 'COPY . ' not in backend
    assert '@sha256:' in backend
    assert 'USER 10001:10001' in backend


def test_la_etapa_de_pruebas_no_pide_lo_que_no_esta_en_la_imagen():
    """`ciencia_datos` y PyTorch no entran en la imagen: ni sus pruebas ni la marca `modelo` pueden correr allí."""
    backend = (RAIZ/'infra/Dockerfile.backend').read_text(encoding='utf-8')
    assert 'COPY backend/ciencia_datos' not in backend
    pruebas = backend.split(' AS pruebas', 1)[1]
    assert 'rm -f /app/backend/tests/test_cd_' in pruebas
    assert '"-m", "not servidor and not modelo"' in pruebas


def test_tmpfs_es_una_sola_entrada_por_servicio():
    """En estilo de flujo YAML la coma de «size=…,mode=…» parte la entrada en dos y Docker la rechaza."""
    compose = yaml.safe_load((RAIZ/'infra/compose.yaml').read_text(encoding='utf-8'))
    for nombre, servicio in compose['services'].items():
        for entrada in servicio.get('tmpfs', []):
            assert entrada.startswith('/'), nombre


def test_nginx_no_escribe_fuera_de_tmp():
    """Con read_only, nginx no arranca si algún temporal queda en /var/cache/nginx."""
    for nombre in ('web.conf', 'proxy.conf.template'):
        conf = (RAIZ/'infra/nginx'/nombre).read_text(encoding='utf-8')
        for temporal in ('client_body', 'proxy', 'fastcgi', 'uwsgi', 'scgi'):
            assert f'{temporal}_temp_path /tmp/' in conf, (nombre, temporal)


def test_imagen_web_incluye_los_recursos_publicos():
    """Vite copia frontend/public (favicon y logo UTI); excluirlo deja la interfaz sin marca."""
    dockerignore = (RAIZ/'.dockerignore').read_text(encoding='utf-8').splitlines()
    assert '!frontend/public/**' in dockerignore
    assert all((RAIZ/'frontend/public'/nombre).is_file() for nombre in ('favicon.svg', 'logo-uti.png'))


def test_proxy_no_confia_cabeceras_de_cliente_y_no_registra_uri():
    nginx = (RAIZ/'infra/nginx/proxy.conf.template').read_text(encoding='utf-8')
    assert 'proxy_set_header X-Forwarded-For $remote_addr;' in nginx
    assert '$proxy_add_x_forwarded_for' not in nginx
    assert 'access_log off;' in nginx
    assert 'location ^~ /api/salud/ { return 404; }' in nginx
    assert 'client_max_body_size 10m;' in nginx
    assert 'proxy_hide_header Cache-Control;' in nginx


def test_limites_configurables_en_compose_con_los_valores_de_la_api():
    """Cada cuota de Ajustes llega al contenedor y su valor por defecto coincide con app/config.py."""
    import re
    from app.config import Ajustes
    entorno = yaml.safe_load((RAIZ/'infra/compose.yaml').read_text(encoding='utf-8'))['x-backend']['environment']
    campos = [c for c in Ajustes.model_fields if c.startswith('limite_')] + ['auditoria_retencion_dias']
    assert len(campos) == 10
    for campo in campos:
        valor = entorno[campo.upper()]
        defecto = re.fullmatch(r'\$\{' + campo.upper() + r':-(\d+)\}', valor)
        assert defecto and int(defecto[1]) == Ajustes.model_fields[campo].default, campo
    ejemplo = (RAIZ/'infra/.env.example').read_text(encoding='utf-8')
    assert all(f'{c.upper()}=' in ejemplo for c in campos)


def test_despliegue_no_expone_acceso_de_prueba():
    """El Compose institucional nunca debe poder encender el ingreso sin validar el correo."""
    assert 'ACCESO_PRUEBA' not in (RAIZ/'infra/compose.yaml').read_text(encoding='utf-8')
    assert 'ACCESO_PRUEBA' not in (RAIZ/'infra/.env.example').read_text(encoding='utf-8')


def _compose():
    return yaml.safe_load((RAIZ/'infra/compose.yaml').read_text(encoding='utf-8'))


def test_compose_no_activa_el_razonador_por_omision():
    """Sin RAZONADOR_RUTA la generación es la de siempre: vacío por omisión y solo en el worker."""
    servicios = _compose()['services']
    assert servicios['worker']['environment']['RAZONADOR_RUTA'] == '${RAZONADOR_RUTA:-}'
    # validar_configuracion corre en todos los servicios: ninguno más debe recibirla.
    for nombre, servicio in servicios.items():
        if nombre != 'worker':
            assert 'RAZONADOR_RUTA' not in (servicio.get('environment') or {}), nombre
    assert 'RAZONADOR_RUTA' not in _compose()['x-backend']['environment']
    ejemplo = (RAIZ/'infra/.env.example').read_text(encoding='utf-8')
    assert any(l.strip() == 'RAZONADOR_RUTA=' for l in ejemplo.splitlines())


def test_el_worker_conserva_todo_el_entorno_comun_y_monta_modelos_de_solo_lectura():
    compose = _compose()
    comun = compose['x-backend']['environment']
    entorno_worker = compose['services']['worker']['environment']
    assert all(entorno_worker[k] == v for k, v in comun.items())
    montajes = compose['services']['worker']['volumes']
    assert montajes == [{'type': 'volume', 'source': 'modelos', 'target': '/modelos', 'read_only': True}]
    for nombre, servicio in compose['services'].items():
        if nombre != 'worker':
            assert not any(isinstance(v, dict) and v.get('source') == 'modelos' or str(v).startswith('modelos:')
                           for v in servicio.get('volumes', [])), nombre
    assert 'modelos' in compose['volumes']


def test_la_imagen_de_produccion_no_lleva_torch_y_el_lock_es_completo():
    """El lock se instala con --no-deps: debe traer las dependencias del razonador y cerrar sus requisitos."""
    import re
    from importlib import metadata
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    lock = (RAIZ/'backend/requirements.lock').read_text(encoding='utf-8').splitlines()
    fijados = {l.split('==')[0].lower().replace('_', '-'): l.split('==')[1] for l in lock if '==' in l}
    assert not {'torch', 'sentence-transformers', 'onnx', 'onnxscript', 'transformers'} & set(fijados)
    assert {'numpy', 'scikit-learn', 'onnxruntime', 'tokenizers'} <= set(fijados)
    entorno = {**default_environment(), 'sys_platform': 'linux', 'platform_system': 'Linux', 'os_name': 'posix',
               'extra': ''}
    for nombre in sorted(fijados):
        # Un paquete del lock que no está instalado impediría comprobar sus requisitos: falla.
        requisitos = metadata.requires(nombre) or []
        for texto in requisitos:
            r = Requirement(texto)
            if r.marker is None or r.marker.evaluate(entorno):
                assert re.sub(r'[-_.]+', '-', r.name).lower() in fijados, (nombre, r.name)
