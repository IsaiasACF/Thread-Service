"""MongoDB: reply y outbox se guardan en una escritura de un documento.

No necesita un replica set para la atomicidad del insert. El worker utiliza
los métodos de OutboxRepository definidos en app/ports.py.
"""
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, ParamSpec, TypeVar
from uuid import uuid4

from pymongo import ASCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, PyMongoError

from app.errors import PersistenceError, PersistenceUnavailable
from app.schemas.reply import ClaimedEvent, ReplyCreatedEvent, ReplyRead


P = ParamSpec('P')
T = TypeVar('T')


def translate_mongo_errors(operation: Callable[P, T]) -> Callable[P, T]:
    """Incluye errores de cursores diferidos; no reintenta escrituras ambiguas."""
    @wraps(operation)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return operation(*args, **kwargs)
        except ConnectionFailure as exc:
            raise PersistenceUnavailable('Storage unavailable') from exc
        except PyMongoError as exc:
            raise PersistenceError('Storage operation failed') from exc
    return wrapped


class MongoReplyRepository:
    def __init__(self, collection: Collection):
        self.collection = collection

    @translate_mongo_errors
    def ensure_indexes(self) -> None:
        self.collection.create_index([('id', ASCENDING)], unique=True)
        self.collection.create_index([
            ('channel_id', ASCENDING), ('message_id', ASCENDING), ('created_at', ASCENDING)
        ])
        self.collection.create_index([('_outbox.published_at', ASCENDING), ('_outbox.lock_until', ASCENDING)])
        self.collection.create_index([('_outbox.id', ASCENDING)], unique=True)

    @translate_mongo_errors
    def save_with_outbox(self, reply: ReplyRead, event: ReplyCreatedEvent) -> None:
        document = reply.model_dump(mode='json')
        document['_outbox'] = {
            'id': str(uuid4()),
            'payload': event.model_dump(mode='json'),
            'published_at': None,
            'lock_until': None,
            'claim_token': None,
            'attempts': 0,
        }
        self.collection.insert_one(document)

    @translate_mongo_errors
    def list_for_message(self, channel_id: str, message_id: str) -> list[ReplyRead]:
        cursor = self.collection.find(
            {'channel_id': channel_id, 'message_id': message_id},
            {'_id': 0, '_outbox': 0},
        )
        # ISO 8601 con fracciones opcionales no ordena cronológicamente como texto:
        # "00.5Z" antecede a "00Z". Ya materializamos toda la lista (sin paginación);
        # comparamos fechas decodificadas para conservar también documentos previos.
        return sorted((ReplyRead.model_validate(doc) for doc in cursor),
                      key=lambda reply: (reply.created_at, reply.id))

    @translate_mongo_errors
    def claim_next_event(self, lease_seconds: int = 60) -> ClaimedEvent | None:
        if lease_seconds <= 0:
            raise ValueError('lease_seconds must be positive')
        now = datetime.now(timezone.utc)
        token = str(uuid4())
        doc = self.collection.find_one_and_update(
            {'_outbox.published_at': None,
             '$or': [{'_outbox.lock_until': None}, {'_outbox.lock_until': {'$lte': now}}]},
            {'$set': {'_outbox.lock_until': now + timedelta(seconds=lease_seconds),
                      '_outbox.claim_token': token},
             '$inc': {'_outbox.attempts': 1}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            return None
        outbox = doc['_outbox']
        return ClaimedEvent(event_id=outbox['id'], claim_token=token,
                            payload=ReplyCreatedEvent.model_validate(outbox['payload']),
                            attempts=outbox['attempts'])

    @translate_mongo_errors
    def mark_published(self, event_id: str, claim_token: str) -> bool:
        result = self.collection.update_one(
            {'_outbox.id': event_id, '_outbox.claim_token': claim_token,
             '_outbox.published_at': None},
            {'$set': {'_outbox.published_at': datetime.now(timezone.utc),
                      '_outbox.lock_until': None, '_outbox.claim_token': None}},
        )
        return result.modified_count == 1

    @translate_mongo_errors
    def release_claim(self, event_id: str, claim_token: str) -> bool:
        result = self.collection.update_one(
            {'_outbox.id': event_id, '_outbox.claim_token': claim_token,
             '_outbox.published_at': None},
            {'$set': {'_outbox.lock_until': None, '_outbox.claim_token': None}},
        )
        return result.modified_count == 1
