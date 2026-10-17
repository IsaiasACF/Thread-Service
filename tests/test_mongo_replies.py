from datetime import datetime, timezone
from uuid import uuid4

import mongomock

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
