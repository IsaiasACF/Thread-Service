"""Endpoints versionados que solo delegan en el servicio de dominio."""
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from app.schemas.reply import ReplyCreate, ReplyRead
from app.services.thread_service import ThreadService

router = APIRouter(prefix='/api/v1/channels/{channel_id}/messages/{message_id}/replies', tags=['Replies'])


def get_thread_service(request: Request) -> ThreadService:
    service: ThreadService | None = getattr(request.app.state, 'thread_service', None)
    if service is None:
        raise HTTPException(status_code=503, detail='Thread Service not configured')
    return service


@router.post('', response_model=ReplyRead, status_code=status.HTTP_201_CREATED,
             summary='Crear una respuesta a un mensaje raíz')
def create_reply(
    body: ReplyCreate,
    channel_id: str = Path(min_length=1),
    message_id: str = Path(min_length=1),
    service: ThreadService = Depends(get_thread_service),
) -> ReplyRead:
    return service.create_reply(channel_id, message_id, body)


@router.get('', response_model=list[ReplyRead],
            summary='Consultar respuestas de un mensaje raíz')
def list_replies(
    channel_id: str = Path(min_length=1),
    message_id: str = Path(min_length=1),
    service: ThreadService = Depends(get_thread_service),
) -> list[ReplyRead]:
    return service.list_replies(channel_id, message_id)
