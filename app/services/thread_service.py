"""Reglas de negocio. No importa HTTPX, PyMongo ni RabbitMQ."""
from datetime import datetime, timezone
from uuid import uuid4

from app.ports import MessageGateway, ReplyRepository, UserGateway
from app.schemas.reply import ReplyCreate, ReplyCreatedEvent, ReplyRead


class RootMessageNotFound(Exception):
    pass


class AuthorNotFound(Exception):
    pass


class ThreadService:
    def __init__(self, replies: ReplyRepository, users: UserGateway, messages: MessageGateway):
        self.replies = replies
        self.users = users
        self.messages = messages

    def create_reply(self, channel_id: str, message_id: str, body: ReplyCreate) -> ReplyRead:
        if not self.messages.exists_in_channel(channel_id, message_id):
            raise RootMessageNotFound('Root message not found in channel')
        if not self.users.exists(body.author_id):
            raise AuthorNotFound('Author does not exist')

        reply = ReplyRead(
            id=str(uuid4()),
            channel_id=channel_id,
            message_id=message_id,
            author_id=body.author_id,
            content=body.content,
            created_at=datetime.now(timezone.utc),
        )
        event = ReplyCreatedEvent(
            subject_id=reply.id,
            occurred_at=reply.created_at,
            data=reply,
        )
        # Un insert atómico: respuesta y evento pendiente en el MISMO documento MongoDB.
        self.replies.save_with_outbox(reply, event)
        return reply

    def list_replies(self, channel_id: str, message_id: str) -> list[ReplyRead]:
        if not self.messages.exists_in_channel(channel_id, message_id):
            raise RootMessageNotFound('Root message not found in channel')
        return self.replies.list_for_message(channel_id, message_id)
