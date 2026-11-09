"""Generación, seguimiento y recursos, con permisos y pertenencia transaccionales."""
import re
from contextlib import closing, contextmanager

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from app.agentes.orquestador import SolicitudGeneracion, crear_trabajos
from app.agentes.planificador import perfil_por_nivel
from app.agentes.workers import WORKERS
from app.agentes.verificador import revision_claves
from app.agentes.workers.definiciones import DEFINICIONES
from app.asignaturas.servicio import exigir_acceso
from app.herramientas.sin_ia import HERRAMIENTAS_SIN_IA, generar_sin_ia
from app.recursos.validacion import EdicionInvalida, validar_contenido
from app.exportar.html import CON_RESPUESTAS, exportar_html, nombre_archivo
from app.exportar.presentacion import es_quiz, presentar, sin_respuestas
from app.herramientas.politica import excluye_ia_en_evaluacion
from app.silabo.contexto import contexto_por_id
from app.silabo.modelo import SilaboUTI


def _recurso(conn, aid, rid, *, editar=False):
    fila = conn.execute("select r.*,t.parametros snapshot,(select e.revision_ia from recurso_edicion e where "
                        "e.recurso_id=r.id and e.revision=r.revision) revision_ia from recurso r join trabajo t "
                        "on t.id=r.trabajo_id and t.asignatura_id=r.asignatura_id "
                        "where r.id=%s and r.asignatura_id=%s" + (" for update of r" if editar else ""),
                        (rid, aid)).fetchone()
    if fila is None:
        raise HTTPException(404, "Recurso inexistente en este Proyecto Formativo")
    return fila


def _contexto(recurso, asignatura):
    datos = recurso["snapshot"].get("silabo")
    if datos is None:
        # El número de versión no garantiza igualdad de contenido. No sustituir
        # una instantánea ausente por el sílabo actual para validar una edición.
        raise HTTPException(409, "El contexto original del recurso no está disponible")
    try:
        return contexto_por_id(SilaboUTI.model_validate(datos), recurso["ambito_id"])
    except (ValueError, KeyError):
        raise HTTPException(409, "El contexto original del recurso no está disponible") from None


def _restriccion(silabo: SilaboUTI, tipo: str, ambito_id: str | None) -> str | None:
    """§9.4 regla 2: motivo si el momento del ámbito excluye la IA en una evaluación."""
    numero = None
    if tipo in ("clase", "momento") and ambito_id:
        m = re.fullmatch(r"M(\d+)(?:-S\d+)?", ambito_id)
        numero = int(m.group(1)) if m else None
    momento = next((x for x in silabo.momentos if x.numero == numero), None)
    if momento is not None and excluye_ia_en_evaluacion(momento.politica_ia):
        return ("La política de IA de este momento excluye la IA en una evaluación, así que aquí no se "
                "generan herramientas con IA (§9.4).")
    return None


def _actualizado_sin_ia(recurso, asignatura) -> bool:
    """Sin IA: cambió si regenerar con el sílabo actual da otro contenido que con la instantánea."""
    try:
        original = generar_sin_ia(recurso["herramienta"], SilaboUTI.model_validate(recurso["snapshot"]["silabo"]),
                                  recurso["ambito_id"])
        actual = generar_sin_ia(recurso["herramienta"], SilaboUTI.model_validate(asignatura["silabo"]),
                                recurso["ambito_id"])
    except (ValueError, KeyError, TypeError):
        return True
    return original != actual


def _detalle(recurso, asignatura):
    campos = ("id", "trabajo_id", "asignatura_id", "ambito_id", "herramienta", "version_silabo",
              "version_esquema", "contenido", "evidencia", "estado", "revision", "creado",
              "actualizado", "verificacion_edicion", "validado_por", "validado_en")
    resultado = {k: recurso[k] for k in campos}
    resultado["validado"] = recurso["validado_por"] is not None
    resultado['revision_ia'] = recurso.get('revision_ia')
    resultado["presentacion"] = presentar(recurso["herramienta"], recurso["contenido"])
    # Sobre lo guardado: también cubre lo generado antes de esta comprobación y lo editado después.
    resultado["revision_claves"] = revision_claves(recurso["contenido"])
    resultado["evidencia_vigente"] = recurso["revision"] == 0
    if recurso["herramienta"] in HERRAMIENTAS_SIN_IA:
        resultado["silabo_actualizado"] = _actualizado_sin_ia(recurso, asignatura)
        return resultado
    actualizado = recurso["version_silabo"] != asignatura["version_silabo"]
    try:
        original = _contexto(recurso, asignatura)
        actual = contexto_por_id(SilaboUTI.model_validate(asignatura["silabo"]), recurso["ambito_id"])
        actualizado = actualizado or original.model_dump(exclude={"version_silabo"}) != actual.model_dump(exclude={"version_silabo"})
    except (HTTPException, ValueError, KeyError):
        actualizado = True
    resultado["silabo_actualizado"] = actualizado
    return resultado


