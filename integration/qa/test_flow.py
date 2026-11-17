"""Real HTTP flow. Run inside the dedicated QA Compose network."""
from datetime import datetime
import json
import os
from pathlib import Path
import time
from uuid import uuid4

import httpx
import pytest


OUTPUT = Path(os.environ.get('QA_OUTPUT', '/evidence'))


@pytest.fixture
def api():
    with httpx.Client(timeout=10, trust_env=False) as client:
        yield client


def request(api, service, method, path, expected=200, **kwargs):
    response = api.request(method, f'http://qa-{service}:8000{path}', **kwargs)
    assert response.status_code == expected, (
        f'{service} {method} {path}: {response.status_code} {response.text[:400]}'
    )
    return response.json()


def write_report(name, report):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def test_create_read_and_reject_invalid_replies(api):
    andres = request(api, 'users', 'POST', '/api/v1/users', 201,
                     json={'display_name': 'Andrés'})
    isaias = request(api, 'users', 'POST', '/api/v1/users', 201,
                     json={'display_name': 'Isaías'})
    channel = request(api, 'channels', 'POST', '/api/v1/channels', 201,
                      json={'name': 'Grupo de estudio'})
    other = request(api, 'channels', 'POST', '/api/v1/channels', 201,
                    json={'name': 'Otro grupo'})
    messages_path = f'/api/v1/channels/{channel["id"]}/messages'
    root = request(api, 'messages', 'POST', messages_path, 201, json={
        'author_id': andres['id'], 'content': '¿Repasamos integrales mañana?',
    })
    for user in (andres, isaias):
        assert request(api, 'users', 'GET', f'/api/v1/users/{user["id"]}') == user
    assert request(api, 'messages', 'GET', messages_path) == [root]
    route = f'{messages_path}/{root["id"]}/replies'
    assert request(api, 'threads', 'GET', route) == []
    reply = request(api, 'threads', 'POST', route, 201, json={
        'author_id': isaias['id'], 'content': '¡Sí! Nos vemos después de clases.',
    })
    assert isinstance(reply['id'], str) and reply['id']
    assert reply['channel_id'] == channel['id']
    assert reply['message_id'] == root['id']
    assert reply['author_id'] == isaias['id']
    assert reply['content'] == '¡Sí! Nos vemos después de clases.'
    assert datetime.fromisoformat(reply['created_at'].replace('Z', '+00:00')).tzinfo
    assert set(reply) == {'id', 'channel_id', 'message_id', 'author_id', 'content', 'created_at'}
    assert request(api, 'threads', 'GET', route) == [reply]
    assert request(api, 'messages', 'GET', messages_path) == [root]

    unknown = str(uuid4())
    errors = [
        (route, {'author_id': unknown, 'content': 'Autor inexistente'}, 422),
        (f'{messages_path}/{unknown}/replies', {'author_id': isaias['id'], 'content': 'Raíz inexistente'}, 404),
        (f'/api/v1/channels/{other["id"]}/messages/{root["id"]}/replies',
         {'author_id': isaias['id'], 'content': 'Canal equivocado'}, 404),
    ]
    for path, body, status in errors:
        result = request(api, 'threads', 'POST', path, status, json=body)
        assert isinstance(result['detail'], str)
        assert request(api, 'threads', 'GET', route) == [reply]
    write_report('before-restart.json', {
        'passed': True, 'users': [andres, isaias], 'channel': channel,
        'root': root, 'reply': reply, 'route': route,
        'negativeStatuses': [422, 404, 404],
        'rootMessagesUnchanged': True,
    })


def test_read_same_reply_after_restart(api):
    before = json.loads((OUTPUT / 'before-restart.json').read_text(encoding='utf-8'))
    deadline = time.monotonic() + 60
    while True:
        try:
            health = api.get('http://qa-threads:8000/health')
            if health.status_code == 200:
                break
        except httpx.TransportError:
            pass
        assert time.monotonic() < deadline, 'Threads failed to recover within 60 seconds'
        time.sleep(0.5)
    replies = request(api, 'threads', 'GET', before['route'])
    assert replies == [before['reply']]
    write_report('after-restart.json', {'passed': True, 'replies': replies})
