import asyncio

import httpx
import pytest
from graphql import GraphQLError

from gateway.app.clients.polls import PollsClient
from gateway.app.graphql.errors import GatewayError, format_error


def run_request(handler, url="http://polls:8000"):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await PollsClient(http, url).request_json("GET", "/api/v1/polls/p")
    return asyncio.run(run())


@pytest.mark.parametrize("status,code", [(400,"VALIDATION_ERROR"), (422,"VALIDATION_ERROR"),
    (404,"NOT_FOUND"), (403,"FORBIDDEN"), (409,"CONFLICT"), (410,"GONE"),
    (503,"UPSTREAM_UNAVAILABLE"), (504,"UPSTREAM_TIMEOUT"), (500,"BAD_UPSTREAM_RESPONSE"),
    (302,"BAD_UPSTREAM_RESPONSE")])
def test_http_errors_are_sanitized(status, code):
    with pytest.raises(GatewayError) as caught:
        run_request(lambda _: httpx.Response(status, text="private-upstream-body"))
    formatted = format_error(caught.value)
    assert formatted["extensions"] == {"code": code, "service": "polls", "httpStatus": status}
    assert "private-upstream-body" not in str(formatted)


@pytest.mark.parametrize("exc,code", [(httpx.ReadTimeout,"UPSTREAM_TIMEOUT"),
                                     (httpx.ConnectError,"UPSTREAM_UNAVAILABLE")])
def test_transport_errors(exc, code):
    def handler(request):
        raise exc("private-url-and-credentials", request=request)
    with pytest.raises(GatewayError) as caught:
        run_request(handler)
    assert caught.value.extensions["code"] == code
    assert "private" not in str(format_error(caught.value))


def test_invalid_json_and_unconfigured_service():
    for handler, url, code in [
        (lambda _: httpx.Response(200, text="not json"), "http://polls", "BAD_UPSTREAM_RESPONSE"),
        (lambda _: pytest.fail("Must not call upstream"), None, "UPSTREAM_UNAVAILABLE"),
    ]:
        with pytest.raises(GatewayError) as caught:
            run_request(handler, url)
        assert caught.value.extensions["code"] == code


def test_rest_preserves_snake_case():
    payload = {"poll_id": "p", "created_at": "2026-01-01T00:00:00Z"}
    assert run_request(lambda _: httpx.Response(200, json=payload)) == payload


def test_unknown_exceptions_do_not_leak_in_debug_mode():
    error = GraphQLError("private", original_error=RuntimeError("secret"),
                         extensions={"exception": "secret"})
    assert format_error(error, debug=True) == {
        "message": "Error interno del Gateway.", "extensions": {"code": "INTERNAL_ERROR"}}