def _sin_clave(contenido):
    """Lista de campos permitidos: lo que se agregue al esquema no se filtra por omisión."""
    if es_quiz(contenido):
        return [{"item_id": i.get("item_id"), "contexto": i.get("contexto"), "pregunta": i.get("pregunta"),
                 "opciones": [{"texto": o.get("texto")} for o in i.get("opciones", [])]} for i in contenido]
    try:
        caso = contenido["caso"]
        return {"caso": {"caso": caso["caso"], "ra": caso["ra"],
                         "preguntas": [{"nivel": p["nivel"], "pregunta": p["pregunta"]} for p in caso["preguntas"]]}}
    except (KeyError, TypeError):
        return {}  # Forma no prevista: mejor no mostrar nada que arriesgar una respuesta.


# Lo único que recibe quien solo lee: un campo nuevo del detalle no se expone por omisión.
CAMPOS_LECTOR = ("id", "trabajo_id", "asignatura_id", "ambito_id", "herramienta", "version_silabo", "version_esquema",
                 "estado", "revision", "creado", "actualizado", "validado", "validado_por", "validado_en",
                 "silabo_actualizado", "evidencia_vigente")


def _para_lector(detalle):
    """Quien solo lee recibe lo mismo que el estudiante: sin claves, explicaciones ni alertas sobre ellas."""
    if detalle["herramienta"] not in CON_RESPUESTAS:
        return detalle
    return {**{k: detalle[k] for k in CAMPOS_LECTOR if k in detalle},
            "contenido": _sin_clave(detalle["contenido"]), "evidencia": {}, "revision_claves": {},
            "verificacion_edicion": None, "revision_ia": None,
            "presentacion": [sin_respuestas(b) for b in detalle["presentacion"]]}


