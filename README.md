# Thread Service

Microservicio FastAPI para crear y consultar respuestas de un solo nivel a un mensaje del chat. API v1, persistencia MongoDB propia y eventos RabbitMQ. No accede a las bases de datos de Users, Channels ni Messages.

## Ejecutar con Docker Compose

Requisitos: Docker Engine con Compose y el Compose base levantado, que crea la red compartida `microsvcs` y publica Users y Messages dentro de ella. Este repositorio incluye únicamente Threads y su infraestructura; no incluye ni levanta código de Users, Channels o Messages. No requiere Kubernetes ni Python local.

```sh
docker compose up --build -d
docker compose logs -f threads worker
docker compose down
```

API: `http://localhost:8004`; Swagger: `/docs`; ReDoc: `/redoc`; esquema OpenAPI: `/openapi.json`. RabbitMQ Management: `http://localhost:15672` (credenciales locales predeterminadas: `threads` / `threads`). MongoDB y AMQP solo se exponen dentro de la red Compose. Los volúmenes conservan datos al detener el sistema; `docker compose down -v` elimina esos datos.

Compose levanta `threads`, `worker`, `mongodb` y `rabbitmq`. API y worker usan la misma imagen y colección. La API puede seguir guardando respuestas si RabbitMQ está temporalmente caído: el worker publicará los eventos pendientes al recuperarse.

## Conexión con los servicios base

La configuración se define directamente en `docker-compose.yaml`: las variables compartidas están en `x-thread-env`, las credenciales del broker en `rabbitmq.environment` y el puerto público en `threads.ports`. No se necesita un archivo `.env`. La API se conecta a la red externa `microsvcs` creada por el Compose base y utiliza los nombres DNS `users` y `messages`, ambos con puerto interno `8000`. Los puertos publicados `8001` y `8003` sirven para acceder desde el host; la comunicación entre contenedores usa `8000`.

| Variable | Predeterminado | Uso |
|---|---|---|
| `THREAD_USERS_URL` | `http://users:8000` | Base HTTP de Users |
| `THREAD_MESSAGES_URL` | `http://messages:8000` | Base HTTP de Messages |
| `THREAD_HTTP_TIMEOUT_SECONDS` | `5` | Timeout HTTP de conexión/lectura/escritura/pool |
| `threads.ports` | `8004:8000` | Puerto publicado por Compose |
| `THREAD_RABBITMQ_URL` | `amqp://threads:threads@rabbitmq:5672/%2F` | Conexión AMQP del worker |
| `THREAD_RABBITMQ_EXCHANGE` | `chat` | Exchange topic no durable, compatible con Messages |
| `THREAD_RABBITMQ_QUEUE` | `thread.reply.created` | Cola durable enlazada al evento |

Al cambiar las credenciales locales de RabbitMQ en Compose, cambia también la URL AMQP en `x-thread-env` y `THREAD_TEST_RABBITMQ_URL` del servicio de pruebas (codifica caracteres especiales). Las credenciales del broker se inicializan al crear el volumen por primera vez.

Solo `threads` se conecta a `microsvcs`; también conserva la red propia para acceder a MongoDB. Worker, MongoDB y RabbitMQ permanecen en la red propia de Threads. Channels no se consulta directamente: la pertenencia del mensaje se valida en Messages. No hay `depends_on` entre proyectos Compose: levanta primero la base; si Users o Messages no responden, las operaciones afectadas devuelven `503`. La suite con perfil `test` usa la red propia y no necesita servicios base.

Contratos consumidos:

- Users: `GET /api/v1/users/{user_id}` → objeto JSON con `id` coincidente; `404` significa inexistente.
- Messages: `GET /api/v1/channels/{channel_id}/messages` → arreglo JSON de objetos con `id` y `channel_id` de tipo string. Debe existir una coincidencia de ambos IDs. `404` o un arreglo sin coincidencia significa mensaje raíz inexistente en el canal.

JSON inválido, cuerpos incompatibles y estados distintos de `200`/`404` se traducen a `502`; fallas de transporte o timeout a `503`. No se siguen redirecciones. Estos contratos deben coincidir con las implementaciones base conectadas.

## API REST v1

| Método | Ruta | Resultado |
|---|---|---|
| POST | `/api/v1/channels/{channel_id}/messages/{message_id}/replies` | `201` con respuesta creada |
| GET | `/api/v1/channels/{channel_id}/messages/{message_id}/replies` | `200` con arreglo ordenado por fecha e ID |
| GET | `/health` | `200`, comprobación de vida de la API |

