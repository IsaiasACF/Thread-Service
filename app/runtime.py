"""MongoDB resource construction, independent of HTTP and AMQP."""
from pymongo import MongoClient

from app.config import Settings
from app.repositories.mongo_replies import MongoReplyRepository


def mongo_client(settings: Settings) -> MongoClient:
    return MongoClient(
        settings.mongodb_url, serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
        connectTimeoutMS=settings.mongodb_timeout_ms,
        socketTimeoutMS=settings.mongodb_timeout_ms, w='majority', retryWrites=False,
    )


def repository(client: MongoClient, settings: Settings) -> MongoReplyRepository:
    return MongoReplyRepository(client[settings.mongodb_database][settings.mongodb_collection])
