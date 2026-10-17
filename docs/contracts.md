# Contratos internos compartidos — v1

**Congelados para el desarrollo paralelo** de Persona 1 (núcleo) y Persona 2 (integraciones).

## Entradas REST públicas

- `POST /api/v1/channels/{channel_id}/messages/{message_id}/replies`:
  `{ "author_id": "uuid-del-usuario", "content": "texto" }` → `201` con respuesta.
- `GET /api/v1/channels/{channel_id}/messages/{message_id}/replies` → `200` lista ordenada por `created_at`, luego `id`.
- `GET /health` → `{ "status": "ok" }`.

`ReplyRead`: `{id,channel_id,message_id,author_id,content,created_at}`. Los IDs son cadenas;
`created_at` usa fecha y hora UTC ISO 8601. Contenido: 1–4000 caracteres tras `strip()`.
No se aceptan respuestas anidadas: la API siempre refiere a un mensaje del servicio base.

## Interfaces Python — app/ports.py

- `UserGateway.exists(user_id) -> bool`: `False` únicamente en un HTTP 404 de Users.
- `MessageGateway.exists_in_channel(channel_id, message_id) -> bool`: obtiene
  `GET /api/v1/channels/{channel_id}/messages` y busca un objeto con `id == message_id`
  y `channel_id == channel_id`. El servicio base **NO** publica GET por ID de mensaje.
- En fallas de red o timeout: lanzar `GatewayUnavailable`.
- En 5xx, respuestas no válidas o estados inesperados: lanzar `GatewayBadResponse`.
- `EventPublisher.publish(event: ReplyCreatedEvent, event_id: str) -> None`:
  el worker pasa el ID del outbox como identificador estable del mensaje para deduplicación.

## MongoDB y outbox

Una respuesta se persiste junto con su `_outbox` en **un documento único** mediante
`insert_one`, que es atómico en MongoDB sin transacción multidocumento. El outbox
nunca aparece en las respuestas REST. Campos internos del outbox: `id`, `payload`,
`published_at`, `lock_until`, `claim_token`, `attempts`.

El worker de Persona 2 emplea la interfaz `OutboxRepository`:

1. `claim_next_event(lease_seconds=60)` retorna `ClaimedEvent` o `None`.
2. Publica `payload` al exchange RabbitMQ `chat`, tipo `topic`, routing key
   `chat.thread.reply.created`; recomienda propiedad `message_id=event_id`,
   publicación persistente y publisher confirms.
3. Tras confirmación del broker, `mark_published(event_id, claim_token)`.
4. Ante error, `release_claim(event_id, claim_token)` y reintento con backoff.

Se garantiza el registro conjunto del reply y evento pendiente, **no exactamente una
publicación**: existe la posibilidad de duplicados si el broker recibe el mensaje y
el proceso falla antes del `mark_published`. El consumidor debe ser idempotente.
El worker debe terminar la publicación antes del vencimiento del lease; si tarda,
puede recuperarse el mensaje por otra instancia y duplicarse.

## Ensamble sin pisarse los archivos

- Persona 1: `app/main.py`, `app/api`, `app/schemas`, `app/services`,
  `app/repositories`, `tests/unit` (en esta primera iteración, tests directamente en `tests/`).
- Persona 2: `app/integrations`, `app/workers`, `app/asgi.py`, `tests/integration`,
  `Dockerfile`, `docker-compose.yml`, `.env.example`, `k8s/`.
- Compartidos congelados: `app/ports.py` y `docs/contracts.md`.
- `app.asgi:app` será el punto de entrada productivo; el `app.main:app` actual
  solo permite ver `/docs` y `/health`, pues aún no incluye adaptadores reales.

## Dependencias externas del profesor

- Users: `GET /api/v1/users/{user_id}`
- Messages: `GET /api/v1/channels/{channel_id}/messages`
- El clúster proporciona los hostnames internos `users.servicios-base.svc.cluster.local:8000`
  y `messages.servicios-base.svc.cluster.local:8000`.

No incluir archivos `.kubeconfig`, variables secretas ni URLs con credenciales.