POST recibe `{"author_id":"user-id","content":"Texto de respuesta"}`. El contenido admite 1–4000 caracteres y el autor 1–128, después de quitar espacios laterales. La respuesta contiene `id`, `channel_id`, `message_id`, `author_id`, `content` y `created_at` UTC. Un thread válido sin respuestas devuelve `[]`. No hay respuestas anidadas, edición ni eliminación en esta versión.

POST valida primero mensaje y luego autor; GET valida el mensaje raíz. Una validación fallida no genera escritura ni evento. Los esquemas y ejemplos están en OpenAPI.

| HTTP | Motivo |
|---|---|
| 404 | Mensaje inexistente o fuera del canal |
| 422 | Entrada inválida o autor inexistente |
| 500 | Operación de persistencia rechazada |
| 502 | Respuesta inválida de un servicio base |
| 503 | Servicio base o MongoDB no disponible |

Los errores usan `{"detail":"..."}`; la validación de FastAPI usa `detail` como arreglo de errores. No se exponen mensajes internos del driver. `/health` no prueba conectividad con dependencias. El arranque operativo es `app.asgi:app`; crea índices y cierra MongoDB y clientes HTTP al detenerse. `app.main:app` queda disponible solo para inspeccionar el núcleo sin adaptadores.

## Eventos y persistencia

Cada POST aceptado guarda respuesta y evento pendiente en un único documento MongoDB, con una escritura atómica. El GET no produce eventos de dominio. El worker reclama eventos mediante lease/token y publica:

```json
{
  "type": "chat.thread.reply.created",
  "subject_id": "reply-id",
  "occurred_at": "2026-10-18T12:00:00Z",
  "data": {
    "id": "reply-id", "channel_id": "channel-id", "message_id": "message-id",
    "author_id": "user-id", "content": "Texto", "created_at": "2026-10-18T12:00:00Z"
  }
}
```

Exchange `chat`, tipo `topic`, routing key `chat.thread.reply.created`. El publicador omite el argumento `durable` al declarar el exchange: Pika usa `False` por defecto, igual que el servicio base Messages. La cola sigue siendo durable; los mensajes son persistentes y se usan `mandatory` y publisher confirms. `message_id` de AMQP es el ID estable del outbox, distinto del ID del reply. Solo se marca publicado después de la confirmación del broker. Los consumidores pueden usar la cola incluida o enlazar sus propias colas al exchange.

Al reiniciar RabbitMQ se pierde la definición del exchange no durable y sus bindings. El publicador de Threads recrea el exchange y el binding de su cola antes de cada envío; los demás consumidores deben recuperar sus propios bindings. Esto no elimina por sí solo los mensajes persistentes ya almacenados en una cola durable. Si una instalación anterior ya creó `chat` con `durable=True`, cambiar el código no convierte ese exchange: hay que planificar su recreación como no durable y la recuperación de sus bindings, o usar un broker/virtual host nuevo. No elimines volúmenes para aplicar este cambio.

Ante fallas, se libera el reclamo cuando es posible y se reintenta con backoff exponencial de 1 a 30 segundos. Si el proceso muere, el lease de 60 segundos permite recuperar el evento. SIGTERM detiene el worker entre operaciones. Poll, lease y backoff se configuran con `THREAD_OUTBOX_POLL_SECONDS`, `THREAD_OUTBOX_LEASE_SECONDS` y `THREAD_OUTBOX_BACKOFF_MAX_SECONDS` en el entorno del worker; Compose usa los valores predeterminados.

La entrega es **al menos una vez** bajo recuperación de las dependencias: si se publica y el proceso cae antes de confirmar en MongoDB, puede repetirse el evento. Los consumidores deben deduplicar por `message_id`. No se garantiza orden de publicación. Un `201` confirma persistencia, no entrega inmediata al consumidor. No hay idempotencia HTTP: repetir un POST cuya escritura tuvo resultado ambiguo puede crear otra respuesta. No hay paginación en esta versión.

## Verificación

```sh
docker compose --profile test run --build --rm tests
```

Ejecuta pruebas del núcleo, clientes HTTP con transporte controlado, ensamble, worker, concurrencia MongoDB y entrega real RabbitMQ con recuperación tras publicar antes de confirmar el outbox. Usa colecciones, exchange y cola de prueba con nombres únicos. La URL AMQP de pruebas se define en el entorno del servicio `tests` dentro de Compose. No apuntes estas pruebas a infraestructura de producción.

GitHub Actions ejecuta las pruebas con Python 3.12, MongoDB 7 y RabbitMQ y valida el archivo Compose. Detalles del contrato: [docs/contracts.md](docs/contracts.md). Límites y cobertura: [docs/core-validation.md](docs/core-validation.md).
