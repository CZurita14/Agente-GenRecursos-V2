"""Coordinación durable por facultad: generación, control y cierre con lease."""
from collections.abc import Callable
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.agentes.evidencia import PaqueteEvidencia
from app.agentes.facultades import estilo_para
from app.agentes.mensajes import (
    CheckpointRevision, Cierre, Devolucion, Encargo, EntregaLote, PlanRazonado, TareaLote, Veredicto, guardar, leer,
)
from app.agentes.planificador import NIVELES, estilo_razonado, planificar, tabla_especificaciones
from app.agentes.revisor import revisar_ficha, revisar_items
from app.agentes.verificador import verificar_distribucion, verificar_items
from app.agentes.workers.definiciones import DEFINICIONES
from app.herramientas.esquemas import ItemCuestionario
from app.llm.cliente import JsonInvalido
from app.silabo.contexto import contexto_ambito
from app.silabo.modelo import SilaboUTI


class LeasePerdido(Exception):
    """La ejecución abandonó el trabajo; otro worker puede retomarlo."""


class _ClienteConLease:
    """Controla cada llamada (incluidos reintentos internos) y acumula uso real."""
    def __init__(self, cliente, comprobar, registrar_tokens):
        self.cliente = cliente
        self.comprobar = comprobar
        self.registrar_tokens = registrar_tokens

    @property
    def contexto_max(self) -> int:
        from app.llm.prompts import limite_contexto
        return limite_contexto(self.cliente)

    def contar_tokens(self, mensajes):
        self.comprobar()
        n = self.cliente.contar_tokens(mensajes)
        self.comprobar()
        return n

    def completar(self, mensajes, **kw):
        self.comprobar()
        respuesta = self.cliente.completar(mensajes, **kw)
        self.comprobar()
        self.registrar_tokens((respuesta.tokens_entrada, respuesta.tokens_salida))
        return respuesta


