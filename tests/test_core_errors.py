from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import (
    AutoReconnect, ConnectionFailure, DuplicateKeyError, NetworkTimeout,
    OperationFailure, ServerSelectionTimeoutError,
)

from app.errors import PersistenceError, PersistenceUnavailable
from app.main import create_app
from app.repositories.mongo_replies import MongoReplyRepository
from app.schemas.reply import ReplyCreatedEvent
from app.services.thread_service import ThreadService
from test_mongo_replies import reply_obj
from test_replies_api import FakeMessages, FakeUsers, ROUTE


@pytest.mark.parametrize('driver_error,domain_error,status,detail', [
    (ConnectionFailure, PersistenceUnavailable, 503, 'Storage unavailable'),
    (AutoReconnect, PersistenceUnavailable, 503, 'Storage unavailable'),
    (ServerSelectionTimeoutError, PersistenceUnavailable, 503, 'Storage unavailable'),
    (NetworkTimeout, PersistenceUnavailable, 503, 'Storage unavailable'),
    (OperationFailure, PersistenceError, 500, 'Storage operation failed'),
    (DuplicateKeyError, PersistenceError, 500, 'Storage operation failed'),
])
@pytest.mark.parametrize('method', ['post', 'get'])
def test_driver_errors_return_safe_http_responses(driver_error, domain_error, status, detail, method):
    collection = Mock()
    secret = 'mongodb://admin:secret@private-db/internal'
    if method == 'post':
        collection.insert_one.side_effect = driver_error(secret)
    else:
        # Fallo durante la iteración del cursor, no solo al construir find().
        collection.find.return_value = MagicMock()
        collection.find.return_value.__iter__.side_effect = driver_error(secret)
    repository = MongoReplyRepository(collection)
    with TestClient(create_app(ThreadService(repository, FakeUsers(), FakeMessages()))) as client:
        response = (client.post(ROUTE, json={'author_id': 'user-1', 'content': 'Hola'})
                    if method == 'post' else client.get(ROUTE))
    assert response.status_code == status
    assert response.json() == {'detail': detail}
    assert 'secret' not in response.text
    if method == 'post':
        collection.insert_one.assert_called_once()  # Sin reintento de escritura ambiguo.


@pytest.mark.parametrize('method,driver_method', [
    ('ensure_indexes', 'create_index'),
    ('claim_next_event', 'find_one_and_update'),
    ('mark_published', 'update_one'),
    ('release_claim', 'update_one'),
])
@pytest.mark.parametrize('driver_error,domain_error', [
    (ConnectionFailure, PersistenceUnavailable), (OperationFailure, PersistenceError),
])
def test_repository_translates_errors_for_worker_and_indexes(method, driver_method, driver_error, domain_error):
    collection = Mock()
    getattr(collection, driver_method).side_effect = driver_error('internal')
    repository = MongoReplyRepository(collection)
    args = ('event-id', 'token') if method in ('mark_published', 'release_claim') else ()
    with pytest.raises(domain_error) as caught:
        getattr(repository, method)(*args)
    assert isinstance(caught.value.__cause__, driver_error)
    assert 'internal' not in str(caught.value)


def test_save_uses_exactly_one_insert_with_reply_and_matching_event():
    collection = Mock()
    repository = MongoReplyRepository(collection)
    reply = reply_obj()
    event = ReplyCreatedEvent(subject_id=reply.id, occurred_at=reply.created_at, data=reply)
    repository.save_with_outbox(reply, event)
    assert [call[0] for call in collection.mock_calls] == ['insert_one']
    document = collection.insert_one.call_args.args[0]
    assert document['id'] == reply.id
    assert document['_outbox']['payload']['data'] == reply.model_dump(mode='json')
    assert document['_outbox']['published_at'] is None
    assert document['_outbox']['attempts'] == 0
