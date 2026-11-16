"""Tarea 7: HTTP real y persistencia aislada mediante el lifespan existente."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from fastapi.testclient import TestClient
from test_replies_api import ROUTE

from app import asgi
from app.config import Settings
from app.main import create_app
from app.ports import MessageGateway, UserGateway
from app.schemas.reply import ReplyCreatedEvent, ReplyRead


@pytest.fixture(scope='function')
def isolated_service(monkeypatch):
    # Un cliente nuevo por prueba: incluso el mismo nombre de BD no comparte datos.
    mongo = mongomock.MongoClient()
    settings = Settings(
        mongodb_url='mongodb://unused.invalid:27017',
        mongodb_database='qa_service', mongodb_collection='replies',
        users_url='http://users.invalid', messages_url='http://messages.invalid',
    )
    users = Mock(spec=UserGateway)
    messages = Mock(spec=MessageGateway)
    users.exists.return_value = messages.exists_in_channel.return_value = True
    monkeypatch.setattr(asgi, 'get_settings', lambda: settings)
    monkeypatch.setattr(asgi, 'mongo_client', lambda _: mongo)
    monkeypatch.setattr(asgi, 'RestUserGateway', lambda _: users)
    monkeypatch.setattr(asgi, 'RestMessageGateway', lambda _: messages)
    # Fallar inmediatamente si una regresión intenta construir MongoDB real.
    monkeypatch.setattr('app.runtime.MongoClient', Mock(
        side_effect=AssertionError('Real MongoDB is forbidden in service tests'),
    ))
    application = create_app(lifespan=asgi.lifespan)
    collection = mongo[settings.mongodb_database][settings.mongodb_collection]
    try:
        with TestClient(application) as client:
            assert collection.count_documents({}) == 0
            yield SimpleNamespace(
                client=client, collection=collection, users=users, messages=messages,
                repository=application.state.thread_service.replies,
            )
        assert application.state.thread_service is None
    finally:
        # También se ejecuta si falla el test o el arranque. Outbox está embebido.
        try:
            mongo.drop_database(settings.mongodb_database)
        finally:
            mongo.close()


def test_post_persists_exactly_one_reply_and_matching_outbox(isolated_service):
    env = isolated_service
    response = env.client.post(ROUTE, json={'author_id': ' user-1 ', 'content': ' Hola '})
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {'id', 'channel_id', 'message_id', 'author_id', 'content', 'created_at'}
    assert data['id']
    assert data['created_at'].endswith('Z')
    assert {key: data[key] for key in ('channel_id', 'message_id', 'author_id', 'content')} == {
        'channel_id': 'channel-1', 'message_id': 'message-1',
        'author_id': 'user-1', 'content': 'Hola',
    }
    env.users.exists.assert_called_once_with('user-1')
    env.messages.exists_in_channel.assert_called_once_with('channel-1', 'message-1')
    assert env.collection.count_documents({}) == 1
    stored = env.collection.find_one()
    assert {key: stored[key] for key in data} == data
    outbox = stored['_outbox']
    assert outbox['id']
    assert outbox['payload'] == {
        'type': 'chat.thread.reply.created', 'subject_id': data['id'],
        'occurred_at': data['created_at'], 'data': data,
    }
    assert outbox['published_at'] is None
    assert outbox['attempts'] == 0
    listed = env.client.get(ROUTE)
    assert listed.status_code == 200
    assert listed.json() == [data]


@pytest.mark.parametrize('missing,status,detail', [
    ('root', 404, 'Root message not found in channel'),
    ('author', 422, 'Author does not exist'),
])
def test_reference_errors_leave_isolated_reply_and_outbox_empty(
    isolated_service, missing, status, detail,
):
    env = isolated_service
    if missing == 'root':
        env.messages.exists_in_channel.return_value = False
    else:
        env.users.exists.return_value = False
    response = env.client.post(ROUTE, json={'author_id': 'user-1', 'content': 'Hola'})
    assert response.status_code == status
    assert response.json() == {'detail': detail}
    assert env.collection.count_documents({}) == 0
    assert env.repository.claim_next_event() is None


def test_validation_error_leaves_isolated_reply_and_outbox_empty(isolated_service):
    env = isolated_service
    response = env.client.post(ROUTE, json={'author_id': 'user-1', 'content': 12})
    assert response.status_code == 422
    assert any(error['loc'] == ['body', 'content'] for error in response.json()['detail'])
    assert env.collection.count_documents({}) == 0
    assert env.repository.claim_next_event() is None
    env.users.exists.assert_not_called()
    env.messages.exists_in_channel.assert_not_called()


def test_new_fixture_starts_with_empty_thread_and_no_outbox(isolated_service):
    # Independiente del test que escribe: también pasa ejecutado solo o primero.
    env = isolated_service
    response = env.client.get(ROUTE)
    assert response.status_code == 200
    assert response.json() == []
    assert env.collection.count_documents({}) == 0
    assert env.repository.claim_next_event() is None
    env.messages.exists_in_channel.assert_called_once_with('channel-1', 'message-1')
    env.users.exists.assert_not_called()


def test_get_returns_chronological_data_and_only_requested_thread(isolated_service):
    env = isolated_service
    start = datetime(2026, 10, 17, tzinfo=UTC)
    expected = []
    # Inserción fuera de orden, empate y fracciones en el mismo segundo.
    for identifier, microseconds, channel, message in [
        ('c', 500000, 'channel-1', 'message-1'),
        ('b', 0, 'channel-1', 'message-1'),
        ('a', 0, 'channel-1', 'message-1'),
        ('other-channel', 0, 'channel-2', 'message-1'),
        ('other-message', 0, 'channel-1', 'message-2'),
    ]:
        reply = ReplyRead(
            id=identifier, channel_id=channel, message_id=message,
            author_id='user-1', content='Respuesta ' + identifier,
            created_at=start + timedelta(microseconds=microseconds),
        )
        env.repository.save_with_outbox(reply, ReplyCreatedEvent(
            subject_id=reply.id, occurred_at=reply.created_at, data=reply,
        ))
        if channel == 'channel-1' and message == 'message-1':
            expected.append(reply)
    response = env.client.get(ROUTE)
    assert response.status_code == 200
    assert response.json() == [
        reply.model_dump(mode='json')
        for reply in sorted(expected, key=lambda row: (row.created_at, row.id))
    ]
    assert [row['id'] for row in response.json()] == ['a', 'b', 'c']
    assert env.collection.count_documents({}) == 5


def test_health_is_liveness_without_storage_or_gateway_checks(isolated_service, monkeypatch):
    env = isolated_service
    for target, method in [
        (env.repository, 'list_for_message'), (env.repository, 'save_with_outbox'),
        (env.repository, 'claim_next_event'), (env.collection.database, 'command'),
        (env.users, 'exists'), (env.messages, 'exists_in_channel'),
    ]:
        monkeypatch.setattr(target, method, Mock(side_effect=AssertionError(
            'Liveness must not probe dependencies',
        )))
    response = env.client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    assert env.collection.count_documents({}) == 0


def test_health_rejects_post_with_method_not_allowed(isolated_service):
    response = isolated_service.client.post('/health')
    assert response.status_code == 405
    assert response.json() == {'detail': 'Method Not Allowed'}
    assert 'GET' in response.headers['allow']
    assert isolated_service.collection.count_documents({}) == 0