class Coordinador:
    def __init__(self, perfil, workers, cliente, razonador=None):
        self.perfil, self.workers, self.cliente, self.razonador = perfil, workers, cliente, razonador

    def ejecutar(self, conn, trabajo, encargo: Encargo, contexto, latido: Callable[[], bool]) -> Cierre:
        if (encargo.trabajo_id, encargo.asignatura_id, encargo.codigo_pf, encargo.version_silabo,
            encargo.ambito, encargo.herramienta) != (
                trabajo.id, trabajo.asignatura_id, contexto.codigo_pf, contexto.version_silabo,
                trabajo.ambito, trabajo.herramienta):
            raise ValueError("encargo y contexto no corresponden al trabajo")
        if contexto.clase_id != trabajo.ambito.id or self.perfil.id != trabajo.agente:
            raise ValueError("clase o agente ajeno al trabajo")
        asignatura = conn.execute("select codigo_pf,silabo from asignatura where id=%s", (trabajo.asignatura_id,)).fetchone()
        if asignatura is None or asignatura["codigo_pf"] != contexto.codigo_pf:
            raise ValueError("contexto ajeno a la asignatura persistida")
        fuente = SilaboUTI.model_validate(trabajo.parametros.get("silabo", asignatura["silabo"]))
        if contexto_ambito(fuente, trabajo.ambito) != contexto:
            raise ValueError("el contexto no corresponde al sílabo del trabajo")
        worker = self.workers[trabajo.herramienta]
        definicion = DEFINICIONES[trabajo.herramienta]
        es_quiz = definicion.es_quiz
        cantidad = trabajo.parametros.get("cantidad", 12)
        ids = dict(trabajo_id=trabajo.id, asignatura_id=trabajo.asignatura_id)

        def bloquear():
            fila = conn.execute(
                "select * from trabajo where id=%s and worker_id=%s and lease_version=%s "
                "and estado in ('generando','verificando','revisando') "
                "and lease_hasta > clock_timestamp() for update",
                (trabajo.id, trabajo.worker_id, trabajo.lease_version),
            ).fetchone()
            if fila is None:
                raise LeasePerdido("el trabajo perdió su lease")
            return fila

        def comprobar():
            with conn.transaction():
                bloquear()
            if not latido():
                raise LeasePerdido("el latido no pudo renovar el lease")
            with conn.transaction():
                bloquear()

        def persistir(mensajes=(), *, estado=None, lote_cerrado=False, ronda=None, tokens=(0, 0)):
            with conn.transaction():
                fila = bloquear()
                for mensaje in mensajes:
                    guardar(conn, mensaje)
                conn.execute(
                    "update trabajo set estado=coalesce(%s,estado), lotes_total=%s, "
                    "lotes_hechos=lotes_hechos+%s, rondas_revision=coalesce(%s,rondas_revision), "
                    "tokens_entrada=tokens_entrada+%s, tokens_salida=tokens_salida+%s, "
                    "actualizado=clock_timestamp() where id=%s",
                    (estado, len(planes), int(lote_cerrado), ronda, *tokens, trabajo.id),
                )
            return fila

        comprobar()
        existentes = leer(conn, trabajo.id)
        encargos = [m for m in existentes if isinstance(m, Encargo)]
        if encargos and encargos[0] != encargo:
            raise ValueError("el encargo cambió al reanudar")
        guardado = next((m for m in existentes if isinstance(m, PlanRazonado)), None)
        if guardado is not None:
            # El plan guardado manda sobre el modelo instalado, o sobre su ausencia.
            razonador_version = guardado.version
            estilo = estilo_para(self.perfil, encargo.carrera).model_copy(update={"escenarios": guardado.escenarios})
            planes = guardado.planes if es_quiz else [[] for _ in definicion.secciones]
        else:
            # Encargo sin plan guardado: empezó sin razonador y sus lotes entregados siguen ese plan.
            razonador = None if encargos else self.razonador
            razonador_version = razonador.version if razonador is not None else None
            estilo = estilo_razonado(self.perfil, encargo.carrera, contexto, razonador)
            planes = (planificar(contexto, cantidad, encargo.perfil_dificultad, escenarios=estilo.escenarios,
                                 razonador=razonador)
                      if es_quiz else [[] for _ in definicion.secciones])
        if not encargos:
            # Encargo y plan se confirman juntos: un encargo sin plan prueba que no hubo razonador.
            persistir([encargo, *([PlanRazonado(**ids, version=razonador_version, planes=planes,
                                                escenarios=estilo.escenarios)]
                                  if razonador_version is not None else [])])
        cliente = _ClienteConLease(self.cliente, comprobar, lambda t: persistir(tokens=t))
        entregas = [m for m in existentes if isinstance(m, EntregaLote)]
        primeras = {}
        for entrega in entregas:
            primeras.setdefault(entrega.lote, entrega)
        contenido = {}
        secciones = {}

        def incorporar(entrega):
            if es_quiz:
                for item in entrega.contenido:
                    contenido[item["item_id"]] = item
            else:
                secciones[definicion.secciones[entrega.lote - 1]] = entrega.contenido[0]

        for entrega in entregas:
            incorporar(entrega)

        def verificar(entrega, plan):
            if (entrega.trabajo_id, entrega.asignatura_id) != (trabajo.id, trabajo.asignatura_id):
                raise ValueError("entrega de otro trabajo o asignatura")
            if es_quiz:
                items = [ItemCuestionario.model_validate(i) for i in entrega.contenido]
                if [i.item_id for i in items] != [p.item_id for p in plan]:
                    raise JsonInvalido("la entrega no contiene exactamente los ítems del plan")
                previos = [i["pregunta"] for k, i in contenido.items() if k not in {p.item_id for p in plan}]
                return verificar_items(items, plan, contexto, previos, entrega.asignatura_id, trabajo.asignatura_id)
            definicion.modelos[entrega.lote - 1].model_validate(entrega.contenido[0])
            return {definicion.id_revision: definicion.verificar(entrega.contenido[0], contexto)}

        def generar(lote, plan, ronda, devoluciones):
            tarea = TareaLote(**ids, lote=lote, ronda=ronda, contexto=contexto, estilo=estilo,
                              plan=plan, ya_generado=[i["pregunta"] for k, i in contenido.items()
                                                     if k not in {p.item_id for p in plan}],
                              devoluciones=devoluciones, instrucciones=encargo.instrucciones)
            persistir([tarea], estado="generando")
            comprobar()
            entrega = worker.generar(tarea, cliente)
            comprobar()
            if (entrega.lote, entrega.ronda) != (lote, ronda):
                raise ValueError("lote o ronda ajenos a la tarea")
            persistir(estado="verificando")
            return entrega, verificar(entrega, plan)

        for numero, plan in enumerate(planes, 1):
            if numero in primeras:
                continue
            anteriores = [m for m in existentes if isinstance(m, TareaLote) and m.lote == numero]
            inicio = len(anteriores)
            if inicio >= 3:
                raise JsonInvalido("lote sin entrega tras agotar tres intentos durables")
            devoluciones = anteriores[-1].devoluciones if anteriores else []
            for intento in range(inicio, 3):
                try:
                    entrega, fallos = generar(numero, plan, intento, devoluciones)
                except JsonInvalido:
                    if intento == 2:
                        raise
                    devoluciones = [Devolucion(**ids, item_id="lote", motivo="JSON o cantidad de ítems inválidos", ronda=intento+1)]
                    persistir(devoluciones)
                    continue
                if not any(fallos.values()) or intento == 2:
                    break
                devoluciones = [Devolucion(**ids, item_id=k, motivo="; ".join(f), ronda=intento+1)
                                for k, f in fallos.items() if f]
                persistir(devoluciones)
            persistir([entrega], lote_cerrado=True)
            incorporar(entrega)

        plan_total = [p for lote in planes for p in lote]

        def revisar(previos, objetivos=None):
            """Revisa los objetivos (None = todos) y guarda el veredicto completo, fusionado."""
            persistir(estado="revisando")
            if not es_quiz:
                resultados = [revisar_ficha(secciones, contexto, cliente, item_id=definicion.id_revision, **ids)]
            else:
                nuevos = revisar_items([ItemCuestionario.model_validate(contenido[p.item_id])
                                        for p in plan_total if objetivos is None or p.item_id in objetivos],
                                       contexto, cliente, **ids)
                fusion = {r.item_id: r for r in previos} | {r.item_id: r for r in nuevos}
                resultados = [fusion[p.item_id] for p in plan_total]
            persistir([Veredicto(**ids, resultados=resultados)])
            return resultados

        def ultimo(tipo):
            return max((k for k, m in enumerate(existentes) if isinstance(m, tipo)), default=-1)

        # Al retomar se reutiliza el último veredicto guardado; solo se revisa lo que aún no lo tiene.
        k_veredicto, k_checkpoint = ultimo(Veredicto), ultimo(CheckpointRevision)
        checkpoint = existentes[k_checkpoint] if k_checkpoint >= 0 else None
        if k_veredicto < 0:
            resultados = revisar([])
        elif checkpoint is not None and not checkpoint.pendientes and k_veredicto < k_checkpoint:
            resultados = revisar(existentes[k_veredicto].resultados, set(checkpoint.motivos))
        else:
            resultados = existentes[k_veredicto].resultados
        ronda_hecha = checkpoint.ronda if checkpoint else 0
        while True:
            if checkpoint is None or not checkpoint.pendientes:
                devueltos = [r for r in resultados if r.revisor == "devuelto"]
                if not devueltos or ronda_hecha >= 2:
                    break
                ronda_hecha += 1
                motivos = {r.item_id: r.motivo for r in devueltos}
                pendientes = (list(motivos) if es_quiz else
                              [f"{definicion.id_revision}-{k}" for k in range(1, len(definicion.secciones) + 1)])
                checkpoint = CheckpointRevision(**ids, ronda=ronda_hecha, pendientes=pendientes, motivos=motivos)
                persistir([checkpoint], ronda=ronda_hecha)
            for objetivo in list(checkpoint.pendientes):
                item_id = objetivo if es_quiz else definicion.id_revision
                numero = (1 + next(i for i, lote in enumerate(planes) if any(p.item_id == item_id for p in lote))
                          if es_quiz else int(objetivo.rsplit("-", 1)[1]))
                plan = [p for p in plan_total if p.item_id == item_id] if es_quiz else []
                devolucion = Devolucion(**ids, item_id=item_id, motivo=checkpoint.motivos[item_id], ronda=checkpoint.ronda)
                persistir([devolucion])
                entrega, fallos = generar(numero, plan, checkpoint.ronda, [devolucion])
                if any(fallos.values()):
                    # Una corrección que rompe la verificación se reintenta una vez con sus fallos.
                    reintento = [Devolucion(**ids, item_id=k, motivo="; ".join(f), ronda=checkpoint.ronda)
                                 for k, f in fallos.items() if f]
                    persistir(reintento)
                    entrega, _ = generar(numero, plan, checkpoint.ronda, [devolucion, *reintento])
                siguiente = checkpoint.model_copy(update={"pendientes": [p for p in checkpoint.pendientes if p != objetivo]})
                # Entrega y avance de ronda se confirman juntos; una caída no omite objetivos.
                persistir([entrega, siguiente])
                checkpoint = siguiente
                incorporar(entrega)
            resultados = revisar(resultados, set(checkpoint.motivos))

        if es_quiz:
            items = [ItemCuestionario.model_validate(contenido[p.item_id]) for p in plan_total]
            fallos = verificar_items(items, plan_total, contexto, [], trabajo.asignatura_id, trabajo.asignatura_id)
            tabla = tabla_especificaciones(cantidad, encargo.perfil_dificultad)
            distribucion = verificar_distribucion(items, tabla)
            reales = {n: sum(i.nivel == n for i in items) for n in NIVELES}
            recurso_contenido = [i.model_dump() for i in items]
        else:
            fallos = {definicion.id_revision: definicion.verificar(secciones, contexto)}
            tabla, reales, distribucion, recurso_contenido = {}, {}, [], secciones
        estado = "requiere_revision" if (any(fallos.values()) or distribucion or
                                         any(r.revisor != "ok" for r in resultados)) else "listo"
        comprobar()
        with conn.transaction():
            fila = bloquear()  # Escritura y cierre bajo el mismo bloqueo; sin HTTP dentro.
            tokens = (fila["tokens_entrada"], fila["tokens_salida"])
            evidencia = PaqueteEvidencia(
                clase_id=contexto.clase_id, momento=contexto.momento_titulo,
                ra=[r.id for r in contexto.ra], contenidos=contexto.contenidos,
                agente=self.perfil.id, perfil_dificultad=encargo.perfil_dificultad,
                tabla_planificada=tabla, tabla_real=reales, verificaciones=fallos,
                veredictos={r.item_id: r.motivo or r.revisor for r in resultados},
                devoluciones=sum(isinstance(m, Devolucion) for m in leer(conn, trabajo.id)),
                tokens=tokens, borrador=es_quiz, motivos_revision=distribucion,
                razonador_version=razonador_version,
            )
            rid = uuid4()
            conn.execute(
                "insert into recurso(id,trabajo_id,asignatura_id,ambito_id,herramienta,version_silabo,contenido,evidencia,estado) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (rid, trabajo.id, trabajo.asignatura_id, contexto.clase_id, trabajo.herramienta,
                 encargo.version_silabo, Jsonb(recurso_contenido), Jsonb(evidencia.model_dump(mode="json")), estado),
            )
            cierre = Cierre(**ids, recurso_id=rid, estado=estado, tokens=tokens)
            guardar(conn, cierre)
            conn.execute("update trabajo set estado=%s, worker_id=null, lease_hasta=null, "
                         "actualizado=clock_timestamp() where id=%s", (estado, trabajo.id))
        return cierre
