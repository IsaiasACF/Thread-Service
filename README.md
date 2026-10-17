# Thread Service — Arquitectura de Software, Tarea 3

Microservicio de respuestas a mensajes raíz del chat base del curso. Los threads
son de un solo nivel y tienen persistencia propia: nunca se accede a la base de
datos de `users`, `channels` o `messages`.

**Estado:** núcleo REST, lógica, persistencia y outbox implementados y probados de forma independiente.
Integraciones REST/RabbitMQ y despliegue pendientes (Persona 2).
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
entrada inválida; `500` operación de persistencia fallida; `502` respuesta incorrecta de dependencia;
`503` dependencia o almacenamiento no disponible (también servicio sin configurar).
Los errores de negocio, gateways y almacenamiento conservan mensajes diferenciados
en `{ "detail": "..." }`; las validaciones de entrada usan `detail` como arreglo
de errores de FastAPI. No se devuelven mensajes internos del driver MongoDB. OpenAPI disponible en `/docs` y `/openapi.json`.

## Desarrollo de núcleo (Persona 1)

```bash
python -m venv .venv
# Activa .venv según el sistema operativo
pip install -r requirements-dev.txt
pytest -q -W error
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


## Verificación del núcleo

- Pydantic v2 se declara explícitamente. `httpx2` se usa solo para el TestClient
  actual de Starlette y evita su advertencia de deprecación; HTTPX sigue en las
  dependencias de desarrollo para versiones anteriores. Los clientes REST reales
  y sus dependencias productivas siguen a cargo de Persona 2.
- La API documenta esquemas y ejemplos de entrada, éxito y errores en `/docs`.
- El repositorio ordena por fechas decodificadas e ID: el orden textual ISO 8601
  puede fallar con fracciones de segundo opcionales. Ya se materializaba toda la
  lista; el ordenamiento se hace en memoria y no incorpora paginación.
- GitHub Actions levanta MongoDB 7 y ejecuta también las pruebas de concurrencia
  del repositorio, con advertencias de Python tratadas como errores.
- Sin `THREAD_TEST_MONGODB_URL`, las pruebas reales se omiten explícitamente.
  Para incluirlas contra una instancia de pruebas independiente:

  ```bash
  THREAD_TEST_MONGODB_URL=mongodb://127.0.0.1:27017 pytest -q -W error
  ```

  Se crean y eliminan colecciones con nombres únicos en `thread_core_tests`.
  No usar una base de producción ni credenciales reales en el repositorio.

Detalles del alcance, fallas de escritura ambiguas y validaciones pendientes:
[docs/core-validation.md](docs/core-validation.md).
