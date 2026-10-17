from datetime import datetime, timedelta, timezone
from uuid import uuid4

import mongomock
import pytest
from pymongo.errors import DuplicateKeyError

from app.errors import PersistenceError

from app.repositories.mongo_replies import MongoReplyRepository
from app.schemas.reply import ReplyCreatedEvent, ReplyRead


def build():
    collection = mongomock.MongoClient().thread_service.replies
    repository = MongoReplyRepository(collection)
    repository.ensure_indexes()
    return repository, collection


def reply_obj(channel_id='channel-1', message_id='message-1'):
    return ReplyRead(
        id=str(uuid4()), channel_id=channel_id, message_id=message_id,
        author_id='user-1', content='Hola', created_at=datetime.now(timezone.utc),
    )


def save(repository, reply):
    repository.save_with_outbox(
        reply, ReplyCreatedEvent(subject_id=reply.id, occurred_at=reply.created_at, data=reply)
    )


def test_reply_and_event_are_one_document_and_private():
    repository, collection = build()
    reply = reply_obj()
    save(repository, reply)
    assert collection.count_documents({}) == 1
    stored = collection.find_one({'id': reply.id})
    assert stored['_outbox']['payload']['type'] == 'chat.thread.reply.created'
    response = repository.list_for_message('channel-1', 'message-1')
    assert len(response) == 1
    assert response[0].id == reply.id
    assert '_outbox' not in response[0].model_dump()


def test_worker_claim_acknowledge():
    repository, _ = build()
    reply = reply_obj()
    save(repository, reply)
    claim = repository.claim_next_event()
    assert claim is not None
    assert claim.payload.subject_id == reply.id
    assert claim.attempts == 1
    assert repository.claim_next_event() is None
    assert repository.mark_published(claim.event_id, 'bad-token') is False
    assert repository.mark_published(claim.event_id, claim.claim_token) is True
    assert repository.claim_next_event() is None


def test_worker_release_and_retry():
    repository, _ = build()
    save(repository, reply_obj())
    first = repository.claim_next_event()
    assert first is not None
    assert repository.release_claim(first.event_id, first.claim_token) is True
    second = repository.claim_next_event()
    assert second is not None
    assert second.event_id == first.event_id
    assert second.attempts == 2
    assert repository.mark_published(second.event_id, first.claim_token) is False


def test_chronological_order_with_id_tiebreaker_and_thread_isolation():
    repository, _ = build()
    now = datetime(2026, 10, 17, tzinfo=timezone.utc)
    for identifier, seconds, channel, message in [
        ('c', 2, 'channel-1', 'message-1'),
        ('b', 0, 'channel-1', 'message-1'),
        ('a', 0, 'channel-1', 'message-1'),
        ('other-message', -1, 'channel-1', 'message-2'),
        ('other-channel', -1, 'channel-2', 'message-1'),
    ]:
        reply = reply_obj(channel, message).model_copy(update={
            'id': identifier, 'created_at': now + timedelta(seconds=seconds),
        })
        save(repository, reply)
    assert [r.id for r in repository.list_for_message('channel-1', 'message-1')] == ['a', 'b', 'c']
    assert [r.id for r in repository.list_for_message('channel-1', 'message-2')] == ['other-message']
    assert [r.id for r in repository.list_for_message('channel-2', 'message-1')] == ['other-channel']
    assert repository.list_for_message('channel-2', 'message-2') == []


def test_duplicate_reply_does_not_insert_another_event():
    repository, collection = build()
    reply = reply_obj()
    save(repository, reply)
    with pytest.raises(PersistenceError) as caught:
        save(repository, reply)
    assert isinstance(caught.value.__cause__, DuplicateKeyError)
    assert collection.count_documents({}) == 1
    assert repository.claim_next_event().attempts == 1
    assert repository.claim_next_event() is None


def test_expired_lease_reclaimed_with_new_token(monkeypatch):
    repository, collection = build()
    save(repository, reply_obj())
    clock = datetime(2026, 10, 17, tzinfo=timezone.utc)

    class Clock:
        @classmethod
        def now(cls, tz):
            return clock

    monkeypatch.setattr('app.repositories.mongo_replies.datetime', Clock)
    first = repository.claim_next_event(lease_seconds=60)
    clock += timedelta(seconds=59)
    assert repository.claim_next_event() is None
    clock += timedelta(seconds=1)
    second = repository.claim_next_event()
    assert first.event_id == second.event_id
    assert first.claim_token != second.claim_token
    assert second.attempts == 2
    assert second.payload == first.payload
    assert not repository.mark_published(first.event_id, first.claim_token)
    assert not repository.release_claim(first.event_id, first.claim_token)
    assert repository.mark_published(second.event_id, second.claim_token)
    stored = collection.find_one()['_outbox']
    assert stored['published_at'] is not None
    assert stored['claim_token'] is None and stored['lock_until'] is None
    assert repository.claim_next_event() is None


def test_claim_release_and_acknowledgement_are_guarded():
    repository, collection = build()
    assert repository.claim_next_event() is None
    assert not repository.mark_published('missing', 'token')
    assert not repository.release_claim('missing', 'token')
    save(repository, reply_obj())
    claim = repository.claim_next_event()
    assert not repository.release_claim(claim.event_id, 'wrong-token')
    assert repository.claim_next_event() is None
    assert repository.release_claim(claim.event_id, claim.claim_token)
    assert not repository.release_claim(claim.event_id, claim.claim_token)
    assert not repository.mark_published(claim.event_id, claim.claim_token)
    stored = collection.find_one()['_outbox']
    assert stored['claim_token'] is None and stored['lock_until'] is None
    next_claim = repository.claim_next_event()
    assert next_claim.claim_token != claim.claim_token
    assert repository.mark_published(next_claim.event_id, next_claim.claim_token)
    assert not repository.mark_published(next_claim.event_id, next_claim.claim_token)
    assert not repository.release_claim(next_claim.event_id, next_claim.claim_token)


@pytest.mark.parametrize('lease', [0, -1])
def test_lease_must_be_positive(lease):
    repository, _ = build()
    with pytest.raises(ValueError, match='positive'):
        repository.claim_next_event(lease_seconds=lease)



def test_chronological_order_in_same_second_with_optional_fraction():
    repository, _ = build()
    now = datetime(2026, 10, 17, tzinfo=timezone.utc)
    for identifier, microseconds in [('later', 500000), ('earlier', 0)]:
        reply = reply_obj().model_copy(update={
            'id': identifier, 'created_at': now + timedelta(microseconds=microseconds),
        })
        save(repository, reply)
    assert [r.id for r in repository.list_for_message('channel-1', 'message-1')] == ['earlier', 'later']
