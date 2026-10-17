from fastapi.testclient import TestClient

from app.main import create_app
from app.ports import GatewayBadResponse, GatewayUnavailable
from app.services.thread_service import ThreadService

ROUTE = '/api/v1/channels/channel-1/messages/message-1/replies'


class FakeRepository:
    def __init__(self):
        self.rows = []
        self.events = []

    def save_with_outbox(self, reply, event):
        self.rows.append(reply)
        self.events.append(event)

    def list_for_message(self, channel_id, message_id):
        return [row for row in self.rows if row.channel_id == channel_id and row.message_id == message_id]


class FakeUsers:
    def __init__(self):
        self.is_found = True
        self.error = None

    def exists(self, user_id):
        if self.error:
            raise self.error
        return self.is_found


class FakeMessages:
    def __init__(self):
        self.is_found = True
        self.error = None

    def exists_in_channel(self, channel_id, message_id):
        if self.error:
            raise self.error
        return self.is_found


def setup_client():
    repo, users, messages = FakeRepository(), FakeUsers(), FakeMessages()
    service = ThreadService(repo, users, messages)
    return TestClient(create_app(service)), repo, users, messages


def test_create_reply_and_retrieve_it():
    client, repo, _, _ = setup_client()
    response = client.post(ROUTE, json={'author_id': ' user-1 ', 'content': ' Hola '})
    assert response.status_code == 201
    data = response.json()
    assert data['author_id'] == 'user-1'
    assert data['content'] == 'Hola'
    assert data['channel_id'] == 'channel-1'
    assert data['message_id'] == 'message-1'
    assert data['id']
    assert data['created_at'].endswith('Z')
    assert len(repo.events) == 1
    assert repo.events[0].type == 'chat.thread.reply.created'
    assert repo.events[0].subject_id == data['id']
    assert client.get(ROUTE).json() == [data]


def test_get_empty_thread():
    client, _, _, _ = setup_client()
    response = client.get(ROUTE)
    assert response.status_code == 200
    assert response.json() == []


def test_cannot_create_reply_for_missing_root():
    client, repo, _, messages = setup_client()
    messages.is_found = False
    response = client.post(ROUTE, json={'author_id': 'user-1', 'content': 'Hola'})
    assert response.status_code == 404
    assert repo.rows == []
    assert repo.events == []


def test_cannot_list_missing_root():
    client, _, _, messages = setup_client()
    messages.is_found = False
    assert client.get(ROUTE).status_code == 404


def test_author_must_exist():
    client, repo, users, _ = setup_client()
    users.is_found = False
    response = client.post(ROUTE, json={'author_id': 'unknown', 'content': 'Hola'})
    assert response.status_code == 422
    assert repo.rows == []


def test_rejects_empty_blank_and_oversized_messages():
    client, repo, _, _ = setup_client()
    for content in ['', '   ', 'X' * 4001]:
        r = client.post(ROUTE, json={'author_id': 'user-1', 'content': content})
        assert r.status_code == 422
    assert not repo.rows


def test_dependency_unavailable():
    client, _, _, messages = setup_client()
    messages.error = GatewayUnavailable()
    assert client.post(ROUTE, json={'author_id': 'user-1', 'content': 'Ok'}).status_code == 503


def test_dependency_bad_response():
    client, _, users, _ = setup_client()
    users.error = GatewayBadResponse()
    assert client.post(ROUTE, json={'author_id': 'user-1', 'content': 'Ok'}).status_code == 502


def test_app_without_injected_adapters_is_docs_only():
    client = TestClient(create_app())
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/docs').status_code == 200
    assert client.get(ROUTE).status_code == 503


def test_no_nested_reply_endpoint():
    client, _, _, _ = setup_client()
    r = client.post(ROUTE + '/nested-reply/replies', json={'author_id': 'user-1', 'content': 'Hola'})
    assert r.status_code == 404
