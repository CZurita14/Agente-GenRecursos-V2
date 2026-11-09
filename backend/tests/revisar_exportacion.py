"""Muestras reproducibles para QA visual, sin IA ni BD. No se ejecuta con pytest.

Desde backend: python -m tests.revisar_exportacion <directorio de salida>
"""
import json
from pathlib import Path
import sys

from app.exportar.documento import exportar_documento
from app.herramientas.sin_ia import generar_sin_ia
from app.silabo.contexto import contexto_clase, contexto_por_id
from app.silabo.modelo import SilaboUTI
from tests.test_exportar_html import _item, _recurso


def main():
    salida = Path(sys.argv[1]).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    silabo = SilaboUTI.model_validate(json.loads((Path(__file__).parent / 'fixtures/silabo_datos.json').read_text(encoding='utf-8')))
    quiz = _recurso('cuestionario', [_item(n, r'Calcula $\frac{1}{2} + \sqrt{x^2}$ y explica la relación entre α y β.') for n in range(1, 9)])
    ficha = _recurso('ficha_clase', {'conceptual': {'ideas_clave': ['Primera idea', 'Segunda idea'], 'relacion_ra': 'Práctica de aplicación', 'errores_frecuentes': ['No comprobar unidades']},
        'aplicacion': {'ejemplo': {'enunciado': 'Una empresa ficticia mide sus ventas diarias.', 'pasos': ['Ordenar los datos', r'Calcular $\bar{x} = \frac{1}{n}\sum_{i=1}^{n}x_i$'], 'resultado': 'Interpretar el valor obtenido.'}, 'autocomprobacion': ['¿Qué significa la media?']}})
    hoja = _recurso('hoja_ruta', generar_sin_ia('hoja_ruta', silabo, 'asignatura'), 'asignatura')
    for nombre, recurso in [('cuestionario', quiz), ('ficha', ficha), ('tablas', hoja)]:
        ctx = contexto_por_id(silabo, 'asignatura') if nombre == 'tablas' else contexto_clase(silabo, 'M2-S1')
        for formato in ('pdf', 'docx'):
            (salida / f'{nombre}.{formato}').write_bytes(exportar_documento(recurso, ctx, formato))
    print(f'6 muestras generadas en {salida}')


if __name__ == '__main__':
    main()
