"""Confirmed, persistent publication; unroutable events remain in the outbox."""
import pika

from app.config import Settings
from app.schemas.reply import ReplyCreatedEvent


class RabbitPublisher:
    def __init__(self, settings: Settings):
        self.settings = settings

    def publish(self, event: ReplyCreatedEvent, event_id: str) -> None:
        params = pika.URLParameters(str(self.settings.rabbitmq_url))
        params.connection_attempts = 1
        params.socket_timeout = 5
        params.stack_timeout = 10
        params.blocked_connection_timeout = 10
        params.heartbeat = 10
        # One connection per event avoids stale idle connections and cross-thread use.
        connection = pika.BlockingConnection(params)
        try:
            channel = connection.channel()
            # Omit durable: Pika defaults to False, matching base Messages.
            channel.exchange_declare(
                exchange=self.settings.rabbitmq_exchange, exchange_type='topic',
            )
            # Durable delivery queue also retains events before consumers connect.
            channel.queue_declare(queue=self.settings.rabbitmq_queue, durable=True)
            channel.queue_bind(queue=self.settings.rabbitmq_queue,
                               exchange=self.settings.rabbitmq_exchange,
                               routing_key=event.type)
            channel.confirm_delivery()
            channel.basic_publish(
                exchange=self.settings.rabbitmq_exchange, routing_key=event.type,
                body=event.model_dump_json().encode('utf-8'), mandatory=True,
                properties=pika.BasicProperties(
                    content_type='application/json', content_encoding='utf-8',
                    delivery_mode=2, message_id=event_id, type=event.type,
                    timestamp=int(event.occurred_at.timestamp()),
                ),
            )
        finally:
            if connection.is_open:
                connection.close()
