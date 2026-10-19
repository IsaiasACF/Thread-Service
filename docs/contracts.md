# Contratos de Thread Service — v1

## API pública

- POST `/api/v1/channels/{channel_id}/messages/{message_id}/replies`: `{ "author_id": "user-id", "content": "texto" }` → 201 con respuesta.
- GET de la misma ruta → 200 con arreglo ordenado por `created_at`, luego `id`.
- GET `/health` → `{ "status": "ok" }` (vida de la API, no disponibilidad de dependencias).

`ReplyRead`: `{id,channel_id,message_id,author_id,content,created_at}`. IDs string; fecha UTC ISO 8601. El contenido admite 1–4000 caracteres después de `strip()`. No se aceptan respuestas anidadas: el mensaje raíz siempre debe existir en Messages.

## Interfaces Python — app/ports.py

- `UserGateway.exists(user_id) -> bool`: consulta GET `/api/v1/users/{user_id}`. Solo 404 produce False; 200 exige un objeto JSON con el ID solicitado.
- `MessageGateway.exists_in_channel(channel_id, message_id) -> bool`: consulta GET `/api/v1/channels/{channel_id}/messages`. Exige un arreglo de objetos con `id` y `channel_id` string y busca coincidencia de ambos. Lista sin coincidencia o 404 produce False. No usa GET por ID de mensaje.
- Red/timeout → `GatewayUnavailable`; estados inesperados o respuestas incompatibles → `GatewayBadResponse`.
- `EventPublisher.publish(event, event_id) -> None`: retorna tras confirmación del broker; errores de conexión, publicación o enrutamiento se propagan al worker.

Las implementaciones REST usan HTTPX con timeouts y clientes reutilizados, propiedad del lifespan de la API. Las URLs se configuran por entorno. No hay llamadas directas a bases externas ni validación separada en Channels.

## MongoDB y outbox

Cada respuesta se guarda con `_outbox` en un único documento mediante `insert_one`. El outbox nunca aparece en REST. Contiene `id`, `payload`, `published_at`, `lock_until`, `claim_token`, `attempts`.

El ensamble crea índices y usa MongoClient con timeouts finitos, `w=majority` y `retryWrites=False`. No requiere replica set: la atomicidad es de un único documento.

Worker:

1. `claim_next_event(lease_seconds=60)` devuelve `ClaimedEvent` o None.
2. Publica el payload con `message_id=event_id` al exchange `chat`, tipo topic, routing key `chat.thread.reply.created`. Omite el argumento `durable`, usando el valor predeterminado `False` de Pika para coincidir con Messages.
3. Declara la cola durable configurable `thread.reply.created` y su binding. Publica JSON persistente con `mandatory=True` y publisher confirms.
4. Después de confirmación, llama `mark_published(event_id, claim_token)`.
5. Ante error libera el reclamo si puede y espera con backoff exponencial, hasta 30 segundos. Si muere, el lease permite otro reclamo.

El evento contiene `type`, `subject_id`, `occurred_at` y `data` (`ReplyRead`). El ID AMQP estable pertenece al outbox y no se agrega al contrato JSON. El GET no emite eventos. No existe un evento por intento rechazado.

Se garantiza registro conjunto de respuesta/evento; la publicación puede repetirse si el broker confirma y falla el reconocimiento en MongoDB. Los consumidores deduplican por `message_id`. No hay garantía de orden ni de exactamente una publicación. Un 201 no espera al worker. Las instancias deben usar relojes sincronizados; una publicación que exceda el lease puede duplicarse.

## Ejecución

- API: `app.asgi:app` con lifespan para MongoDB y clientes REST.
- Worker independiente: `python -m app.workers.outbox`.
- `app.main:app` permite inspeccionar documentación/salud; sin inyección devuelve 503 en las operaciones de respuestas.
- Docker Compose incluye API, worker, MongoDB y RabbitMQ. Los servicios base permanecen externos y se configuran por URL. No se incluye Kubernetes.

Variables, arranque y esquema de errores: [README.md](../README.md).
