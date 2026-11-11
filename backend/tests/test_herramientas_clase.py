"""Herramientas de clase de la V2: práctica guiada, tarjetas, guía autónoma y guion de clase."""
import json
from uuid import uuid4

import pytest

from app.agentes.mensajes import EstiloFacultad, TareaLote
from app.agentes.planificador import planificar
from app.agentes.workers import WORKERS
from app.agentes.workers.definiciones import DEFINICIONES
from app.exportar.presentacion import presentar
from app.llm.cliente import ClienteSimulado
from app.silabo.contexto import contexto_clase
from app.silabo.modelo import Actividad

ESTILO = EstiloFacultad(tipos_de_caso=["datasets"], software_habitual=["Git"])
NUEVAS = ("practica_guiada", "tarjetas", "guia_autonoma", "guion_clase", "presentacion")


def _tarea(ctx):
    return TareaLote(trabajo_id=uuid4(), asignatura_id=uuid4(), lote=1, ronda=0, contexto=ctx, estilo=ESTILO,
                     plan=planificar(ctx, 4, "fundamentacion")[0], ya_generado=[], devoluciones=[])


def _salida(herramienta, ctx):
    texto = "Texto suficientemente largo para cumplir el mínimo del esquema de la herramienta."
    if herramienta == "practica_guiada":
        e = {"enunciado": texto, "pasos": ["Paso uno", "Paso dos"], "resultado_esperado": "Un resultado claro"}
        return {"objetivo": texto, "ejercicios": [e, e], "errores_a_evitar": ["Olvidar las unidades"]}
    if herramienta == "tarjetas":
        return {"tarjetas": [{"frente": f"Pregunta {k}", "reverso": "Respuesta breve",
                              "contenido": ctx.contenidos[0]} for k in range(8)]}
    if herramienta == "guia_autonoma":
        return {"objetivo": texto, "actividad": texto, "pasos": ["Leer", "Resolver", "Revisar"],
                "tiempo_estimado": "2 horas", "para_la_siguiente_clase": "Traer el ejercicio",
                "autochequeo": ["¿Entendí?", "¿Revisé?", "¿Comparé?"], "conexion_pis": "Aporta al módulo"}
    if herramienta == "presentacion":
        d = {"titulo": "Diapositiva de prueba", "puntos": ["Idea uno", "Idea dos"],
             "notas": "Explicar la idea con un ejemplo del sílabo."}
        return {"titulo": "Presentación de la clase", "diapositivas": [d] * 6}
    fase = {"fase": "inicio", "minutos": 20, "docente": "Presenta el tema", "estudiantes": "Responden preguntas"}
    return {"objetivo": texto, "fases": [fase, {**fase, "fase": "desarrollo"}, {**fase, "fase": "cierre"}],
            "preguntas_detonantes": ["¿Por qué?", "¿Cómo?"], "conexion_pis": ""}


def test_las_nuevas_estan_registradas_como_herramientas_de_clase():
    for h in NUEVAS:
        assert h in WORKERS and DEFINICIONES[h].ambito == "clase" and not DEFINICIONES[h].es_quiz


