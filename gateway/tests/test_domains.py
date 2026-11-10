import pytest


@pytest.mark.parametrize("operation,service", [
    ('{ integrals { total } }', "integrals"),
    ('{ integral(id:"i") { id } }', "integrals"),
    ('{ poll(id:"123e4567-e89b-12d3-a456-426614174000") { pollId } }', "polls"),
    ('mutation { calculateIntegral(latex:"x") { id } }', "integrals"),
    ('mutation { createPoll(input:{channelId:"c",authorId:"u",question:"Q",options:["a","b"]},idempotencyKey:"k") { pollId } }', "polls"),
    ('mutation { votePoll(pollId:"123e4567-e89b-12d3-a456-426614174000",voterId:"u",optionId:"123e4567-e89b-12d3-a456-426614174001") { pollId } }', "polls"),
    ('mutation { closePoll(pollId:"123e4567-e89b-12d3-a456-426614174000",authorId:"u") { pollId } }', "polls"),
])
def test_unconfigured_operations_never_return_fake_success(client, operation, service):
    body = client.post("/graphql", json={"query": operation}).json()
    assert len(body["errors"]) == 1
    assert body["errors"][0]["extensions"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert body["errors"][0]["extensions"]["service"] == service
    assert not body.get("data") or all(value is None for value in body["data"].values())
