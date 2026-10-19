"""Pruebas del repositorio con MongoDB real, sin worker ni adaptadores externos.

Se ejecutan solo con THREAD_TEST_MONGODB_URL. Si la URL está definida pero
MongoDB no responde, fallan: no se oculta una infraestructura de CI averiada.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from pymongo import MongoClient

from app.errors import PersistenceError
from app.repositories.mongo_replies import MongoReplyRepository
from test_mongo_replies import reply_obj, save


@pytest.fixture
def real_repository():
    uri = os.environ.get('THREAD_TEST_MONGODB_URL')
    if not uri:
        pytest.skip('Requiere THREAD_TEST_MONGODB_URL apuntando a MongoDB real')
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    collection = client.thread_core_tests['replies_' + uuid4().hex]
    try:
        client.admin.command('ping')
        repository = MongoReplyRepository(collection)
        repository.ensure_indexes()
        yield repository, collection
    finally:
        collection.drop()
        client.close()


def simultaneously(count, operation):
    barrier = Barrier(count)

    def run(index):
        barrier.wait(timeout=10)
        return operation(index)

    with ThreadPoolExecutor(max_workers=count) as executor:
        return list(executor.map(run, range(count)))


def test_real_mongo_single_event_has_one_active_claim(real_repository):
    repository, collection = real_repository
    save(repository, reply_obj())
    claims = simultaneously(16, lambda _: repository.claim_next_event(lease_seconds=120))
    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 1
    assert winners[0].attempts == 1
    assert collection.find_one()['_outbox']['attempts'] == 1
    assert repository.mark_published(winners[0].event_id, winners[0].claim_token)
    assert repository.claim_next_event() is None


def test_real_mongo_parallel_claims_do_not_share_events(real_repository):
    repository, collection = real_repository
    for _ in range(12):
        save(repository, reply_obj())
    claims = simultaneously(16, lambda _: repository.claim_next_event(lease_seconds=120))
    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 12
    assert len({claim.event_id for claim in winners}) == 12
    assert all(claim.attempts == 1 for claim in winners)
    assert collection.count_documents({'_outbox.attempts': 1}) == 12


def test_real_mongo_expiry_fences_stale_claims(real_repository):
    repository, collection = real_repository
    save(repository, reply_obj())
    first = repository.claim_next_event()
    # Simula el paso del tiempo en el dato BSON sin sleeps ni relojes de mock.
    collection.update_one({'_outbox.id': first.event_id}, {'$set': {
        '_outbox.lock_until': datetime.now(timezone.utc) - timedelta(seconds=1),
    }})
    second = repository.claim_next_event()
    assert first.event_id == second.event_id
    assert second.claim_token != first.claim_token
    assert second.attempts == 2
    assert not repository.mark_published(first.event_id, first.claim_token)
    assert not repository.release_claim(first.event_id, first.claim_token)
    assert repository.mark_published(second.event_id, second.claim_token)


def test_real_mongo_ack_and_release_only_one_can_succeed(real_repository):
    repository, _ = real_repository
    save(repository, reply_obj())
    claim = repository.claim_next_event()
    operations = [repository.mark_published, repository.release_claim]
    results = simultaneously(2, lambda index: operations[index](claim.event_id, claim.claim_token))
    assert sorted(results) == [False, True]


def test_real_mongo_duplicate_insert_keeps_original_reply_and_event(real_repository):
    repository, collection = real_repository
    reply = reply_obj()
    save(repository, reply)
    original = collection.find_one()
    with pytest.raises(PersistenceError):
        save(repository, reply)
    assert collection.count_documents({}) == 1
    assert collection.find_one() == original
