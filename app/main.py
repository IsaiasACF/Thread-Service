"""Aplicación HTTP. Persona 2 inyectará adaptadores reales desde app/asgi.py."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.replies import router as replies_router
from app.ports import GatewayBadResponse, GatewayUnavailable
from app.services.thread_service import AuthorNotFound, RootMessageNotFound, ThreadService


def create_app(thread_service: ThreadService | None = None) -> FastAPI:
    application = FastAPI(
        title='Thread Service',
        description='Respuestas de un solo nivel a mensajes del chat. API v1.',
        version='1.0.0',
    )
    application.state.thread_service = thread_service
    application.include_router(replies_router)

    @application.get('/health', tags=['Health'])
    def health() -> dict[str, str]:
        return {'status': 'ok'}

    @application.exception_handler(RootMessageNotFound)
    def root_not_found(_request, _exc):
        return JSONResponse(status_code=404, content={'detail': 'Root message not found in channel'})

    @application.exception_handler(AuthorNotFound)
    def author_not_found(_request, _exc):
        return JSONResponse(status_code=422, content={'detail': 'Author does not exist'})

    @application.exception_handler(GatewayUnavailable)
    def unavailable(_request, _exc):
        return JSONResponse(status_code=503, content={'detail': 'Dependent service unavailable'})

    @application.exception_handler(GatewayBadResponse)
    def bad_response(_request, _exc):
        return JSONResponse(status_code=502, content={'detail': 'Dependent service failed'})

    return application


# Solo para documentación y comprobación de salud. La app operativa usa app.asgi:app.
app = create_app()
