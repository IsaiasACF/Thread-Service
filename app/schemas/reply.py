"""Contratos públicos de respuestas y del evento de dominio."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReplyCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        'examples': [{'author_id': 'user-1', 'content': 'Estoy de acuerdo.'}],
    })

    author_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=4000)

    @field_validator('content', 'author_id', mode='before')
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReplyRead(ReplyCreate):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [{
        'id': '86af1f81-a897-42eb-8ca7-425c18354ddd',
        'channel_id': 'channel-1', 'message_id': 'message-1',
        'author_id': 'user-1', 'content': 'Estoy de acuerdo.',
        'created_at': '2026-10-17T16:00:00Z',
    }]})

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
