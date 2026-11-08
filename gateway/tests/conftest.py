import pytest
from fastapi.testclient import TestClient
from gateway.app.config import Settings
from gateway.app.main import create_app


@pytest.fixture
def client(monkeypatch):
    import httpx
    async def no_network(*args, **kwargs):
        raise AssertionError("El scaffold no debe consultar servicios externos")
    monkeypatch.setattr(httpx.AsyncClient, "send", no_network)
    with TestClient(create_app(Settings(_env_file=None))) as client:
        yield client
