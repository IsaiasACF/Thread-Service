"""Contratos públicos de respuestas y del evento de dominio."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReplyCreate(BaseModel):
    author_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=4000)

    @field_validator('content', 'author_id', mode='before')
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReplyRead(ReplyCreate):
    model_config = ConfigDict(extra='forbid')

    id: str
    channel_id: str
    message_id: str
    created_at: datetime


class ReplyCreatedEvent(BaseModel):
    type: Literal['chat.thread.reply.created'] = 'chat.thread.reply.created'
    subject_id: str
    occurred_at: datetime
    data: ReplyRead


class ClaimedEvent(BaseModel):
    """Dato interno que el worker obtiene al reclamar un evento pendiente."""
    event_id: str
    claim_token: str
    payload: ReplyCreatedEvent
    attempts: int