class ServicioRecursos:
    def __init__(self, conexion, perfiles):
        self.conexion, self.perfiles = conexion, perfiles

    @contextmanager
    def _acceso(self, aid, correo, *, editar=False):
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            with conn.transaction():
                conn.execute("set local lock_timeout to '2s'")
                asignatura, _ = exigir_acceso(conn, aid, correo, editar=editar)
                yield conn, asignatura

    def catalogo(self, aid, correo, ambito, ambito_id=None):
        with self._acceso(aid, correo) as (_, a):
            silabo = SilaboUTI.model_validate(a["silabo"])
            motivo = _restriccion(silabo, ambito, ambito_id)
            contexto = None
            if ambito_id is not None:
                try:
                    contexto = (contexto_por_id(silabo, ambito_id)
                                if ambito != "asignatura" or ambito_id == "asignatura" else None)
                except KeyError:
                    contexto = None
                if contexto is None:
                    raise HTTPException(404, "Ámbito inexistente en este Proyecto Formativo")
            recomendaciones = self.perfiles[a["agente"]].herramientas_recomendadas.get(ambito, [])
            con_ia = [] if motivo else [h for h in WORKERS if h in DEFINICIONES and DEFINICIONES[h].ambito == ambito
                                        and (contexto is None or DEFINICIONES[h].requisitos(contexto) is None)]
            disponibles = con_ia + [h for h, tipo in HERRAMIENTAS_SIN_IA.items() if tipo == ambito]
            orden = [h for h in recomendaciones if h in disponibles]
            orden += sorted(h for h in disponibles if h not in orden)
            return {"ambito": ambito, "restringido": motivo is not None, "motivo": motivo,
                    # La detección no es exhaustiva: el docente ve siempre la política para juzgar.
                    "politica_ia": contexto.politica_ia if contexto is not None else None,
                    "perfil_sugerido": perfil_por_nivel(silabo.proyecto_formativo.nivel),
                    "herramientas": [{"id": h, "recomendada": h in recomendaciones} for h in orden]}

    def generar(self, aid, correo, ambito, herramientas, cantidad, instrucciones, perfil):
        with self._acceso(aid, correo, editar=True) as (conn, a):
            if any(h in HERRAMIENTAS_SIN_IA for h in herramientas):
                return self._generar_sin_ia(conn, aid, a, ambito, herramientas)
            motivo = _restriccion(SilaboUTI.model_validate(a["silabo"]), ambito.tipo, ambito.id)
            if motivo:
                raise HTTPException(422, motivo)
            # Pedir otra vez lo que ya está en curso no gasta GPU: se sigue el trabajo existente.
            activos = {} if instrucciones else {f["herramienta"]: f for f in conn.execute(
                "select distinct on (herramienta) id,herramienta,estado from trabajo where asignatura_id=%s "
                "and ambito_id=%s and tipo='generacion' and herramienta=any(%s) "
                "and estado in ('en_cola','en_espera','generando','verificando','revisando') order by herramienta,creado",
                (aid, ambito.id, herramientas)).fetchall()}
            nuevas = [h for h in herramientas if h not in activos]
            try:
                ids = crear_trabajos(conn, SolicitudGeneracion(aid, ambito, nuevas, cantidad=cantidad,
                                     instrucciones=instrucciones, perfil_dificultad=perfil)) if nuevas else []
            except (ValueError, KeyError):
                raise HTTPException(422, "Selección de generación no válida") from None
            creados = dict(zip(nuevas, ids))
            return {"trabajos": [{"id": str(activos[h]["id"]), "herramienta": h, "estado": activos[h]["estado"]}
                                 if h in activos else {"id": str(creados[h]), "herramienta": h, "estado": "en_cola"}
                                 for h in herramientas]}

    @staticmethod
    def _generar_sin_ia(conn, aid, asignatura, ambito, herramientas):
        """Al instante y en la transacción del pedido: trabajo ya `listo` + recurso, sin cola ni modelo."""
        if len(set(herramientas)) != len(herramientas) or any(
                HERRAMIENTAS_SIN_IA.get(h) != ambito.tipo for h in herramientas):
            raise HTTPException(422, "Selección de generación no válida")
        silabo = SilaboUTI.model_validate(asignatura["silabo"])
        try:
            contenidos = [generar_sin_ia(h, silabo, ambito.id) for h in herramientas]
        except ValueError:
            raise HTTPException(422, "El sílabo no tiene lo necesario para esta herramienta") from None
        parametros = {"silabo": asignatura["silabo"], "version_silabo": asignatura["version_silabo"]}
        evidencia = {"origen": "silabo", "sin_ia": True, "ambito": {"tipo": ambito.tipo, "id": ambito.id}}
        trabajos = []
        for herramienta, contenido in zip(herramientas, contenidos):
            tid = conn.execute(
                "insert into trabajo (asignatura_id,agente,ambito_tipo,ambito_id,herramienta,parametros,estado) "
                "values (%s,%s,%s,%s,%s,%s,'listo') returning id",
                (aid, asignatura["agente"], ambito.tipo, ambito.id, herramienta, Jsonb(parametros))).fetchone()["id"]
            rid = conn.execute(
                "insert into recurso (trabajo_id,asignatura_id,ambito_id,herramienta,version_silabo,contenido,"
                "evidencia,estado) values (%s,%s,%s,%s,%s,%s,%s,'listo') returning id",
                (tid, aid, ambito.id, herramienta, asignatura["version_silabo"], Jsonb(contenido),
                 Jsonb(evidencia))).fetchone()["id"]
            trabajos.append({"id": str(tid), "herramienta": herramienta, "estado": "listo", "recurso_id": str(rid)})
        return {"trabajos": trabajos}

    def exportar(self, aid, rid, correo, formato="html", version="estudiante"):
        """Exportación validada (spec §13). La versión del docente trae las respuestas: lector no accede."""
        docente = version == "docente"
        with self._acceso(aid, correo, editar=docente) as (conn, _):
            r = _recurso(conn, aid, rid)
            if r["validado_por"] is None:
                raise HTTPException(409, "Valida el recurso antes de descargarlo")
            contexto = _contexto(r, None)
            if formato not in ("html", "pdf", "docx"):
                raise HTTPException(422, "Formato no soportado")
            if docente and (formato == "html" or r["herramienta"] not in CON_RESPUESTAS):
                raise HTTPException(422, "Esta versión no está disponible")
            nombre = nombre_archivo(r["herramienta"], r["ambito_id"], contexto.asignatura, formato, docente)
        if formato == "html":
            return nombre, exportar_html(r, contexto)
        from app.exportar.documento import exportar_documento, FormulaInvalida
        try:
            return nombre, exportar_documento(r, contexto, formato, docente)
        except FormulaInvalida:
            raise HTTPException(422, "No se pudo representar una fórmula. Revisa su notación antes de exportar.") from None

    def validar(self, aid, rid, correo, revision):
        """El docente da por revisado el recurso (spec §13); exigido para exportar."""
        with self._acceso(aid, correo, editar=True) as (conn, a):
            r = _recurso(conn, aid, rid, editar=True)
            if r["revision"] != revision:
                raise HTTPException(409, "El recurso cambió; recárguelo antes de validar")
            conn.execute("update recurso set validado_por=%s,validado_en=clock_timestamp() "
                         "where id=%s and asignatura_id=%s", (correo, rid, aid))
            return _detalle(_recurso(conn, aid, rid), a)

    def trabajos(self, aid, correo, limite, desde, ids=None):
        with self._acceso(aid, correo) as (conn, _):
            return conn.execute(
                "select t.id,t.herramienta,t.ambito_tipo,t.ambito_id,t.estado,t.lotes_total,t.lotes_hechos,"
                "t.rondas_revision,t.tokens_entrada,t.tokens_salida,t.creado,t.actualizado,r.id recurso_id,"
                "r.estado recurso_estado,r.revision recurso_revision,"
                "case when t.estado='error' then 'No se pudo completar el trabajo' else null end error "
                "from trabajo t left join recurso r on r.trabajo_id=t.id and r.asignatura_id=t.asignatura_id "
                "where t.asignatura_id=%s and t.tipo='generacion' and (%s::uuid[] is null or t.id=any(%s)) order by case "
                "when t.estado in ('generando','verificando','revisando') then 0 "
                "when t.estado in ('en_cola','en_espera') then 1 else 2 end,t.creado desc,t.id limit %s offset %s",
                (aid, ids, ids, limite, desde)).fetchall()

    def listar(self, aid, correo, limite, desde):
        with self._acceso(aid, correo) as (conn, _):
            return conn.execute("select id,trabajo_id,ambito_id,herramienta,version_silabo,estado,revision,"
                                "creado,actualizado,validado_por is not null as validado from recurso where asignatura_id=%s "
                                "order by creado desc,id limit %s offset %s", (aid, limite, desde)).fetchall()

    def obtener(self, aid, rid, correo):
        with closing(self.conexion()) as conn:
            conn.autocommit = True
            with conn.transaction():
                conn.execute("set local lock_timeout to '2s'")
                a, rol = exigir_acceso(conn, aid, correo)
                detalle = _detalle(_recurso(conn, aid, rid), a)
                return _para_lector(detalle) if rol == "lector" else detalle

    def editar(self, aid, rid, correo, revision, contenido):
        with self._acceso(aid, correo, editar=True) as (conn, a):
            r = _recurso(conn, aid, rid, editar=True)
            if r["herramienta"] in HERRAMIENTAS_SIN_IA:
                # Reproducen el sílabo: se cambian subiendo una versión nueva del sílabo.
                raise HTTPException(422, "Esta herramienta reproduce el sílabo y no se edita")
            if r["revision"] != revision:
                raise HTTPException(409, "El recurso cambió; recárguelo antes de editar")
            try:
                canonico, verificaciones = validar_contenido(r["herramienta"], contenido, r["contenido"],
                                                            _contexto(r, a), aid)
            except EdicionInvalida:
                raise HTTPException(422, "El contenido editado no es válido") from None
            if canonico == r["contenido"]:
                # Guardar sin cambios no crea historia ni invalida la revisión original.
                return _detalle(r, a)
            nueva_revision = revision + 1
            conn.execute("insert into recurso_edicion (recurso_id,asignatura_id,usuario,revision,"
                         "contenido_anterior,contenido_nuevo,estado_anterior,verificaciones) "
                         "values (%s,%s,%s,%s,%s,%s,%s,%s)",
                         (rid, aid, correo, nueva_revision, Jsonb(r["contenido"]), Jsonb(canonico),
                          r["estado"], Jsonb(verificaciones)))
            # Una edición anula la validación: el docente debe volver a validar antes de exportar.
            conn.execute("update recurso set contenido=%s,revision=%s,estado='requiere_revision',"
                         "validado_por=null,validado_en=null,"
                         "verificacion_edicion=%s,actualizado=clock_timestamp() where id=%s and asignatura_id=%s",
                         (Jsonb(canonico), nueva_revision, Jsonb(verificaciones), rid, aid))
            return _detalle(_recurso(conn, aid, rid), a)
