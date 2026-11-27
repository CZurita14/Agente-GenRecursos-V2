"""Momentos del Proyecto Formativo: trazabilidad, contexto del docente y descarga del perfil.

- `momentos`: cada momento con su fase de la cadena (M1 → M4), su RA, sesiones, evidencia,
  el contexto del docente, la guía de estudio y el estado de sus herramientas.
- `guardar_contexto`: el docente cambia el contexto de un momento; se valida, se guarda con
  historia y lo generado antes queda «por regenerar».
- `descarga`: ZIP «<docente>_<materia>» con lo validado, ordenado por momento.
"""
from contextlib import closing
import io
import re
import unicodedata
import zipfile

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from app.agentes.verificador import PALABRAS_POR_PAGINA, palabras_guia
from app.asignaturas.servicio import exigir_acceso
from app.exportar.html import CON_RESPUESTAS, NOMBRES
from app.momentos.contexto import ContextoInvalido, validar_contexto
from app.momentos.trazabilidad import fase, numero_momento
from app.silabo.modelo import SilaboUTI

_NO_VALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slug(texto: str, largo: int = 60) -> str:
    plano = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", plano.lower()).strip("_")[:largo].strip("_") or "sin_nombre"


def carpeta(texto: str, largo: int = 70) -> str:
    """Nombre de carpeta o archivo legible y válido en Windows."""
    limpio = _NO_VALIDOS.sub("", texto or "").strip(" .")
    return " ".join(limpio.split())[:largo].strip(" .") or "Sin nombre"


def _iso(valor):
    return valor.isoformat() if valor is not None else None


