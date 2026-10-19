"""Run with python -m app.workers.outbox. SIGTERM stops between transactions."""
import logging
import signal
from threading import Event

from app.config import get_settings
from app.integrations.rabbitmq import RabbitPublisher
from app.ports import EventPublisher, OutboxRepository
from app.runtime import mongo_client, repository

logger = logging.getLogger(__name__)


def publish_next(repo: OutboxRepository, publisher: EventPublisher, lease_seconds: int) -> bool:
    claim = repo.claim_next_event(lease_seconds)
    if claim is None:
        return False
    try:
        publisher.publish(claim.payload, claim.event_id)
        if not repo.mark_published(claim.event_id, claim.claim_token):
            raise RuntimeError('Outbox claim was replaced before acknowledgement')
    except Exception:
        try:
            repo.release_claim(claim.event_id, claim.claim_token)
        except Exception:
            logger.warning('Could not release outbox claim; lease will expire')
        raise
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    stopped = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    failures = 0
    with mongo_client(settings) as mongo:
        repo = repository(mongo, settings)
        publisher = RabbitPublisher(settings)
        initialized = False
        while not stopped.is_set():
            try:
                if not initialized:
                    repo.ensure_indexes()
                    initialized = True
                published = publish_next(repo, publisher, settings.outbox_lease_seconds)
                failures = 0
                if not published:
                    stopped.wait(settings.outbox_poll_seconds)
            except Exception as exc:
                # Do not log connection strings or credentials embedded in driver errors.
                logger.warning('Outbox attempt failed (%s); retrying', type(exc).__name__)
                failures += 1
                stopped.wait(min(2 ** min(failures - 1, 10),
                                 settings.outbox_backoff_max_seconds))


if __name__ == '__main__':
    main()
