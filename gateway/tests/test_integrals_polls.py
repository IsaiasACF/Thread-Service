import json
from copy import deepcopy

import httpx
import pytest

from test_chat_graphql import mock_gateway

POLL_ID = '123e4567-e89b-12d3-a456-426614174000'
OPTION_ID = '123e4567-e89b-12d3-a456-426614174001'
DATE = '2026-11-09T12:00:00Z'
INTEGRAL = {'id': 'i', 'latex': r'\int x dx', 'status': 'calculated',
    'result': {'latex': 'x^2/2', 'numeric': None, 'indefinite': True},
    'error': None, 'source': {'kind': 'rest'}, 'duration_ms': 10, 'created_at': DATE}
POLL = {'poll_id': POLL_ID, 'channel_id': 'c', 'author_id': 'u', 'question': 'Q',
    'options': [{'option_id': OPTION_ID, 'position': 0, 'text': 'A', 'vote_count': 0},
                {'option_id': '123e4567-e89b-12d3-a456-426614174002', 'position': 1,
                 'text': 'B', 'vote_count': 0}],
    'status': 'open', 'duration_minutes': 5, 'closes_at': DATE, 'created_at': DATE,
    'closed_at': None, 'total_votes': 0, 'creation_error': None}
VOTE = {'poll_id': POLL_ID, 'voter_id': 'u', 'option_id': OPTION_ID, 'cast_at': DATE}

CASES = [
    ('{ integrals(limit:2,offset:0) { total items { id durationMs createdAt source { kind channelId } } } }',
     'integrals', 'GET', '/api/v1/integrals', {'items': [INTEGRAL], 'total': 1, 'limit': 2, 'offset': 0}, None),
    ('{ integral(id:"i") { id result { indefinite numeric } } }', 'integral', 'GET', '/api/v1/integrals/i', INTEGRAL, None),
    ('mutation { calculateIntegral(latex:" x ") { id status } }', 'calculateIntegral', 'POST', '/api/v1/integrals', INTEGRAL, {'latex': 'x'}),
    (f'{{ poll(id:"{POLL_ID}") {{ pollId totalVotes options {{ optionId voteCount }} }} }}', 'poll', 'GET', f'/api/v1/polls/{POLL_ID}', POLL, None),
    ('mutation { createPoll(input:{channelId:"c",authorId:"u",question:"Q",options:["A","B"]},idempotencyKey:"stable-key") { pollId status } }',
     'createPoll', 'POST', '/api/v1/polls', POLL, {'channel_id': 'c', 'author_id': 'u', 'question': 'Q', 'options': ['A', 'B'], 'duration_minutes': 5}),
    (f'mutation {{ votePoll(pollId:"{POLL_ID}",voterId:"u",optionId:"{OPTION_ID}") {{ pollId voterId optionId castAt }} }}',
     'votePoll', 'POST', f'/api/v1/polls/{POLL_ID}/votes', VOTE, {'voter_id': 'u', 'option_id': OPTION_ID}),
    (f'mutation {{ closePoll(pollId:"{POLL_ID}",authorId:"u") {{ pollId closedAt }} }}', 'closePoll', 'POST', f'/api/v1/polls/{POLL_ID}/close', POLL, {'author_id': 'u'}),
]


@pytest.mark.parametrize('query,root,method,path,payload,body', CASES)
def test_seven_operations(query, root, method, path, payload, body):
    with mock_gateway(lambda _: httpx.Response(201 if method == 'POST' else 200, json=payload)) as (client, calls):
        response = client.post('/graphql', json={'query': query}).json()
        assert 'errors' not in response, response
        assert response['data'][root] is not None
        assert len(calls) == 1
        request = calls[0]
        assert request.method == method
        assert request.url.path == path
        assert (json.loads(request.content) if request.content else None) == body
        if root == 'createPoll':
            assert request.headers['Idempotency-Key'] == 'stable-key'
        if root == 'integrals':
            assert dict(request.url.params) == {'limit': '2', 'offset': '0'}
            assert response['data'][root]['items'][0]['durationMs'] == 10


