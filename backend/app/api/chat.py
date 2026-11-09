from uuid import UUID

from fastapi import APIRouter, Query, Request, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.chat.servicio import ServicioChat
from app.recursos.servicio import _recurso

router = APIRouter(prefix='/asignaturas/{aid}')


class Pedido(BaseModel):
    model_config = ConfigDict(extra='forbid')
    peticion_id: UUID
    mensaje: str = Field(min_length=1, max_length=2000)
    recurso_id: UUID | None = None
    revision: StrictInt | None = Field(default=None, ge=0)

    @model_validator(mode='after')
    def seleccion(self):
        if (self.recurso_id is None) != (self.revision is None):
            raise ValueError('Recurso y revisión se envían juntos')
        return self


class Regeneracion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    peticion_id: UUID
    revision: StrictInt = Field(ge=0)
    motivo: str = Field(min_length=1, max_length=2000)


@router.post('/chat', status_code=202)
def enviar(aid: UUID, datos: Pedido, request: Request):
    return ServicioChat(request.app.state.recursos).enviar(aid, request.state.usuario, **datos.model_dump())


@router.get('/chat')
def historial(aid: UUID, request: Request, limite: int = Query(20, ge=1, le=50), antes: int | None = Query(None, ge=1, le=9223372036854775807)):
    return ServicioChat(request.app.state.recursos).listar(aid, request.state.usuario, limite, antes)


@router.get('/chat/{pedido}')
def estado(aid: UUID, pedido: UUID, request: Request):
    return ServicioChat(request.app.state.recursos).obtener(aid, request.state.usuario, pedido)


@router.post('/recursos/{rid}/items/{item}/regenerar', status_code=202)
def regenerar(aid: UUID, rid: UUID, item: str, datos: Regeneracion, request: Request):
    recursos = request.app.state.recursos
    with recursos._acceso(aid, request.state.usuario, editar=True) as (conn, _):
        r = _recurso(conn, aid, rid)
        if not isinstance(r['contenido'], list) or not any(i.get('item_id') == item for i in r['contenido']):
            raise HTTPException(404, 'Pregunta inexistente')
    accion = {'accion':'ajustar_recurso','mensaje_al_docente':'Ajuste de la pregunta solicitado.',
              'recurso_id':str(rid),'items':[item],'rutas':[],'instrucciones':datos.motivo}
    return ServicioChat(recursos).enviar(aid, request.state.usuario, datos.peticion_id, datos.motivo, rid, datos.revision, accion)
