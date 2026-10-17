"""Contratos estables entre el núcleo (Persona 1) y las integraciones (Persona 2)."""
from typing import Protocol

from app.schemas.reply import ClaimedEvent, ReplyCreatedEvent, ReplyRead


class GatewayUnavailable(Exception):
    """Una dependencia externa no responde (p.ej. timeout o conexión)."""


class GatewayBadResponse(Exception):
    """Una dependencia externa devolvió una respuesta no utilizable."""


class UserGateway(Protocol):
    def exists(self, user_id: str) -> bool: ...


class MessageGateway(Protocol):
    def exists_in_channel(self, channel_id: str, message_id: str) -> bool: ...


class ReplyRepository(Protocol):
    def save_with_outbox(self, reply: ReplyRead, event: ReplyCreatedEvent) -> None: ...
    def list_for_message(self, channel_id: str, message_id: str) -> list[ReplyRead]: ...


class OutboxRepository(Protocol):
    def claim_next_event(self, lease_seconds: int = 60) -> ClaimedEvent | None: ...
    def mark_published(self, event_id: str, claim_token: str) -> bool: ...
    def release_claim(self, event_id: str, claim_token: str) -> bool: ...


class EventPublisher(Protocol):
    def publish(self, event: ReplyCreatedEvent, event_id: str) -> None: ...
