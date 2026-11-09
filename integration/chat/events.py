"""Observe real events using a private consumer queue and the existing chat contract."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import time

import pika

ROUTING_KEYS = ('chat.message.created', 'chat.thread.reply.created')


class EventObserver:
    def __init__(self, manifest: dict):
        credentials = json.loads((Path(manifest['state']) / 'runtime-credentials.json').read_text())
        params = pika.ConnectionParameters('127.0.0.1', manifest['ports']['rabbitmq'],
                  credentials=pika.PlainCredentials(credentials['username'], credentials['password']))
        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()
        # Same topic/non-durable exchange as both publishers, no broker/contract change.
        self.channel.exchange_declare(exchange='chat', exchange_type='topic', durable=False)
        self.queue = self.channel.queue_declare(queue='', exclusive=True, auto_delete=True).method.queue
        for key in ROUTING_KEYS:
            self.channel.queue_bind(queue=self.queue, exchange='chat', routing_key=key)
        self.events = []

    def drain(self):
        self.connection.process_data_events(time_limit=0)
        while True:
            method, properties, payload = self.channel.basic_get(self.queue, auto_ack=False)
            if method is None:
                return self.events
            event = json.loads(payload)
            assert event['type'] in ROUTING_KEYS and method.routing_key == event['type']
            self.events.append({'received_at': datetime.now(timezone.utc).isoformat(),
                                'routing_key': method.routing_key, 'event': event,
                                'message_id': properties.message_id})
            self.channel.basic_ack(method.delivery_tag)

    def wait_for(self, expected: dict[str, str], timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.drain()
            if all(any(item['event']['type'] == kind and item['event']['data']['id'] == identity
                       for item in self.events) for kind, identity in expected.items()):
                return self.events
            time.sleep(0.1)
        raise TimeoutError('Expected real message/reply events were not received')

    def close(self):
        if self.connection.is_open:
            self.connection.close()  # Only our exclusive observer queue disappears.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'output', 'ready', 'stop'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    assert json.loads((Path(manifest['state']) / 'owner.json').read_text())['owner'] == 'thread-service-chat-integration-v1'
    observer = EventObserver(manifest)
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    args.ready.write_text('real-amqp-observer-ready\n')
    try:
        while not stopping and not args.stop.exists():
            events = observer.drain()
            temporary = args.output.with_suffix('.tmp')
            temporary.write_text(json.dumps({'kind': 'real-amqp-no-mocks', 'events': events}, ensure_ascii=False, indent=2) + '\n')
            temporary.replace(args.output)
            time.sleep(0.1)
    finally:
        observer.close()


if __name__ == '__main__':
    main()