class ServicioMomentos:
    def __init__(self, conexion, recursos):
        self.conexion, self.recursos = conexion, recursos

    def momentos(self, aid, correo):
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            with conn.transaction():
                conn.execute("set local lock_timeout to '2s'")
                a, rol = exigir_acceso(conn, aid, correo)
                return {"rol": rol, "momentos": self._momentos(conn, aid, a)}

    def _momentos(self, conn, aid, a):
        silabo = SilaboUTI.model_validate(a["silabo"])
        contextos = {f["momento"]: f for f in conn.execute(
            "select momento,texto,revision,actualizado,verificaciones from momento_contexto where asignatura_id=%s",
            (aid,)).fetchall()}
        recursos = conn.execute(
            "select distinct on (herramienta,ambito_id) id,herramienta,ambito_id,estado,creado,validado_en,"
            "validado_por is not null validado,case when herramienta='guia_estudio' then contenido end contenido "
            "from recurso where asignatura_id=%s order by herramienta,ambito_id,creado desc", (aid,)).fetchall()
        salida = []
        for m in sorted(silabo.momentos, key=lambda x: x.numero):
            n, mid = m.numero, f"M{m.numero}"
            ctx = contextos.get(n)
            propios = [r for r in recursos if numero_momento(r["ambito_id"]) == n]
            guia = next((r for r in propios if r["herramienta"] == "guia_estudio" and r["ambito_id"] == mid), None)
            guia_validada = guia["validado_en"] if guia is not None and guia["validado"] else None

            def por_regenerar(r, ctx=ctx, guia_validada=guia_validada):
                # Lo generado antes del último contexto, o (salvo la guía) antes de validar la guía.
                return bool((ctx is not None and r["creado"] < ctx["actualizado"]) or
                            (guia_validada is not None and r["herramienta"] != "guia_estudio"
                             and r["creado"] < guia_validada))
            lista = [{"id": str(r["id"]), "herramienta": r["herramienta"],
                      "nombre": NOMBRES.get(r["herramienta"], r["herramienta"]),
                      "ambito_id": r["ambito_id"], "estado": r["estado"], "validado": r["validado"],
                      "por_regenerar": por_regenerar(r)} for r in propios]
            nombre_fase, proposito = fase(n)
            salida.append({
                "numero": n, "id": mid, "titulo": m.titulo,
                "fase": {"nombre": nombre_fase, "proposito": proposito},
                "fecha_inicio": _iso(m.fecha_inicio), "fecha_fin": _iso(m.fecha_fin),
                "ra": [{"id": r.id, "texto": r.texto} for r in silabo.resultados_aprendizaje if r.id in m.ra],
                "evidencia": m.evidencia, "politica_ia": m.politica_ia,
                "sesiones": [{"id": s.id, "numero": s.numero, "fecha": _iso(s.fecha), "contenidos": list(s.contenidos)}
                             for s in m.sesiones],
                "contexto_docente": None if ctx is None else {
                    "texto": ctx["texto"], "revision": ctx["revision"], "actualizado": _iso(ctx["actualizado"]),
                    "verificaciones": ctx["verificaciones"]},
                "guia": None if guia is None else {
                    "recurso_id": str(guia["id"]), "estado": guia["estado"], "validado": guia["validado"],
                    "paginas": round(palabras_guia(guia["contenido"] or {}) / PALABRAS_POR_PAGINA, 1),
                    "fuentes": {k: len(((guia["contenido"] or {}).get("aplicacion") or {}).get("bibliografia", {}).get(k, [])
                                       if isinstance(((guia["contenido"] or {}).get("aplicacion") or {}).get("bibliografia"), dict) else [])
                                for k in ("silabo", "web")},
                    "por_regenerar": por_regenerar(guia)},
                "recursos": lista,
                "resumen": {"total": len(lista), "validados": sum(r["validado"] for r in lista),
                            "por_regenerar": sum(r["por_regenerar"] for r in lista)},
            })
        return salida

    def plan_evaluacion(self, aid, correo):
        """Plan de evaluación implícito en el sílabo: norma, bloques, actividades con su peso y alertas.

        Si faltan columnas por clasificar con IA y quien consulta puede editar, se encola la clasificación
        (una vez por versión del sílabo); mientras tanto se devuelve lo que leen las reglas.
        """
        from app.evaluacion.clasificador import textos_de
        from app.evaluacion.dependencias import alertas_dependencias, dependencias, legible
        from app.evaluacion.herramientas import NOMBRE_TIPO, disponibles, herramientas_de, rangos_acumulados
        from app.evaluacion.norma import bloques as bloques_de
        from app.evaluacion.norma import norma_de
        from app.evaluacion.pesos import calcular, clave, grupos, validar_ajustes
        from app.evaluacion.servicio import huella, pesos_confirmados, plan_actividades, solicitar_clasificacion
        from app.recursos.servicio import _restriccion

        with closing(self.conexion()) as conn:
            conn.autocommit = True
            a, rol = exigir_acceso(conn, aid, correo)
            silabo = SilaboUTI.model_validate(a["silabo"])
            actividades, estado_ia = plan_actividades(conn, aid, silabo)
            if estado_ia in ("pendiente", "error") and rol != "lector":
                estado_ia = solicitar_clasificacion(conn, aid, a["agente"], silabo)
            confirmados, desactualizados = pesos_confirmados(conn, aid, huella(silabo))
        norma = norma_de(silabo.proyecto_formativo.modalidad)
        bloques = bloques_de(silabo, norma, [x.sesion for x in actividades if x.tipo == "prueba_sumativa"])
        textos = textos_de(silabo)
        # Los pesos del docente valen solo si siguen cuadrando con el plan actual (p. ej. tras clasificar con IA).
        ajustes = confirmados["pesos"] if confirmados and not validar_ajustes(
            actividades, norma, bloques, confirmados["pesos"]) else None
        plan = calcular(actividades, norma, bloques, textos, ajustes)
        pesadas = {(p.actividad.sesion, p.actividad.columna, p.actividad.tipo): p for p in plan.actividades}
        bloque_de = {s: b.numero for b in bloques for s in b.sesiones}
        acumulado = rangos_acumulados([x.sesion for x in actividades if x.tipo == "prueba_sumativa" and x.evaluable])

        cache: dict = {}
        deps = dependencias(silabo)
        sugerencias = dict(plan.sugerencias)
        alertas = plan.alertas + alertas_dependencias(silabo, deps, sugerencias)
        dep_de = {(d.sesion, d.columna): d for d in deps}

        def dependencia(d):
            if d is None or d.tipo != "complementaria":
                return None
            return {"insumo": d.insumo, "origen": d.origen, "origen_legible": legible(d.origen) if d.origen else None,
                    "roto": d.roto, "revisar": d.revisar}

        def fila(act):
            p = pesadas.get((act.sesion, act.columna, act.tipo))
            d = dep_de.get((act.sesion, act.columna))
            return {"clave": clave(act), "sesion": act.sesion, "momento": int(act.sesion.split("-")[0][1:]),
                    "columna": act.columna,
                    "texto": textos.get(f"{act.sesion}/{act.columna}", ""), "tipo": act.tipo,
                    "nombre_tipo": NOMBRE_TIPO.get(act.tipo, act.tipo), "evaluable": act.evaluable,
                    "calificacion": act.calificacion, "instrumento": act.instrumento, "finalidad": act.finalidad,
                    "agente": act.agente, "origen": act.origen, "bloque": bloque_de.get(act.sesion),
                    "peso_bloque": p.peso_bloque if p else 0, "peso_final": p.peso_final if p else 0,
                    "dependencia": dependencia(d),
                    "herramientas": disponibles(silabo, herramientas_de(act.tipo, act.sesion, acumulado.get(act.sesion), d),
                                                 cache)}

        return {
            "rol": rol, "modalidad": silabo.proyecto_formativo.modalidad,
            "norma": None if norma is None else {
                "modalidad": norma.modalidad, "estado": norma.estado, "bloques": norma.bloques, "pesos": norma.pesos,
                "componentes": norma.componentes, "c5": norma.c5, "c4": norma.c4},
            "bloques": [{"numero": b.numero, "nombre": b.nombre, "inicio": _iso(b.inicio), "fin": _iso(b.fin),
                         "sesiones": b.sesiones} for b in bloques],
            "clasificacion_ia": estado_ia, "por_bloque": plan.por_bloque, "por_momento": plan.por_momento,
            "alertas": alertas, "avisos": [{"texto": a, "sugerencia": sugerencias.get(a)} for a in alertas],
            "actividades": [fila(x) for x in actividades],
            # V4-4: de dónde salen los pesos y qué puede repartir el docente (dentro de cada calificación).
            "pesos": {"origen": "docente" if ajustes else "sugeridos",
                      "confirmado_por": confirmados["confirmado_por"] if ajustes else None,
                      "confirmado_en": confirmados["confirmado_en"].isoformat() if ajustes else None,
                      "desactualizados": desactualizados or bool(confirmados and not ajustes)},
            "grupos": grupos(actividades, norma, bloques) if norma is not None and norma.estado == "definida" else [],
            # §9.4: momentos cuya política de IA excluye la IA en una evaluación; ahí solo hay herramientas sin IA.
            "ia_restringida": {str(m.numero): motivo for m in silabo.momentos
                               if (motivo := _restriccion(silabo, "momento", f"M{m.numero}"))},
        }

    def guardar_pesos(self, aid, correo, pesos: dict):
        """V4-4: el docente confirma o ajusta los pesos; cada calificación de cada bloque conserva su % de la norma."""
        from app.evaluacion.norma import bloques as bloques_de
        from app.evaluacion.norma import norma_de
        from app.evaluacion.pesos import validar_ajustes
        from app.evaluacion.servicio import guardar_pesos, huella, plan_actividades

        with closing(self.conexion()) as conn:
            with conn.transaction():
                a, _ = exigir_acceso(conn, aid, correo, editar=True)
                silabo = SilaboUTI.model_validate(a["silabo"])
                actividades, estado_ia = plan_actividades(conn, aid, silabo)
                if estado_ia in ("pendiente", "en_curso"):
                    raise HTTPException(409, "Espera a que termine la clasificación con IA antes de confirmar los pesos.")
                norma = norma_de(silabo.proyecto_formativo.modalidad)
                bloques = bloques_de(silabo, norma, [x.sesion for x in actividades if x.tipo == "prueba_sumativa"])
                pesos = {k: round(float(v), 2) for k, v in pesos.items()}
                if errores := validar_ajustes(actividades, norma, bloques, pesos):
                    raise HTTPException(422, " ".join(errores))
                guardar_pesos(conn, aid, huella(silabo), pesos, correo)
        return self.plan_evaluacion(aid, correo)

    def restaurar_pesos(self, aid, correo):
        """Vuelve a los pesos sugeridos para la versión actual del sílabo."""
        from app.evaluacion.servicio import borrar_pesos, huella

        with closing(self.conexion()) as conn:
            with conn.transaction():
                a, _ = exigir_acceso(conn, aid, correo, editar=True)
                borrar_pesos(conn, aid, huella(SilaboUTI.model_validate(a["silabo"])))
        return self.plan_evaluacion(aid, correo)

    def guardar_contexto(self, aid, correo, numero, revision, texto):
        try:
            limpio, controles = validar_contexto(texto)
        except ContextoInvalido as e:
            raise HTTPException(422, "El contexto no pasó la validación: " + " ".join(e.motivos)) from None
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            with conn.transaction():
                conn.execute("set local lock_timeout to '2s'")
                a, _ = exigir_acceso(conn, aid, correo, editar=True)
                silabo = SilaboUTI.model_validate(a["silabo"])
                if not any(m.numero == numero for m in silabo.momentos):
                    raise HTTPException(404, "Momento inexistente en este Proyecto Formativo")
                actual = conn.execute("select texto,revision from momento_contexto where asignatura_id=%s and "
                                      "momento=%s for update", (aid, numero)).fetchone()
                if (actual["revision"] if actual else 0) != revision:
                    raise HTTPException(409, "El contexto cambió; recárguelo antes de guardar")
                if actual is not None and actual["texto"] == limpio:
                    return self._uno(conn, aid, a, numero)
                nueva = revision + 1
                conn.execute(
                    "insert into momento_contexto (asignatura_id,momento,texto,revision,actualizado_por,verificaciones) "
                    "values (%s,%s,%s,%s,%s,%s) on conflict (asignatura_id,momento) do update set texto=excluded.texto,"
                    "revision=excluded.revision,actualizado_por=excluded.actualizado_por,actualizado=clock_timestamp(),"
                    "verificaciones=excluded.verificaciones", (aid, numero, limpio, nueva, correo, Jsonb(controles)))
                conn.execute("insert into momento_contexto_historial (asignatura_id,momento,revision,texto_anterior,"
                             "texto_nuevo,usuario) values (%s,%s,%s,%s,%s,%s)",
                             (aid, numero, nueva, actual["texto"] if actual else "", limpio, correo))
                return self._uno(conn, aid, a, numero)

    def _uno(self, conn, aid, a, numero):
        return next(m for m in self._momentos(conn, aid, a) if m["numero"] == numero)

    # --- Descarga del perfil docente ------------------------------------------------

    def _validados(self, aid, correo):
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            with conn.transaction():
                a, rol = exigir_acceso(conn, aid, correo)
                filas = conn.execute(
                    "select distinct on (herramienta,ambito_id) id,herramienta,ambito_id from recurso "
                    "where asignatura_id=%s and validado_por is not null "
                    "order by herramienta,ambito_id,validado_en desc", (aid,)).fetchall()
                docente = conn.execute("select nombre from docente where correo=%s", (a["dueno"],)).fetchone()
                momentos = self._momentos(conn, aid, a)
        nombre = docente["nombre"] if docente and docente["nombre"].strip() else a["dueno"].split("@")[0]
        silabo = SilaboUTI.model_validate(a["silabo"])
        raiz = f"{slug(nombre)}_{slug(silabo.proyecto_formativo.nombre)}"
        return silabo, rol, filas, raiz, momentos

    def resumen_descarga(self, aid, correo):
        _, _, filas, raiz, momentos = self._validados(aid, correo)
        return {"carpeta": raiz, "validados": len(filas),
                "asignatura": sum(1 for f in filas if f["ambito_id"] == "asignatura"),
                "momentos": [{"numero": m["numero"], "titulo": m["titulo"], "fase": m["fase"]["nombre"],
                              **m["resumen"], "guia_validada": bool(m["guia"] and m["guia"]["validado"])}
                             for m in momentos]}

    def descarga(self, aid, correo):
        silabo, rol, filas, raiz, momentos = self._validados(aid, correo)
        if not filas:
            raise HTTPException(409, "No hay herramientas validadas para descargar")
        titulos = {m["numero"]: m for m in momentos}
        buffer, fallidos, incluidos = io.BytesIO(), [], 0
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(filas, key=lambda x: (x["ambito_id"], x["herramienta"] != "guia_estudio", x["herramienta"])):
                n = numero_momento(f["ambito_id"])
                if n is None:
                    destino = f"{raiz}/00 Proyecto formativo"
                else:
                    m = titulos.get(n)
                    destino = f"{raiz}/{n:02d} Momento {n} - {carpeta(m['titulo'] if m else '')}"
                    if f["ambito_id"] != f"M{n}":
                        destino += "/Clases"
                versiones = [("pptx" if f["herramienta"] == "presentacion" else "docx", "estudiante")]
                if f["herramienta"] in CON_RESPUESTAS and rol != "lector":
                    versiones.append(("docx", "docente"))
                for formato, version in versiones:
                    try:
                        nombre, contenido = self.recursos.exportar(aid, f["id"], correo, formato, version)
                    except HTTPException:
                        fallidos.append(f"{NOMBRES.get(f['herramienta'], f['herramienta'])} ({f['ambito_id']})")
                        continue
                    sub = "/Respuestas del docente" if version == "docente" else ""
                    z.writestr(f"{destino}{sub}/{carpeta(nombre, 150)}", contenido)
                    incluidos += 1
            lineas = [f"Proyecto Formativo: {silabo.proyecto_formativo.nombre}",
                      f"Archivos incluidos: {incluidos} (solo herramientas validadas por el docente).", "",
                      "Trazabilidad de momentos:"]
            for m in momentos:
                r = m["resumen"]
                lineas.append(f"- Momento {m['numero']} · {m['fase']['nombre']}: {m['titulo']} — "
                              f"{r['validados']} de {r['total']} validadas"
                              + (f", {r['por_regenerar']} por regenerar" if r["por_regenerar"] else ""))
            if fallidos:
                lineas += ["", "No se pudieron exportar (revíselas en el sistema):", *[f"- {x}" for x in fallidos]]
            z.writestr(f"{raiz}/LEEME.txt", "\r\n".join(lineas) + "\r\n")
        return f"{raiz}.zip", buffer.getvalue()
