from pathlib import Path

from graphql import build_schema, get_introspection_query, print_schema, lexicographic_sort_schema
from gateway.app.graphql.schema import build_schema as build_gateway_schema


def test_lifespan_and_health_without_upstreams(client):
    assert client.get("/health").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    assert set(client.app.state.clients) == {
        "users", "channels", "messages", "threads", "integrals", "polls"}
    assert all(c.base_url is None for c in client.app.state.clients.values())


def test_graphql_health_exact_endpoint(client):
    response = client.post("/graphql", json={"query": "{ health }"})
    assert response.status_code == 200
    assert response.history == []
    assert response.json() == {"data": {"health": "ok"}}


def test_full_v1_contract_and_introspection(client):
    # Independent contract snapshot covers types, nullability, args and defaults.
    contract = build_schema(Path(__file__).with_name("contract_v1.graphql").read_text())
    assert print_schema(lexicographic_sort_schema(build_gateway_schema())) == print_schema(lexicographic_sort_schema(contract))
    response = client.post("/graphql", json={"query": get_introspection_query()})
    body = response.json()
    assert "errors" not in body
    types = {item["name"]: item for item in body["data"]["__schema"]["types"]}
    for root in ("Query", "Mutation"):
        assert {f["name"] for f in types[root]["fields"]} == set(contract.get_type(root).fields)


def test_cors(client):
    response = client.options("/graphql", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_graphql_validation_is_safe(client):
    body = client.post("/graphql", json={"query": "{ missing }"}).json()
    assert body["errors"][0]["extensions"] == {"code": "VALIDATION_ERROR"}


def test_health_and_schema_with_unreachable_configured_upstreams(monkeypatch):
    import httpx
    from fastapi.testclient import TestClient
    from gateway.app.config import Settings
    from gateway.app.main import create_app

    async def no_network(*_, **__):
        raise AssertionError("Startup and introspection must not access upstreams")
    monkeypatch.setattr(httpx.AsyncClient, "send", no_network)
    settings = Settings(_env_file=None, **{
        f"{service}_base_url": "http://unreachable.invalid:9"
        for service in ("users", "channels", "messages", "threads", "integrals", "polls")
    })
    with TestClient(create_app(settings)) as app_client:
        assert app_client.get("/health").status_code == 200
        response = app_client.post("/graphql", json={"query": get_introspection_query()})
        assert "errors" not in response.json()
        assert app_client.post("/graphql", json={"query": "{ health }"}).json()["data"]["health"] == "ok"
