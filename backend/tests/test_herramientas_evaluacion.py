"""Herramientas del plan de evaluación (V3-6): generación, verificación, vista y simulacro acumulativo."""
import json
from uuid import uuid4

import pytest

from app.agentes.mensajes import EstiloFacultad, TareaLote
from app.agentes.planificador import planificar
from app.agentes.workers import WORKERS
from app.agentes.workers.definiciones import DEFINICIONES
from app.evaluacion.herramientas import POR_TIPO, herramientas_de, rangos_acumulados
from app.exportar.html import CON_RESPUESTAS, NOMBRES, exportar_html
from app.exportar.presentacion import legible, presentar, sin_respuestas
from app.herramientas.esquemas_evaluacion import SIN_INDICADOR
from app.llm.cliente import ClienteSimulado
from app.momentos.trazabilidad import numero_momento
from app.silabo.contexto import contexto_clase, contexto_momento, contexto_por_id

ESTILO = EstiloFacultad(tipos_de_caso=["datasets"], software_habitual=["Git"])
NUEVAS = ("guia_practica", "ficha_foro", "guia_tarea", "prueba_diagnostica", "guia_entrega", "insumo_respaldo")
TEXTO = "Texto suficientemente largo para cumplir el mínimo del esquema de la herramienta del plan."


def _tarea(ctx):
    return TareaLote(trabajo_id=uuid4(), asignatura_id=uuid4(), lote=1, ronda=0, contexto=ctx, estilo=ESTILO,
                     plan=planificar(ctx, 4, "fundamentacion")[0], ya_generado=[], devoluciones=[])


def _criterios(ctx, n=3):
    indicador = ctx.rubrica[0].indicador if ctx.rubrica else SIN_INDICADOR
    return [{"criterio": f"Criterio {k}", "indicador_momento": indicador, "destacado": TEXTO,
             "satisfactorio": TEXTO, "en_proceso": TEXTO} for k in range(n)]


def _salida(herramienta, ctx):
    ra = ctx.ra[0].id
    if herramienta == "guia_practica":
        return {"titulo": "Práctica de aprendizaje experimental 1", "objetivo": TEXTO, "ra": ra,
                "materiales": ["Computador con Python"], "procedimiento": ["Preparar", "Ejecutar", "Registrar"],
                "registro": ["Tiempo de ejecución", "Errores encontrados"], "producto": TEXTO,
                "condiciones": ["Dos horas, en parejas"],
                "observacion": [{"criterio": f"Ejecuta el paso {k} del procedimiento", "evidencia": TEXTO}
                                for k in range(4)]}
    if herramienta == "ficha_foro":
        return {"tema": "Decisiones de diseño del proyecto", "contenido": ctx.contenidos[0],
                "pregunta_detonante": "¿Qué decisión tomarías en el reto del proyecto y por qué la defenderías?",
                "aporte_inicial": TEXTO, "replicas": TEXTO, "uso_ia": TEXTO, "rubrica": _criterios(ctx)}
    if herramienta == "guia_tarea":
        return {"producto": TEXTO, "proposito": TEXTO, "ra": ra, "modalidad": "individual",
                "condiciones": ["PDF en el aula virtual", "Individual"], "pasos": ["Leer", "Redactar", "Revisar"],
                "criterios": _criterios(ctx), "uso_ia": TEXTO}
    if herramienta == "prueba_diagnostica":
        pre = [{"nombre": f"Prerrequisito {k}", "por_que": TEXTO} for k in range(3)]
        preguntas = [{"prerrequisito": k % 3 + 1, "pregunta": f"Pregunta diagnóstica número {k} del nivel previo",
                      "opciones": ["Opción A", "Opción B", "Opción C", "Opción D"], "correcta": 1,
                      "explicacion": TEXTO, "si_fallas": "Repasa el tema del nivel previo"} for k in range(6)]
        return {"prerrequisitos": pre, "preguntas": preguntas}
    if herramienta == "guia_entrega":
        indicador = ctx.rubrica[0].indicador if ctx.rubrica else SIN_INDICADOR
        return {"que_se_entrega": TEXTO, "insumo_previo": "El prototipo de la sesión 2", "avance_nuevo": TEXTO,
                "pasos": ["Revisar", "Completar", "Subir"],
                "lista_cotejo": [{"item": f"Incluye la parte {k} del avance", "indicador_momento": indicador}
                                 for k in range(5)], "errores_comunes": ["Subir tarde", "Sin portada"]}
    return {"tarea": TEXTO, "insumo_previo": "El prototipo de la sesión 2", "tipo": "plantilla",
            "descripcion": TEXTO, "contenido": TEXTO * 4, "como_usarlo": ["Descárgalo", "Complétalo"]}


