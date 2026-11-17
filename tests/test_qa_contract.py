"""Users/Messages provider verification plus real Threads consumer adapters.

Set THREAD_QA_SOURCE to an immutable provider checkout. The QA launcher verifies
the source first and requires these tests. Ordinary offline suites may omit them.
"""
import hashlib
import json
import os
from pathlib import Path
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from app.integrations.rest import RestMessageGateway, RestUserGateway
from app.ports import GatewayBadResponse
from qa_contract_support import (
    assert_messages_contract, assert_user_contract, load_provider, provider_transport,
)


@pytest.fixture(scope='module')
def provider_source():
    configured = os.environ.get('THREAD_QA_SOURCE')
    if not configured:
        pytest.skip('Run integration/qa/run.py contract to verify pinned providers')
    source = Path(configured)
    lock = json.loads((Path(__file__).parents[1] / 'integration/chat/source.lock.json').read_text(encoding='utf-8'))
    for relative, expected in lock['sha256'].items():
        assert hashlib.sha256((source / relative).read_bytes()).hexdigest() == expected, relative
    return source


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Contract tests must not open network connections')
    monkeypatch.setattr(socket, 'create_connection', forbidden)


def test_users_published_route_and_consumer_agree(provider_source, monkeypatch):
    app, collection, mongo = load_provider(provider_source, 'users', monkeypatch)
    collection.find_one.side_effect = lambda query, projection: (
        {'id': 'andres', 'display_name': 'Andrés', 'future_field': True}
        if query == {'id': 'andres'} else None
    )
    requests = []
    with TestClient(app) as provider, httpx.Client(
        base_url='http://users.contract/', transport=provider_transport(provider, requests),
    ) as consumer:
        assert_user_contract(provider.get('/api/v1/users/andres'), 'andres')
        assert RestUserGateway(consumer).exists('andres')
        missing = provider.get('/api/v1/users/missing')
        assert missing.status_code == 404
        assert missing.json() == {'detail': 'User not found'}
        assert not RestUserGateway(consumer).exists('missing')
    assert requests == [('GET', '/api/v1/users/andres'), ('GET', '/api/v1/users/missing')]
    assert mongo.call_count == 1
    collection.insert_one.assert_not_called()


def test_messages_published_route_and_consumer_agree(provider_source, monkeypatch):
    app, collection, _ = load_provider(provider_source, 'messages', monkeypatch)
    records = [{'id': 'root', 'channel_id': 'study', 'content': '¿Repasamos?', 'future': 1}]
    collection.find.side_effect = lambda query, projection: [
        row for row in records if row['channel_id'] == query['channel_id']
    ]
    requests = []
    with TestClient(app) as provider, httpx.Client(
        base_url='http://messages.contract/', transport=provider_transport(provider, requests),
    ) as consumer:
        assert_messages_contract(provider.get('/api/v1/channels/study/messages'))
        gateway = RestMessageGateway(consumer)
        assert gateway.exists_in_channel('study', 'root')
        assert not gateway.exists_in_channel('other-channel', 'root')
        assert not gateway.exists_in_channel('study', 'reply-id')
        empty = provider.get('/api/v1/channels/unknown/messages')
        assert empty.status_code == 200 and empty.json() == []
    assert requests == [
        ('GET', '/api/v1/channels/study/messages'),
        ('GET', '/api/v1/channels/other-channel/messages'),
        ('GET', '/api/v1/channels/study/messages'),
    ]
    collection.insert_one.assert_not_called()


@pytest.mark.parametrize('payload', [{'id': 42}, {'display_name': 'Andrés'}])
def test_user_contract_detects_incompatible_response(payload):
    with httpx.Client(base_url='http://contract/', transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=payload),
    )) as client:
        with pytest.raises(AssertionError):
            assert_user_contract(client.get('/api/v1/users/andres'), 'andres')
        with pytest.raises(GatewayBadResponse):
            RestUserGateway(client).exists('andres')


@pytest.mark.parametrize('payload', [[{'id': 'root'}], [{'id': 42, 'channel_id': 'study'}]])
def test_message_contract_detects_incompatible_response(payload):
    with httpx.Client(base_url='http://contract/', transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=payload),
    )) as client:
        with pytest.raises(AssertionError):
            assert_messages_contract(client.get('/api/v1/channels/study/messages'))
        with pytest.raises(GatewayBadResponse):
            RestMessageGateway(client).exists_in_channel('study', 'root')