@pytest.mark.parametrize('query,root,method,path,payload,body', CASES)
@pytest.mark.parametrize('status,code', [(403,'FORBIDDEN'),(404,'NOT_FOUND'),(409,'CONFLICT'),
    (410,'GONE'),(422,'VALIDATION_ERROR'),(503,'UPSTREAM_UNAVAILABLE')])
def test_errors_preserve_contract_without_retry(query, root, method, path, payload, body, status, code):
    with mock_gateway(lambda _: httpx.Response(status, json={'detail': 'private credentials'})) as (client, calls):
        result = client.post('/graphql', json={'query': query}).json()
        assert result['errors'][0]['extensions']['code'] == code
        assert result['errors'][0]['extensions']['httpStatus'] == status
        assert 'private' not in json.dumps(result)
        assert len(calls) == 1


def test_failed_integral_and_pending_poll_are_domain_data():
    failed = {**INTEGRAL, 'status': 'failed', 'result': None,
              'error': {'code': 'UNSOLVABLE', 'message': 'No se pudo resolver'}}
    with mock_gateway(lambda _: httpx.Response(201, json=failed)) as (client, _):
        result = client.post('/graphql', json={'query': 'mutation { calculateIntegral(latex:"x") { status error { code message } } }'}).json()
        assert result['data']['calculateIntegral']['status'] == 'failed'
    with mock_gateway(lambda _: httpx.Response(202, json={**POLL, 'status': 'pending_announcement'})) as (client, _):
        result = client.post('/graphql', json={'query': CASES[4][0]}).json()
        assert result['data']['createPoll']['status'] == 'pending_announcement'


@pytest.mark.parametrize('query', [
    '{ integrals(limit:101) { total } }', '{ integrals(offset:-1) { total } }',
    '{ integrals(status:"unknown") { total } }',
    'mutation { calculateIntegral(latex:"  ") { id } }',
    'mutation { createPoll(input:{channelId:"c",authorId:"u",question:"Q",options:["A"," a "]},idempotencyKey:"k") { pollId } }',
    'mutation { createPoll(input:{channelId:"c",authorId:"u",question:"Q",options:["A","B"],durationMinutes:0},idempotencyKey:"k") { pollId } }',
    'mutation { createPoll(input:{channelId:"c",authorId:"u",question:"Q",options:["A","B"]},idempotencyKey:"bad\\nheader") { pollId } }',
])
def test_invalid_input_never_calls_upstream(query):
    with mock_gateway(lambda _: pytest.fail('No HTTP request expected')) as (client, calls):
        result = client.post('/graphql', json={'query': query}).json()
        assert result['errors'][0]['extensions']['code'] == 'VALIDATION_ERROR'
        assert calls == []


def test_wrong_ids_and_malformed_responses_rejected():
    bad = deepcopy(POLL)
    bad['total_votes'] = 7
    for payload in (bad, {'poll_id': POLL_ID}, {**POLL, 'poll_id': 'invalid'}):
        with mock_gateway(lambda _: httpx.Response(200, json=payload)) as (client, _):
            result = client.post('/graphql', json={'query': CASES[3][0]}).json()
            assert result['errors'][0]['extensions']['code'] == 'BAD_UPSTREAM_RESPONSE'


@pytest.mark.parametrize('error,code', [(httpx.ReadTimeout, 'UPSTREAM_TIMEOUT'), (httpx.ConnectError, 'UPSTREAM_UNAVAILABLE')])
def test_transport_errors(error, code):
    def handler(request):
        raise error('private host', request=request)
    with mock_gateway(handler) as (client, calls):
        result = client.post('/graphql', json={'query': CASES[2][0]}).json()
        assert result['errors'][0]['extensions']['code'] == code
        assert len(calls) == 1
