from unittest.mock import Mock

import pytest

from app.errors import PersistenceError
from app.ports import MessageGateway, ReplyRepository, UserGateway
from app.schemas.reply import ReplyCreate
from app.services.thread_service import AuthorNotFound, RootMessageNotFound, ThreadService


def dependencies():
    repository = Mock(spec=ReplyRepository)
    users = Mock(spec=UserGateway)
    messages = Mock(spec=MessageGateway)
    users.exists.return_value = messages.exists_in_channel.return_value = True
    return ThreadService(repository, users, messages), repository, users, messages


def test_validates_references_before_persisting_matching_event():
    service, repository, users, messages = dependencies()
    order = Mock()
    order.attach_mock(messages, 'messages')
    order.attach_mock(users, 'users')
    order.attach_mock(repository, 'repository')
    reply = service.create_reply('channel', 'root', ReplyCreate(author_id=' author ', content=' Hi '))
    assert [call[0] for call in order.mock_calls] == [
        'messages.exists_in_channel', 'users.exists', 'repository.save_with_outbox',
    ]
    messages.exists_in_channel.assert_called_once_with('channel', 'root')
    users.exists.assert_called_once_with('author')
    stored_reply, event = repository.save_with_outbox.call_args.args
    assert stored_reply == reply == event.data
    assert event.subject_id == reply.id
    assert reply.created_at == event.occurred_at
    assert reply.created_at.utcoffset().total_seconds() == 0


@pytest.mark.parametrize('missing,exception', [('root', RootMessageNotFound), ('author', AuthorNotFound)])
def test_missing_references_do_not_persist(missing, exception):
    service, repository, users, messages = dependencies()
    if missing == 'root':
        messages.exists_in_channel.return_value = False
    else:
        users.exists.return_value = False
    with pytest.raises(exception):
        service.create_reply('channel', 'root', ReplyCreate(author_id='author', content='Hi'))
    repository.save_with_outbox.assert_not_called()
    if missing == 'root':
        users.exists.assert_not_called()


def test_service_propagates_storage_failure_without_retry():
    service, repository, _, _ = dependencies()
    repository.save_with_outbox.side_effect = PersistenceError('Storage operation failed')
    with pytest.raises(PersistenceError):
        service.create_reply('channel', 'root', ReplyCreate(author_id='author', content='Hi'))
    repository.save_with_outbox.assert_called_once()


def test_listing_checks_root_then_delegates_without_author_lookup():
    service, repository, users, messages = dependencies()
    repository.list_for_message.return_value = []
    assert service.list_replies('channel', 'root') == []
    messages.exists_in_channel.assert_called_once_with('channel', 'root')
    repository.list_for_message.assert_called_once_with('channel', 'root')
    users.exists.assert_not_called()
