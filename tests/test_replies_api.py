import pytest
from fastapi.testclient import TestClient

from app.schemas.reply import ReplyRead
from app.schemas.error import ErrorResponse, ValidationErrorResponse

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


@pytest.mark.parametrize('field,value', [
    ('content', ''), ('content', ' \t\n '), ('content', 'x' * 4001),
    ('content', None), ('content', 12), ('content', []),
    ('author_id', ''), ('author_id', ' \t '), ('author_id', 'x' * 129),
    ('author_id', None), ('author_id', 12), ('author_id', {}),
])
def test_invalid_input_never_writes(field, value):
    client, repo, _, _ = setup_client()
    body = {'author_id': 'user-1', 'content': 'Hola', field: value}
    response = client.post(ROUTE, json=body)
    assert response.status_code == 422
    ValidationErrorResponse.model_validate(response.json())
    assert not repo.rows and not repo.events


@pytest.mark.parametrize('body', [{}, {'author_id': 'user-1'}, {'content': 'Hola'}])
def test_missing_fields(body):
    client, repo, _, _ = setup_client()
    assert client.post(ROUTE, json=body).status_code == 422
    assert not repo.rows and not repo.events


@pytest.mark.parametrize('length', [1, 4000])
def test_content_boundaries_apply_after_trimming(length):
    client, _, _, _ = setup_client()
    response = client.post(ROUTE, json={'author_id': ' ' + 'a' * 128 + ' ',
                                      'content': ' \t' + 'x' * length + '\n '})
    assert response.status_code == 201
    assert response.json()['content'] == 'x' * length
    assert response.json()['author_id'] == 'a' * 128


@pytest.mark.parametrize('gateway', ['users', 'messages'])
@pytest.mark.parametrize('error,status,detail', [
    (GatewayUnavailable, 503, 'Dependent service unavailable'),
    (GatewayBadResponse, 502, 'Dependent service failed'),
])
def test_gateway_error_contract(gateway, error, status, detail):
    client, repo, users, messages = setup_client()
    target = users if gateway == 'users' else messages
    target.error = error('private upstream response')
    response = client.post(ROUTE, json={'author_id': 'user-1', 'content': 'Hola'})
    assert response.status_code == status
    assert response.json() == {'detail': detail}
    assert not repo.rows and not repo.events
    if gateway == 'messages':
        response = client.get(ROUTE)
        assert response.status_code == status
        assert response.json() == {'detail': detail}


def test_business_error_bodies():
    client, repo, users, messages = setup_client()
    messages.is_found = False
    assert client.get(ROUTE).json() == {'detail': 'Root message not found in channel'}
    messages.is_found = True
    users.is_found = False
    assert client.post(ROUTE, json={'author_id': 'user-1', 'content': 'Hola'}).json() == {
        'detail': 'Author does not exist'}
    assert not repo.events


def test_openapi_documents_success_errors_schemas_and_examples():
    client, _, _, _ = setup_client()
    schema = client.get('/openapi.json').json()
    path = '/api/v1/channels/{channel_id}/messages/{message_id}/replies'
    for method, success in [('post', '201'), ('get', '200')]:
        operation = schema['paths'][path][method]
        assert set([success, '404', '422', '500', '502', '503']) <= operation['responses'].keys()
        for status in ['404', '422', '500', '502', '503']:
            content = operation['responses'][status]['content']['application/json']
            assert content['schema']
            for example in content['examples'].values():
                value = example['value']
                model = ValidationErrorResponse if isinstance(value['detail'], list) else ErrorResponse
                model.model_validate(value)
        content = operation['responses'][success]['content']['application/json']
        assert content['schema']
        if method == 'post':
            ReplyRead.model_validate(content['example'])
        else:
            for example in content['examples'].values():
                for row in example['value']:
                    ReplyRead.model_validate(row)
    request_schema = schema['components']['schemas']['ReplyCreate']
    assert set(request_schema['required']) == {'author_id', 'content'}
    assert request_schema['examples']
    # El 422 describe ambas formas existentes: negocio y validación.
    assert len(schema['paths'][path]['post']['responses']['422']['content']['application/json']['schema']['anyOf']) == 2
