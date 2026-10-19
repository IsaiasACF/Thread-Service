"""Endpoints versionados que solo delegan en el servicio de dominio."""
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from app.schemas.error import ErrorResponse, ValidationErrorResponse
from app.schemas.reply import ReplyCreate, ReplyRead
from app.services.thread_service import ThreadService

SUCCESS_EXAMPLE = {
    'id': '86af1f81-a897-42eb-8ca7-425c18354ddd',
    'channel_id': 'channel-1', 'message_id': 'message-1',
    'author_id': 'user-1', 'content': 'Estoy de acuerdo.',
    'created_at': '2026-10-17T16:00:00Z',
}


def error_response(description: str, **details: str) -> dict:
    return {
        'description': description,
        'model': ErrorResponse,
        'content': {'application/json': {'examples': {
            name: {'value': {'detail': detail}} for name, detail in details.items()
        }}},
    }


RESPONSES = {
    404: error_response('El mensaje raíz no existe en el canal.',
                        root_not_found='Root message not found in channel'),
    422: {
        'description': 'Entrada inválida; en POST, también autor inexistente.',
        'model': ErrorResponse | ValidationErrorResponse,
        'content': {'application/json': {'examples': {
            'author_not_found': {'value': {'detail': 'Author does not exist'}},
            'invalid_content': {'value': {'detail': [{
                'type': 'string_too_short', 'loc': ['body', 'content'],
                'msg': 'String should have at least 1 character', 'input': '',
                'ctx': {'min_length': 1},
            }]}},
        }}},
    },
    500: error_response('Falló una operación de persistencia.',
                        storage_failed='Storage operation failed'),
    502: error_response('Una dependencia externa entregó una respuesta inválida.',
                        bad_gateway='Dependent service failed'),
    503: error_response('Dependencia o almacenamiento inaccesible; o servicio sin configurar.',
                        gateway_unavailable='Dependent service unavailable',
                        storage_unavailable='Storage unavailable',
                        not_configured='Thread Service not configured'),
}

router = APIRouter(
    prefix='/api/v1/channels/{channel_id}/messages/{message_id}/replies',
    tags=['Replies'], responses=RESPONSES,
)


def get_thread_service(request: Request) -> ThreadService:
    service: ThreadService | None = getattr(request.app.state, 'thread_service', None)
    if service is None:
        raise HTTPException(status_code=503, detail='Thread Service not configured')
    return service


@router.post('', response_model=ReplyRead, status_code=status.HTTP_201_CREATED,
             summary='Crear una respuesta a un mensaje raíz',
             description='Valida mensaje y autor. Guarda respuesta y evento pendiente juntos. '
                         'No admite respuestas anidadas.',
             responses={201: {'content': {'application/json': {'example': SUCCESS_EXAMPLE}}}})
def create_reply(
    body: ReplyCreate,
    channel_id: str = Path(min_length=1, examples=['channel-1']),
    message_id: str = Path(min_length=1, examples=['message-1']),
    service: ThreadService = Depends(get_thread_service),
) -> ReplyRead:
    return service.create_reply(channel_id, message_id, body)


@router.get('', response_model=list[ReplyRead],
            summary='Consultar respuestas de un mensaje raíz',
            description='Valida el mensaje raíz y retorna respuestas por created_at e id. '
                        'Un thread sin respuestas retorna [].',
            responses={200: {'content': {'application/json': {'examples': {
                'thread': {'value': [SUCCESS_EXAMPLE]}, 'empty': {'value': []},
            }}}}})
def list_replies(
    channel_id: str = Path(min_length=1, examples=['channel-1']),
    message_id: str = Path(min_length=1, examples=['message-1']),
    service: ThreadService = Depends(get_thread_service),
) -> list[ReplyRead]:
    return service.list_replies(channel_id, message_id)
