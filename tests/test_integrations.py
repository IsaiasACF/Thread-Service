"""Adapter contracts and outbox failure recovery, without external services."""
from contextlib import contextmanager
from unittest.mock import Mock, patch

import httpx
import pytest

from app.config import Settings
from app.integrations.rabbitmq import RabbitPublisher
from app.integrations.rest import RestMessageGateway, RestUserGateway
from app.ports import GatewayBadResponse, GatewayUnavailable
from app.schemas.reply import ClaimedEvent, ReplyCreatedEvent
from app.workers.outbox import publish_next
from test_mongo_replies import reply_obj


@contextmanager
def gateway(status=200, payload=None, error=None):
    def handle(request):
        if error:
            raise error('private endpoint', request=request)
        return httpx.Response(status, json=payload)
    with httpx.Client(base_url='http://base/', transport=httpx.MockTransport(handle)) as client:
        yield RestUserGateway(client), RestMessageGateway(client)


def test_real_adapter_contracts_and_paths():
    paths = []
    def handle(request):
        paths.append(request.url.path)
        return httpx.Response(200, json=(
            {'id': 'user'} if '/users/' in request.url.path else
            [{'id': 'root', 'channel_id': 'channel'}]
        ))
    with httpx.Client(base_url='http://base', transport=httpx.MockTransport(handle)) as client:
        assert RestUserGateway(client).exists('user')
        messages = RestMessageGateway(client)
        assert messages.exists_in_channel('channel', 'root')
        assert not messages.exists_in_channel('other', 'root')
        assert not messages.exists_in_channel('channel', 'reply-id')
    assert paths[:2] == ['/api/v1/users/user', '/api/v1/channels/channel/messages']


def test_missing_references():
    with gateway(404) as (users, messages):
        assert not users.exists('user')
        assert not messages.exists_in_channel('channel', 'root')
    with gateway(payload=[]) as (_, messages):
        assert not messages.exists_in_channel('channel', 'root')


@pytest.mark.parametrize('status', [201, 204, 301, 400, 401, 429, 500, 503])
def test_unexpected_status_is_bad_gateway(status):
    with gateway(status) as (users, messages):
        with pytest.raises(GatewayBadResponse):
            users.exists('user')
        with pytest.raises(GatewayBadResponse):
            messages.exists_in_channel('channel', 'root')


@pytest.mark.parametrize('payload', [None, [], {}, {'id': 'other'}, {'id': 123}])
def test_invalid_user_body(payload):
    with gateway(payload=payload) as (users, _):
        with pytest.raises(GatewayBadResponse):
            users.exists('user')


@pytest.mark.parametrize('payload', [None, {}, ['root'], [{'id': 'root'}],
                                     [{'id': 'root', 'channel_id': 123}]])
def test_invalid_message_body(payload):
    with gateway(payload=payload) as (_, messages):
        with pytest.raises(GatewayBadResponse):
            messages.exists_in_channel('channel', 'root')


def test_invalid_json():
    with httpx.Client(base_url='http://base', transport=httpx.MockTransport(
        lambda _: httpx.Response(200, text='not json')
    )) as client:
        with pytest.raises(GatewayBadResponse):
            RestUserGateway(client).exists('user')


def test_invalid_compressed_body_is_bad_gateway():
    with httpx.Client(base_url='http://base', transport=httpx.MockTransport(
        lambda _: httpx.Response(200, content=b'invalid gzip',
                                 headers={'content-encoding': 'gzip'})
    )) as client:
        with pytest.raises(GatewayBadResponse):
            RestUserGateway(client).exists('user')


@pytest.mark.parametrize('error', [httpx.ConnectError, httpx.ReadTimeout])
def test_network_errors(error):
    with gateway(error=error) as (users, messages):
        with pytest.raises(GatewayUnavailable):
            users.exists('user')
        with pytest.raises(GatewayUnavailable):
            messages.exists_in_channel('channel', 'root')


def event():
    reply = reply_obj()
    return ReplyCreatedEvent(subject_id=reply.id, occurred_at=reply.created_at, data=reply)


def claimed_repo():
    repo = Mock()
    repo.claim_next_event.return_value = ClaimedEvent(
        event_id='stable-id', claim_token='token', payload=event(), attempts=1,
    )
    repo.mark_published.return_value = True
    return repo


def test_worker_marks_only_after_publication():
    repo, publisher = claimed_repo(), Mock()
    order = Mock()
    order.attach_mock(publisher, 'publisher')
    order.attach_mock(repo, 'repo')
    assert publish_next(repo, publisher, 60)
    assert [call[0] for call in order.mock_calls] == [
        'repo.claim_next_event', 'publisher.publish', 'repo.mark_published',
    ]
    publisher.publish.assert_called_once_with(repo.claim_next_event.return_value.payload, 'stable-id')
    repo.mark_published.assert_called_once_with('stable-id', 'token')


@pytest.mark.parametrize('failure', ['publish', 'ack', 'stale'])
def test_worker_failure_keeps_event_recoverable(failure):
    repo, publisher = claimed_repo(), Mock()
    if failure == 'publish':
        publisher.publish.side_effect = RuntimeError('broker offline')
    elif failure == 'ack':
        repo.mark_published.side_effect = RuntimeError('storage offline')
    else:
        repo.mark_published.return_value = False
    with pytest.raises(RuntimeError):
        publish_next(repo, publisher, 60)
    repo.release_claim.assert_called_once_with('stable-id', 'token')
    if failure == 'publish':
        repo.mark_published.assert_not_called()


def test_idle_worker_does_not_publish():
    repo, publisher = Mock(), Mock()
    repo.claim_next_event.return_value = None
    assert not publish_next(repo, publisher, 60)
    publisher.publish.assert_not_called()


def test_rabbit_publisher_confirms_persists_and_routes():
    connection = Mock()
    channel = connection.channel.return_value
    with patch('app.integrations.rabbitmq.pika.BlockingConnection', return_value=connection):
        payload = event()
        RabbitPublisher(Settings()).publish(payload, 'stable-id')
    channel.confirm_delivery.assert_called_once()
    channel.exchange_declare.assert_called_once_with(
        exchange='chat', exchange_type='topic',
    )
    channel.queue_declare.assert_called_once_with(queue='thread.reply.created', durable=True)
    kwargs = channel.basic_publish.call_args.kwargs
    assert kwargs['mandatory'] is True
    assert kwargs['routing_key'] == 'chat.thread.reply.created'
    assert kwargs['properties'].delivery_mode == 2
    assert kwargs['properties'].message_id == 'stable-id'
    assert ReplyCreatedEvent.model_validate_json(kwargs['body']) == payload
    assert [c[0] for c in channel.mock_calls].index('confirm_delivery') < [
        c[0] for c in channel.mock_calls].index('basic_publish')
    connection.close.assert_called_once()


def test_rabbit_failure_propagates_and_closes_connection():
    connection = Mock()
    connection.channel.return_value.basic_publish.side_effect = RuntimeError('nack')
    with patch('app.integrations.rabbitmq.pika.BlockingConnection', return_value=connection):
        with pytest.raises(RuntimeError):
            RabbitPublisher(Settings()).publish(event(), 'stable-id')
    connection.close.assert_called_once()
