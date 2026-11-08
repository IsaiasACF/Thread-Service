import pytest


@pytest.mark.parametrize("operation,service", [
    ('{ integrals { total } }', "integrals"),
    ('{ integral(id:"i") { id } }', "integrals"),
    ('{ poll(id:"p") { pollId } }', "polls"),
    ('mutation { calculateIntegral(latex:"x") { id } }', "integrals"),
    ('mutation { createPoll(input:{channelId:"c",authorId:"u",question:"Q",options:["a","b"]},idempotencyKey:"k") { pollId } }', "polls"),
    ('mutation { votePoll(pollId:"p",voterId:"u",optionId:"o") { pollId } }', "polls"),
    ('mutation { closePoll(pollId:"p",authorId:"u") { pollId } }', "polls"),
])
def test_pending_operations_never_return_fake_success(client, operation, service):
    body = client.post("/graphql", json={"query": operation}).json()
    assert len(body["errors"]) == 1
    assert body["errors"][0]["extensions"] == {"code": "NOT_IMPLEMENTED", "service": service}
    assert not body.get("data") or all(value is None for value in body["data"].values())