def test_estan_registradas_con_nombre_y_vista():
    for h in NUEVAS:
        assert h in WORKERS and DEFINICIONES[h].ambito == "clase" and not DEFINICIONES[h].es_quiz
        assert h in NOMBRES
    # El insumo de respaldo no va por tipo: se ofrece en las tareas complementarias (V4-2).
    usadas = {h for opciones in POR_TIPO.values() for h, _ in opciones} | {"insumo_respaldo"}
    assert set(NUEVAS) <= usadas and usadas <= set(DEFINICIONES) | {
        "rubrica_momento", "rubrica_final", "lista_evidencia", "autoevaluacion_rubrica", "autoevaluacion_final"}


@pytest.mark.parametrize("herramienta", NUEVAS)
def test_genera_valida_verifica_presenta_y_exporta(herramienta, silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    definicion = DEFINICIONES[herramienta]
    assert definicion.requisitos(ctx) is None
    cliente = ClienteSimulado({"worker": [json.dumps(_salida(herramienta, ctx))]})
    entrega = WORKERS[herramienta].generar(_tarea(ctx), cliente)
    contenido = {definicion.secciones[0]: entrega.contenido[0]}
    assert definicion.verificar(contenido, ctx) == []
    bloques = presentar(herramienta, contenido)
    # La vista propia (no la genérica): ningún bloque con la clave interna como título.
    assert bloques and not any(b["titulo"] in {"Indicador momento", "Ra"} for b in bloques)
    html = exportar_html({"herramienta": herramienta, "contenido": contenido}, ctx)
    assert NOMBRES[herramienta] in html


def test_no_aparecen_en_el_catalogo_general_sino_en_el_plan():
    from app.agentes.workers.definiciones import DEL_PLAN
    assert DEL_PLAN == set(NUEVAS)


def test_el_foro_trae_plazos_desde_la_sesion_y_su_tipo_de_evaluacion(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    cliente = ClienteSimulado({"worker": [json.dumps(_salida("ficha_foro", ctx))]})
    foro = WORKERS["ficha_foro"].generar(_tarea(ctx), cliente).contenido[0]
    assert len(foro["plazos"]) == 2 and "sugerido" in foro["plazos"][0]
    assert "coevaluación" in foro["evaluacion"]


@pytest.mark.parametrize("cambio,fallo", [
    ({"pregunta_detonante": "Explica la importancia del diseño en el proyecto formativo del curso."},
     "la pregunta detonante no es una pregunta"),
    ({"pregunta_detonante": "¿Qué es una variable en el contexto del reto del proyecto formativo?"},
     "la pregunta detonante se responde con una definición"),
    ({"contenido": "Tema que no está en la sesión"}, "el foro usa un contenido ajeno a la sesión"),
])
def test_el_foro_valida_su_pregunta_y_su_contenido(silabo, cambio, fallo):
    ctx = contexto_clase(silabo, "M2-S1")
    foro = {**_salida("ficha_foro", ctx), "plazos": ["x"], "evaluacion": "x", **cambio}
    assert fallo in DEFINICIONES["ficha_foro"].verificar({"foro": foro}, ctx)


def test_indicador_ajeno_y_ra_ajeno_no_pasan(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    tarea = _salida("guia_tarea", ctx)
    tarea["criterios"][0]["indicador_momento"] = "Indicador inventado"
    tarea["ra"] = "RA9"
    fallos = DEFINICIONES["guia_tarea"].verificar({"tarea": tarea}, ctx)
    assert "RA ajeno al momento" in fallos
    assert "criterio alineado a un indicador ajeno a la rúbrica del momento" in fallos


def test_la_diagnostica_cubre_cada_prerrequisito_y_no_repite_opciones(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    d = _salida("prueba_diagnostica", ctx)
    for p in d["preguntas"]:
        p["prerrequisito"] = 1
    d["preguntas"][0]["opciones"] = ["Igual", "igual", "Otra", "Más"]
    fallos = DEFINICIONES["prueba_diagnostica"].verificar({"diagnostica": d}, ctx)
    assert "hay prerrequisitos sin pregunta" in fallos and "la pregunta 1 repite opciones" in fallos


def test_la_diagnostica_del_estudiante_no_lleva_respuestas(silabo):
    ctx = contexto_clase(silabo, "M2-S1")
    bloques = presentar("prueba_diagnostica", {"diagnostica": _salida("prueba_diagnostica", ctx)})
    assert "prueba_diagnostica" in CON_RESPUESTAS
    estudiante = [sin_respuestas(b) for b in bloques]
    assert not any(x["titulo"] == "Respuesta orientativa" for b in estudiante for x in b.get("bloques", []))
    # El HTML (Canvas) es del estudiante: ni la clave ni lo que debe repasar.
    contenido = {"diagnostica": _salida("prueba_diagnostica", ctx)}
    html = exportar_html({"herramienta": "prueba_diagnostica", "contenido": contenido}, ctx)
    assert "Pregunta diagnóstica número 0" in html and 'type="radio"' in html
    assert "Respuesta orientativa" not in html and "Repasa el tema del nivel previo" not in html


def test_sin_actividad_practica_no_se_ofrece_la_guia_de_la_practica(silabo):
    from app.silabo.modelo import Actividad
    ctx = contexto_clase(silabo, "M2-S1").model_copy(update={"actividad_practica": Actividad(texto=" ")})
    assert "práctico-experimentales" in DEFINICIONES["guia_practica"].requisitos(ctx)


# --- Simulacro acumulativo del parcial -------------------------------------------------------

def test_rangos_acumulados_por_prueba_sumativa():
    assert rangos_acumulados(["M4-S4", "M2-S4"]) == {"M2-S4": "M1-M2", "M4-S4": "M3-M4"}
    assert rangos_acumulados(["M1-S3", "M1-S8"]) == {"M1-S3": "M1", "M1-S8": "M1"}
    assert rangos_acumulados(["M3-S2"]) == {"M3-S2": "M1-M3"}


def test_el_simulacro_de_la_prueba_es_del_rango_y_lo_demas_del_momento():
    [simulacro, repaso] = herramientas_de("prueba_sumativa", "M2-S4", "M1-M2")
    assert simulacro == {"herramienta": "simulacro", "ambito": {"tipo": "momento", "id": "M1-M2"}}
    assert repaso["ambito"] == {"tipo": "momento", "id": "M2"}
    assert herramientas_de("prueba_sumativa", "M2-S4")[0]["ambito"]["id"] == "M2"


def test_contexto_de_un_rango_de_momentos(silabo):
    ctx = contexto_momento(silabo, "M2-M3")
    m1, m2 = contexto_momento(silabo, "M2"), contexto_momento(silabo, "M3")
    assert ctx.clase_id == "M2-M3" and ctx.fecha == m1.fecha
    assert set(m1.contenidos) | set(m2.contenidos) == set(ctx.contenidos)
    assert {r.id for r in ctx.ra} == {r.id for r in m1.ra} | {r.id for r in m2.ra}
    assert ctx.rubrica == m2.rubrica and ctx.politica_ia == m2.politica_ia
    assert contexto_por_id(silabo, "M2-M3") == ctx
    assert DEFINICIONES["simulacro"].requisitos(ctx) is None
    for invalido in ("M3-M2", "M1-M3", "M2-M2"):
        with pytest.raises(KeyError):
            contexto_momento(silabo, invalido)


def test_el_rango_se_muestra_y_se_agrupa_en_el_momento_que_cierra():
    assert numero_momento("M1-M2") == 2 and numero_momento("M3") == 3 and numero_momento("M2-S4") == 2
    assert legible("Simulacro de M1-M2") == "Simulacro de Momentos 1 a 2"


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
    assert cierre.estado == r["estado"] == "listo", r["evidencia"]
    assert set(r["contenido"]) == set(DEFINICIONES[herramienta].secciones)


def test_simulacro_acumulativo_se_encola_y_genera_con_el_rango(conn, silabo):
    from psycopg.types.json import Jsonb
    from app.agentes.orquestador import SolicitudGeneracion, crear_trabajos
    from app.cola.trabajos import Ambito
    aid = conn.execute("insert into asignatura (dueno,codigo_pf,version_silabo,agente,silabo) "
                       "values ('p@uti.edu.ec','PF','1','ingenierias',%s) returning id",
                       (Jsonb(silabo.model_dump(mode="json")),)).fetchone()["id"]
    [tid] = crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("momento", "M2-M3"), ["simulacro"], cantidad=4))
    fila = conn.execute("select ambito_tipo, ambito_id from trabajo where id=%s", (tid,)).fetchone()
    assert (fila["ambito_tipo"], fila["ambito_id"]) == ("momento", "M2-M3")
    with pytest.raises(KeyError):
        crear_trabajos(conn, SolicitudGeneracion(aid, Ambito("momento", "M3-M2"), ["simulacro"], cantidad=4))


@pytest.mark.parametrize("herramienta,seccion,cita,otro", [
    ("guia_tarea", "tarea", "producto", "proposito"), ("guia_entrega", "entrega", "que_se_entrega", "avance_nuevo"),
    ("insumo_respaldo", "insumo", "tarea", "descripcion")])
def test_el_campo_que_dice_que_se_entrega_puede_citar_la_entrega_y_el_resto_no(silabo, herramienta, seccion, cita, otro):
    ctx = contexto_clase(silabo, "M2-S1")
    entregable = ctx.entregables_momento[0]
    verificar = DEFINICIONES[herramienta].verificar
    assert verificar({seccion: {**_salida(herramienta, ctx), cita: entregable}}, ctx) == []
    assert "copia un entregable del momento" in verificar({seccion: {**_salida(herramienta, ctx), otro: entregable}}, ctx)


def test_el_plan_no_ofrece_herramientas_que_no_se_pueden_encolar(silabo):
    from app.evaluacion.herramientas import disponibles
    sin_rubrica = silabo.model_copy(update={"rubrica_producto_final": []})
    ofrecidas = herramientas_de("proyecto_final", "M3-S4")
    assert [h["herramienta"] for h in disponibles(silabo, ofrecidas)] == ["guia_producto_final", "rubrica_final"]
    assert disponibles(sin_rubrica, ofrecidas) == []
    assert disponibles(silabo, herramientas_de("prueba_sumativa", "M3-S4", "M2-M9")) == [
        {"herramienta": "repaso_momento", "ambito": {"tipo": "momento", "id": "M3"}}]


def test_en_un_momento_que_excluye_la_ia_solo_se_ofrecen_las_sin_ia(silabo):
    """§9.4: si la política del momento prohíbe la IA en una evaluación, el plan no ofrece herramientas con IA."""
    from app.evaluacion.herramientas import disponibles
    momentos = [m.model_copy(update={"politica_ia": "Prueba sin uso de IA."}) if m.numero == 3 else m
                for m in silabo.momentos]
    restringido = silabo.model_copy(update={"momentos": momentos})
    ofrecidas = herramientas_de("taller_coevaluacion", "M3-S1") + herramientas_de("prueba_sumativa", "M3-S4", "M2-M3")
    assert [h["herramienta"] for h in disponibles(restringido, ofrecidas)] == [
        "rubrica_momento", "autoevaluacion_rubrica"]
    assert [h["herramienta"] for h in disponibles(silabo, herramientas_de("prueba_sumativa", "M3-S4", "M2-M3"))] == [
        "simulacro", "repaso_momento"]
