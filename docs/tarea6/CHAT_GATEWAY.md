# Tarea 6 — Gateway de Chat y Threads (Integrante A)

Este PR implementa las nueve operaciones de A sobre la base del PR #4, ya
fusionado en main (`d7cd0e93f5478e3b2f0bd549f6ff573a324314eb`).
No cambia el [contrato GraphQL v1](CONTRATO_COMPARTIDO.md), su snapshot ni el
frontend. Integrales y Polls conservan sus siete resolvers `NOT_IMPLEMENTED`.

## Contratos REST consultados

Fuente de Users, Channels y Messages: código del repositorio docente, commit
`d15f2e20ced1007099b90bf59b720e97be3d2d4a`:

- [Users](https://github.com/rmasad/microservicios/blob/d15f2e20ced1007099b90bf59b720e97be3d2d4a/03_Comunicaci%C3%B3n/demo/users/app/main.py).
- [Channels](https://github.com/rmasad/microservicios/blob/d15f2e20ced1007099b90bf59b720e97be3d2d4a/03_Comunicaci%C3%B3n/demo/channels/app/main.py).
- [Messages](https://github.com/rmasad/microservicios/blob/d15f2e20ced1007099b90bf59b720e97be3d2d4a/03_Comunicaci%C3%B3n/demo/messages/app/main.py).

Threads: `app/schemas/reply.py`, `app/api/replies.py`, `docs/contracts.md` de este
repositorio y su OpenAPI público consultado por GET el 2026-11-08. Las rutas,
campos, límites y códigos documentados coinciden con el código local.

| GraphQL | Servicio | Método y ruta REST |
|---|---|---|
| `user(id)` | Users | GET `/api/v1/users/{user_id}` |
| `createUser(displayName)` | Users | POST `/api/v1/users` |
| `channels` | Channels | GET `/api/v1/channels` |
| `channel(id)` | Channels | GET `/api/v1/channels/{channel_id}` |
| `createChannel(name)` | Channels | POST `/api/v1/channels` |
| `messages(channelId)` | Messages | GET `/api/v1/channels/{channel_id}/messages` |
| `sendMessage(channelId, authorId, content)` | Messages | POST a la misma ruta |
| `replies(channelId, messageId)` | Threads | GET `/api/v1/channels/{channel_id}/messages/{message_id}/replies` |
| `createReply(channelId, messageId, authorId, content)` | Threads | POST a la misma ruta |

Users devuelve objetos con `id` y `display_name`; Channels, `id` y `name`.
Los tres listados REST son arreglos JSON directos, **sin envelope** `items`.
Messages devuelve `id`, `channel_id`, `author_id`, `content`, `created_at`.
Replies agrega `message_id`. No se importan modelos del Thread Service en Gateway.

Las creaciones envían únicamente:

```json
{"display_name":"Usuario de prueba"}
{"name":"general"}
{"author_id":"usuario-ficticio","content":"Hola"}
```

El último cuerpo se usa tanto para mensajes como para respuestas, cada uno en
su endpoint. Los IDs de canal y mensaje raíz se envían en la ruta, no en el body.

## Implementación y decisiones

- Los cuatro clientes heredan de `RestClient` sin modificar el transporte,
  el ciclo de vida ni el registro automático compartidos.
- `gateway/app/clients/chat_contracts.py` contiene DTOs Pydantic de A y helpers
  de validación. No contiene clases RestClient adicionales registrables.
- Campos requeridos estrictos: no convierte números, booleanos o null en strings.
  Acepta campos extra para permitir ampliaciones compatibles del REST.
- Verifica coincidencia del ID consultado y del canal/mensaje raíz solicitado;
  las creaciones también comprueban el autor devuelto. Una lista con un DTO
  incorrecto falla completa; no se devuelven resultados parciales engañosos.
- Las fechas deben ser strings ISO 8601 con zona; se normalizan a UTC con `Z`.
- Los IDs son opacos, se codifican como segmentos de URL. No se asume UUID ni
  ObjectId, y no se permiten segmentos de puntos que cambien la ruta HTTP.
- Nombres de usuario/canal: 1–80 caracteres. Mensajes: contenido de 1–4000,
  sin recortar espacios, como Messages. La existencia del autor/canal la valida
  el servicio de dominio; el Gateway no duplica llamadas de validación.
- Replies replica el recorte de espacios de author_id y content de Thread
  Service; autor de 1–128 y contenido de 1–4000 después de recortar.
- Los resolvers son delegación async y mapeo explícito snake_case → camelCase
  en `graphql/chat/mapping.py` y `graphql/threads/mapping.py`.
- No hay retries automáticos, ni caché ni IDs/resultados generados por Gateway.
  Un timeout de POST puede dejar una creación aplicada aunque el cliente vea
  error: no reintentar automáticamente ni prometer idempotencia.

No se cambian tipos, argumentos, defaults ni nullabilidad de GraphQL. Un GET
individual con 404 produce `NOT_FOUND` y null en su campo nullable; no es un
éxito silencioso. Errores de campos non-null propagan null según GraphQL.

### Listados y errores

Un listado vacío válido devuelve `[]`. Nunca se transforma una falla HTTP,
un timeout o un DTO inválido en lista vacía.
**En el código docente, GET de mensajes no consulta Channels**: puede devolver
`[]` aun si ese canal no existe. El Gateway conserva esa semántica y no infiere
la existencia del canal a partir de la lista. Consultar `channel(id)` para
comprobarla. En cambio Threads valida el mensaje raíz: 404 no equivale a thread
vacío; un thread válido sin respuestas devuelve `[]`.

Se conserva el contrato común de errores:

| Situación | Código público |
|---|---|
| Entrada local inválida o upstream 400/422, incluido autor inexistente | `VALIDATION_ERROR` |
| Recurso inexistente (404) | `NOT_FOUND` |
| Upstream 403 / 409 / 410 | `FORBIDDEN` / `CONFLICT` / `GONE` |
| Timeout HTTP / upstream 504 | `UPSTREAM_TIMEOUT` |
| Conexión fallida, URL no configurada / upstream 503 | `UPSTREAM_UNAVAILABLE` |
| JSON, DTO o referencias incompatibles / otros estados, incluidos 500 y 502 | `BAD_UPSTREAM_RESPONSE` |
| Excepción inesperada del Gateway | `INTERNAL_ERROR` |

Un 500 de persistencia comunicado por Threads se publica como
`BAD_UPSTREAM_RESPONSE` con `service: threads` y `httpStatus: 500`, conforme al
mapeo común preexistente; no se analiza ni expone el detalle interno de almacenamiento.
Los mensajes públicos son genéricos. No se incluyen trazas ni cuerpos externos.

## Configuración y arranque

No requiere nuevas variables ni dependencias. Para operar cada dominio se
necesita su URL; si falta, solo esa operación devuelve `UPSTREAM_UNAVAILABLE`.
`/health` e introspección siempre pueden iniciar sin servicios externos.

| Variable | Ejemplo local seguro |
|---|---|
| `USERS_BASE_URL` | `http://localhost:8001` |
| `CHANNELS_BASE_URL` | `http://localhost:8002` |
| `MESSAGES_BASE_URL` | `http://localhost:8003` |
| `THREADS_BASE_URL` | `http://localhost:8004` |
| `HTTP_TIMEOUT_SECONDS` | `5` |
| `CORS_ORIGINS` | `["http://localhost:5173"]` |

No establecer URLs vacías: omitirlas si no están configuradas. Integrales y
Polls no son dependencias de Chat. En Compose usar los nombres DNS internos;
los ejemplos localhost son solo para ejecución en el host. No configurar URLs
ni credenciales de despliegue en código o commits.

Desde la raíz:

```sh
python3.12 -m venv /tmp/thread-gateway-venv
/tmp/thread-gateway-venv/bin/pip install -r gateway/requirements-dev.txt
cp gateway/.env.example gateway/.env
# Editar gateway/.env con las URLs de servicios LOCALES de prueba.
cd gateway
/tmp/thread-gateway-venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 5000 --reload
```

El Compose independiente sigue en `integration/compose.yaml` y conserva la red
externa `microsvcs`. Este PR no levanta los demás servicios por cuenta propia.

## Prueba manual de GraphQL

**Las siguientes mutaciones son para un stack local de prueba aislado. No
apuntarlas al clúster compartido ni a datos reales.** No fueron ejecutadas contra
los servicios del curso durante este PR. Los IDs siguientes son ficticios:
sustituirlos por IDs devueltos por las creaciones de ese stack local.

Enviar los documentos siguientes como JSON `{ "query": "...", "variables": {...} }`
a `POST http://localhost:5000/graphql`, con Content-Type application/json.
Por ejemplo, salud sin dependencias:

```sh
curl --fail -H 'Content-Type: application/json' \
  -d '{"query":"{ health }"}' http://localhost:5000/graphql
```

Crear identidad y canal en operaciones separadas; conservar sus IDs:

```graphql
mutation CreateUser($name: String!) {
  createUser(displayName: $name) { id displayName }
}
# variables: {"name":"Usuario de prueba"}

mutation CreateChannel($name: String!) {
  createChannel(name: $name) { id name }
}
# variables: {"name":"general"}
```

Consultar usuario y canales:

```graphql
query IdentityAndChannels($user: ID!, $channel: ID!) {
  user(id: $user) { id displayName }
  channels { id name }
  channel(id: $channel) { id name }
}
# variables: {"user":"usuario-ficticio","channel":"canal-ficticio"}
```

Publicar un mensaje y guardar su ID para la respuesta:

```graphql
mutation Send($channel: ID!, $author: ID!, $text: String!) {
  sendMessage(channelId: $channel, authorId: $author, content: $text) {
    id channelId authorId content createdAt
  }
}
# variables: {"channel":"canal-ficticio","author":"usuario-ficticio","text":"Hola"}

query Messages($channel: ID!) {
  messages(channelId: $channel) { id channelId authorId content createdAt }
}
# variables: {"channel":"canal-ficticio"}
```

Responder y consultar el thread (solo respuestas de un nivel):

```graphql
mutation Reply($channel: ID!, $message: ID!, $author: ID!, $text: String!) {
  createReply(channelId: $channel, messageId: $message, authorId: $author, content: $text) {
    id channelId messageId authorId content createdAt
  }
}
# variables: {"channel":"canal-ficticio","message":"mensaje-ficticio","author":"usuario-ficticio","text":"Una respuesta"}

query Replies($channel: ID!, $message: ID!) {
  replies(channelId: $channel, messageId: $message) {
    id channelId messageId authorId content createdAt
  }
}
# variables: {"channel":"canal-ficticio","message":"mensaje-ficticio"}
```

No existen mutaciones de edición, eliminación o respuesta anidada. Procesar
`errors` aunque el estado HTTP sea 200. Los mensajes de error no deben mostrarse
como operaciones exitosas. Usar `extensions.code` para presentación/reintentos
controlados; las mutaciones no deben reintentarse automáticamente.

## Pruebas reproducibles y resultados

```sh
# Desde raíz, con entorno Gateway:
/tmp/thread-gateway-venv/bin/python -m pytest -c gateway/pytest.ini gateway/tests -q -W error
# Entorno independiente para Thread Service, sin cambiar sus requisitos:
python3.12 -m venv /tmp/thread-original-venv
/tmp/thread-original-venv/bin/pip install -r requirements-dev.txt
/tmp/thread-original-venv/bin/python -m pytest -q -W error
/tmp/thread-original-venv/bin/python -m pytest scripts/test_k8s_rendering.py -q -W error
/tmp/thread-original-venv/bin/python scripts/validate_k8s.py
docker compose -f integration/compose.yaml config --quiet
git diff --check
```

Resultados locales (2026-11-08):

| Comprobación | Resultado |
|---|---|
| Gateway completo, incluidas nuevas pruebas | **263 passed, 0 failed, 0 skipped** |
| Thread Service original | **101 passed, 0 failed, 6 skipped** |
| Renderizado Kubernetes offline | **20 passed, 0 failed, 0 skipped** |
| Total local | **384 passed, 0 failed, 6 skipped** |
| Validador estático Kubernetes | Correcto, 10 recursos; sin conexión al clúster |
| Snapshot GraphQL y SDL | Intactos, comparación completa aprobada |

La prueba anterior de placeholders se limita ahora a las siete operaciones
pendientes de B. Sus nueve casos de A son sustituidos por pruebas de operaciones
reales con transporte controlado; no se modifica el snapshot ni se debilita la
validación del esquema. Se conservan las pruebas anteriores de salud,
introspección, errores y transporte común.

Los nuevos tests cubren cada método cliente y cada resolver, variables GraphQL,
rutas/bodies REST, errores 404/422/403/409/500/502/503, DTOs estrictos y referencias
incorrectas, fechas UTC, límites, listas vacías, IDs codificados, timeouts,
indisponibilidad, JSON inválido, ausencia de retries POST y sanitización.
El caso de creación seguido de lectura de reply comprueba que el Gateway usa
los valores de la API simulada; **no prueba durabilidad real de MongoDB**.

Las seis omisiones originales necesitan MongoDB/RabbitMQ de prueba y sus
variables opt-in. Docker no dispone de daemon local; no se levantó el stack.
No se declaran verificadas operaciones de dominio contra servicios reales.

## Verificación externa y límites

Se realizaron exclusivamente estas inspecciones reales de lectura:

- Services/Ingress de Kubernetes: Users, Channels y Messages en `servicios-base`,
  puerto 8000; API Threads en `grupo-threads`, puerto 8000.
- El proxy de Services del API server denegó el acceso con RBAC (Forbidden).
  No se verificó el OpenAPI desplegado de Users/Channels/Messages ni se intentó
  modificar permisos, iniciar Pods o consultar Secrets.
- `GET /health` público de Threads devolvió `{"status":"ok"}` y se leyó su
  OpenAPI público. Esto confirma salud/documentación, **no** una integración
  GraphQL→REST de dominio ni el funcionamiento de persistencia en esta prueba.

Chat se basa en el contrato del código docente citado. Falta comprobar en un
stack local aislado que las versiones reales de Users/Channels/Messages
conserven sus DTOs, serialización de creaciones y errores documentados. La
implementación valida y rechaza respuestas incompatibles sin simular éxito.
No hubo POST de dominio ni escrituras de prueba contra el clúster.

## Siguiente PR: frontend de A

Reemplazar placeholders solo en `features/identity`, `features/chat` y
`features/threads`. Reutilizar `lib/graphql.ts`, el QueryClientProvider y los
componentes comunes; no hacer llamadas REST desde el navegador.

- Identidad: createUser y user; guardar ID opaco de la sesión.
- Canales: channels, channel, createChannel.
- Chat: messages/sendMessage, claves Query como `['messages', channelId]`.
- Threads: replies/createReply, claves `['replies', channelId, messageId]`.
- Invalidar la consulta correspondiente después de una mutación exitosa,
  distinguir listas vacías de errores y mantener retries de POST deshabilitados.
- No modificar pantallas, rutas ni módulos de Integrales/Polls de Andrés.

Los registros automáticos siguen vigentes. No se editan ensamblador, transporte,
configuración o dependencias compartidos, frontend, código original de Thread
Service ni manifiestos Kubernetes. El contrato original y su informe de scaffold
se conservan como documentación histórica, sin reemplazarlos por este PR.
