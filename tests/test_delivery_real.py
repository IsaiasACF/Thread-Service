"""Opt-in MongoDB + RabbitMQ delivery tests, enabled by Compose's test service."""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pika
import pytest
from pymongo import MongoClient

from app.config import Settings
from app.integrations.rabbitmq import RabbitPublisher
from app.repositories.mongo_replies import MongoReplyRepository
from app.schemas.reply import ReplyCreatedEvent
from app.workers.outbox import publish_next
from test_mongo_replies import reply_obj


def test_real_confirmed_delivery_and_retry_after_publish_before_ack():
    mongo_url = os.environ.get('THREAD_TEST_MONGODB_URL')
    rabbit_url = os.environ.get('THREAD_TEST_RABBITMQ_URL')
    if not mongo_url or not rabbit_url:
        pytest.skip('Requires independent MongoDB and RabbitMQ test instances')
    suffix = uuid4().hex
    settings = Settings(rabbitmq_url=rabbit_url, rabbitmq_exchange='test.' + suffix,
                        rabbitmq_queue='test.' + suffix)
    mongo = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    connection = pika.BlockingConnection(pika.URLParameters(rabbit_url))
    collection = mongo.thread_core_tests['delivery_' + suffix]
    channel = connection.channel()
    try:
        # Base Messages may declare the shared exchange before Threads starts.
        channel.exchange_declare(exchange=settings.rabbitmq_exchange,
                                 exchange_type='topic', durable=False)
        repo = MongoReplyRepository(collection)
        repo.ensure_indexes()
        reply = reply_obj()
        payload = ReplyCreatedEvent(subject_id=reply.id, occurred_at=reply.created_at, data=reply)
        repo.save_with_outbox(reply, payload)
        publisher = RabbitPublisher(settings)
        claim = repo.claim_next_event()
        publisher.publish(claim.payload, claim.event_id)
        # Simulate crash after broker confirmation but before Mongo acknowledgement.
        collection.update_one({}, {'$set': {
            '_outbox.lock_until': datetime.now(timezone.utc) - timedelta(seconds=1),
        }})
        assert publish_next(repo, publisher, 60)
        assert not publish_next(repo, publisher, 60)
        for _ in range(2):
            method, properties, body = channel.basic_get(settings.rabbitmq_queue, auto_ack=True)
            assert method is not None
            assert properties.message_id == claim.event_id
            assert properties.delivery_mode == 2
            assert ReplyCreatedEvent.model_validate_json(body) == payload
        assert collection.find_one()['_outbox']['published_at'] is not None
    finally:
        channel.queue_delete(settings.rabbitmq_queue)
        channel.exchange_delete(settings.rabbitmq_exchange)
        connection.close()
        collection.drop()
        mongo.close()
