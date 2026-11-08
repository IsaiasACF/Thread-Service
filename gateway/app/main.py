from contextlib import asynccontextmanager

import httpx
from ariadne.asgi import GraphQL
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .clients.registry import build_clients
from .config import Settings
from .graphql.errors import format_error
from .graphql.schema import build_schema


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
            app.state.clients = build_clients(http, settings)
            yield

    app = FastAPI(title="Gateway Tarea 6", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["POST", "GET"], allow_headers=["Content-Type"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    async def context(request, _data):
        return {"request": request, "clients": request.app.state.clients}

    graphql = GraphQL(build_schema(), debug=False, introspection=True,
                      error_formatter=format_error, context_value=context)

    @app.post("/graphql")
    async def execute_graphql(request: Request):
        return await graphql.handle_request(request)

    return app


app = create_app()