@pytest.mark.parametrize("herramienta", NUEVAS)
def test_genera_valida_verifica_y_presenta(herramienta, silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    definicion = DEFINICIONES[herramienta]
    assert definicion.requisitos(ctx) is None
    cliente = ClienteSimulado({"worker": [json.dumps(_salida(herramienta, ctx))]})
    entrega = WORKERS[herramienta].generar(_tarea(ctx), cliente)
    contenido = {definicion.secciones[0]: entrega.contenido[0]}
    assert definicion.verificar(contenido, ctx) == []
    bloques = presentar(herramienta, contenido)
    assert bloques and all(b["tipo"] in {"texto", "lista", "tabla", "grupo"} for b in bloques)
    # El prompt lleva el JSON de trabajo: sesión con fecha y actividades separadas.
    prompt = "\n".join(m["content"] for m in cliente.llamadas[0]["mensajes"])
    assert f"Sesión {ctx.sesion_numero}" in prompt and "Actividades de trabajo autónomo" in prompt


def test_tarjeta_con_contenido_ajeno_no_pasa(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    datos = _salida("tarjetas", ctx)
    datos["tarjetas"][0]["contenido"] = "Tema que no está en la sesión"
    assert "tarjeta con un contenido ajeno a la sesión" in DEFINICIONES["tarjetas"].verificar({"mazo": datos}, ctx)


def test_copiar_un_entregable_no_pasa(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    datos = _salida("practica_guiada", ctx)
    datos["objetivo"] = ctx.entregables_momento[0]
    assert "copia un entregable del momento" in DEFINICIONES["practica_guiada"].verificar({"practica": datos}, ctx)


def test_sin_actividad_autonoma_o_docente_no_se_ofrecen(silabo):
    ctx = contexto_clase(silabo, "M2-S1").model_copy(update={
        "actividad_autonoma": Actividad(texto=" "), "actividad_docente": None})
    assert "trabajo autónomo" in DEFINICIONES["guia_autonoma"].requisitos(ctx)
    assert "con el docente" in DEFINICIONES["guion_clase"].requisitos(ctx)


@pytest.mark.parametrize("herramienta", NUEVAS)
def test_trabajo_completo_con_coordinador(herramienta, conn, silabo):
    """Generación, verificación y revisión de punta a punta, como en el worker."""
    import re as _re
    from psycopg.types.json import Jsonb
    from app.agentes.coordinador import Coordinador
    from app.agentes.facultades import cargar_perfiles
    from app.agentes.mensajes import Encargo
    from app.cola.trabajos import Ambito, encolar, tomar_siguiente
    from tests.test_coordinador import RAIZ

    ctx = contexto_clase(silabo, "M2-S1")

    def revisor(mensajes):
        opciones = _re.findall(r"^(\d)\) (.+)$", mensajes[-1]["content"], _re.M)
        return json.dumps({"veredictos": [{"opcion": int(k), "valida": True, "motivo": "ok"} for k, _ in opciones],
                           "resuelve_entregable": False, "motivo": "", "entregable": ""})

    cliente = ClienteSimulado({"worker": lambda m: json.dumps(_salida(herramienta, ctx)), "revisor": revisor})
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('p@uti.edu.ec',%s,%s,'ingenierias',%s) returning id",
                       (ctx.codigo_pf, ctx.version_silabo, Jsonb(silabo.model_dump(mode="json")))).fetchone()["id"]
    encolar(conn, asignatura_id=aid, agente="ingenierias", ambito=Ambito("clase", "M2-S1"),
            herramienta=herramienta, parametros={})
    t = tomar_siguiente(conn, "w1", 360)
    e = Encargo(trabajo_id=t.id, asignatura_id=aid, codigo_pf=ctx.codigo_pf, version_silabo=ctx.version_silabo,
                carrera=ctx.carrera, nivel=ctx.nivel, ambito=t.ambito, herramienta=herramienta,
                perfil_dificultad="fundamentacion")
    perfil = cargar_perfiles(RAIZ / "agentes")["ingenierias"]
    cierre = Coordinador(perfil, WORKERS, cliente).ejecutar(conn, t, e, ctx, lambda: True)
    r = conn.execute("select * from recurso").fetchone()
    assert cierre.estado == r["estado"] == "listo"
    assert set(r["contenido"]) == set(DEFINICIONES[herramienta].secciones)


def test_la_presentacion_se_exporta_a_pptx(silabo):
    from io import BytesIO
    from pptx import Presentation
    from app.exportar.pptx import exportar_pptx
    ctx = contexto_clase(silabo, "M2-S1")
    datos = _salida("presentacion", ctx)
    binario = exportar_pptx({"herramienta": "presentacion", "contenido": {"presentacion": datos}}, ctx)
    prs = Presentation(BytesIO(binario))
    diapositivas = list(prs.slides)
    assert len(diapositivas) == 1 + 6 + 1  # portada, contenido y datos del recurso
    assert diapositivas[0].shapes.title.text == "Presentación de la clase"
    assert diapositivas[1].notes_slide.notes_text_frame.text.startswith("Explicar")
    assert "asistencia de IA" in diapositivas[-1].placeholders[1].text_frame.text
