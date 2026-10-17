# Thread Service — Arquitectura de Software, Tarea 3

Microservicio de respuestas a mensajes raíz del chat base del curso. Los threads
son de un solo nivel y tienen persistencia propia: nunca se accede a la base de
datos de `users`, `channels` o `messages`.

**Estado:** núcleo API en desarrollo, integraciones REST/RabbitMQ y despliegue pendientes.
El arranque productivo `app.asgi:app` será agregado por la Persona 2.

## Contrato REST (v1)

| Método | Ruta | Resultado |
|---|---|---|
| POST | `/api/v1/channels/{channel_id}/messages/{message_id}/replies` | `201` + respuesta |
| GET | `/api/v1/channels/{channel_id}/messages/{message_id}/replies` | `200` + arreglo |
| GET | `/health` | `200` |

POST recibe `{ "author_id": "user-id", "content": "Texto de respuesta" }`.
El contenido admite de 1 a 4000 caracteres después de eliminar espacios laterales.

Códigos de error: `404` mensaje raíz no encontrado; `422` autor inexistente o
entrada inválida; `502` respuesta incorrecta de dependencia; `503` dependencia
no disponible. OpenAPI disponible en `/docs` y `/openapi.json`.

## Desarrollo de núcleo (Persona 1)

```bash
python -m venv .venv
# Activa .venv según el sistema operativo
pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload  # /docs y /health, pero endpoints 503 sin adaptadores
```

El servicio HTTP se ensambla con `create_app(ThreadService(repo, users, messages))`.
Las pruebas usan implementaciones falsas para trabajar sin bloquearse por integraciones.

## Outbox y eventos

Se guarda cada respuesta junto al evento pendiente en **un documento MongoDB**.
El worker que publicará eventos en RabbitMQ y Docker Compose quedan a cargo de
la Persona 2. Este diseño permite publicación *al menos una vez*, no exactamente
una vez; los consumidores deben deduplicar cuando sea necesario.

Evento: `chat.thread.reply.created`. Exchange: `chat`, tipo `topic`.
Consulta [docs/contracts.md](docs/contracts.md) para esquemas, interfaces y roles.

## Material del profesor

- [Unidad 3 y servicios base](https://github.com/rmasad/microservicios/tree/main/03_Comunicaci%C3%B3n/demo)
- [Unidad 4, implementación](https://github.com/rmasad/microservicios/tree/main/04_Implementaci%C3%B3n)
