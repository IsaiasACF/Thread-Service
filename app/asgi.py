"""Operational ASGI entry point; lifespan owns and closes all connections."""
from contextlib import ExitStack, asynccontextmanager

import httpx

from app.config import get_settings
from app.integrations.rest import RestMessageGateway, RestUserGateway
from app.main import create_app
from app.runtime import mongo_client, repository
from app.services.thread_service import ThreadService


@asynccontextmanager
async def lifespan(application):
    settings = get_settings()
    with ExitStack() as resources:
        mongo = resources.enter_context(mongo_client(settings))
        repo = repository(mongo, settings)
        repo.ensure_indexes()
        users = resources.enter_context(httpx.Client(
            base_url=str(settings.users_url), timeout=settings.http_timeout_seconds,
            trust_env=False,
        ))
        messages = resources.enter_context(httpx.Client(
            base_url=str(settings.messages_url), timeout=settings.http_timeout_seconds,
            trust_env=False,
        ))
        application.state.thread_service = ThreadService(
            repo, RestUserGateway(users), RestMessageGateway(messages),
        )
        try:
            yield
        finally:
            application.state.thread_service = None


app = create_app(lifespan=lifespan)
