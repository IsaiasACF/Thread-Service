"""Environment configuration shared by the API and outbox worker."""
from functools import lru_cache

from pydantic import AmqpDsn, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='THREAD_', extra='ignore')

    mongodb_url: str = 'mongodb://mongodb:27017'
    mongodb_database: str = 'threads'
    mongodb_collection: str = 'replies'
    mongodb_timeout_ms: int = Field(default=5000, gt=0)
    users_url: HttpUrl = HttpUrl('http://users:8000')
    messages_url: HttpUrl = HttpUrl('http://messages:8000')
    http_timeout_seconds: float = Field(default=5, gt=0)
    rabbitmq_url: AmqpDsn = AmqpDsn('amqp://threads:threads@rabbitmq:5672/%2F')
    rabbitmq_exchange: str = 'chat'
    rabbitmq_queue: str = 'thread.reply.created'
    outbox_poll_seconds: float = Field(default=1, gt=0)
    outbox_lease_seconds: int = Field(default=60, ge=30)
    outbox_backoff_max_seconds: float = Field(default=30, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
