"""El armado del prompt usa la ventana real del cliente: DeepSeek (1M) no se recorta a los 8192 del vLLM local."""
import pytest

from app.llm.cliente import CONTEXTO_DEEPSEEK, CONTEXTO_MAXIMO, ClienteVLLM, ContextoExcedido
from app.llm.prompts import CONTEXTO_MAX, Sello, construir_prompt, limite_contexto
from app.silabo.contexto import contexto_clase
from app.agentes.mensajes import EstiloFacultad


def _cliente(proveedor):
    return ClienteVLLM("http://x.test/v1", "m", 5, 1, lambda e: None, api_key="k", proveedor=proveedor)


def test_ventana_segun_proveedor():
    assert _cliente("deepseek").contexto_max == CONTEXTO_DEEPSEEK
    assert _cliente("vllm").contexto_max == CONTEXTO_MAXIMO
    assert limite_contexto(object()) == CONTEXTO_MAX


def test_una_clase_larga_cabe_en_deepseek_pero_no_en_8k(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    args = dict(sello=Sello(codigo_pf=ctx.codigo_pf, clase_id=ctx.clase_id, fecha=ctx.fecha),
                instrucciones="Reglas.", contexto=ctx, estilo=EstiloFacultad(tipos_de_caso=[], software_habitual=[]),
                ya_generado=[], pedido="Pedido.", salida_max=2048, contar=lambda m: 9000)
    with pytest.raises(ContextoExcedido):
        construir_prompt(**args)
    assert len(construir_prompt(**args, contexto_max=CONTEXTO_DEEPSEEK)) == 2


def test_los_envoltorios_del_cliente_conservan_la_ventana():
    from app.agentes.coordinador import _ClienteConLease
    envuelto = _ClienteConLease(_cliente("deepseek"), lambda: None, lambda t: None)
    assert limite_contexto(envuelto) == CONTEXTO_DEEPSEEK
