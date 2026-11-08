# Tarea 6 — Contrato compartido v1

Base para Isaías (A) y Andrés (B). Esta rama entrega únicamente la plataforma:
las operaciones de dominio responden `NOT_IMPLEMENTED`. No hay datos simulados,
operaciones REST de dominio, bot, RabbitMQ nuevo ni despliegue Kubernetes.
Referencia: https://github.com/rmasad/microservicios/tree/main/06_Interfaz.
La entrega final del curso requerirá integración funcional y video en una fase posterior.

## Arquitectura y dependencias

Navegador → `/graphql` del mismo origen → Gateway FastAPI/Ariadne → clientes
REST httpx → Users, Channels, Messages, Threads, Integrales y Polls.
Solo el Gateway conocerá los contratos REST. Nunca acceder directamente a las
bases de datos de otros servicios. Thread Service existente sigue independiente.

- Gateway: Python 3.12, FastAPI, Ariadne, Pydantic Settings, httpx.AsyncClient.
  Versiones fijadas en `gateway/requirements.txt`; pytest en requirements-dev.
- Frontend: React 18, TypeScript 5, Vite 6, React Router 7, TanStack Query 5,
  graphql-request 7, CSS Modules. Usar Node 22 LTS y `npm ci` (lockfile versionado).
- Pruebas de interfaz: Vitest 4, Testing Library, jsdom; navegación real en router
  de memoria, sin llamar servicios externos.
- Compose independiente, red externa exacta `microsvcs`. No modifica el Compose
  original ni `app/`, `tests/`, `k8s/` o los requisitos de Thread Service.

## Estructura y responsables

| Ruta | Contenido / responsable |
|---|---|
| `gateway/app/main.py`, `config.py` | Ciclo de vida, HTTP, entorno; A coordina plataforma |
| `gateway/app/graphql/{registry,schema,errors}.py` | Registro, ensamblaje y errores compartidos |
| `gateway/app/graphql/base/` | Únicas raíces Query/Mutation y salud real |
| `gateway/app/graphql/chat/` | Users, Channels, Messages; A |
| `gateway/app/graphql/threads/` | Respuestas; A |
| `gateway/app/graphql/integrals/` | Calculadora e historial; B |
| `gateway/app/graphql/polls/` | Encuestas y votos; B |
| `gateway/app/clients/` | Un archivo por servicio, transporte común y registro automático |
| `gateway/tests/` | Pruebas nuevas independientes; agregar archivos por dominio |
| `frontend/src/app/` | Proveedor Query, router y layout comunes |
| `frontend/src/components/`, `styles/`, `lib/` | Componentes, tokens y cliente compartidos |
| `frontend/src/features/{identity,chat,threads}/` | Identidad, chat y respuestas; A |
| `frontend/src/features/{integrals,polls}/` | Pantallas y rutas; B |
| `integration/compose.yaml`, `overrides/` | Base compartida; B amplía integración local |
| `docs/tarea6/` | Contrato y validación compartidos |

A integra y despliega en PRs posteriores. B desarrolla Integrales/Polls y conecta
localmente sus servicios externos sin modificar sus repositorios. Coordinar
cambios de dependencias, contrato y archivos compartidos antes de integrarlos.

## GraphQL v1

`POST /graphql` es exacto, sin redirect ni slash final. Introspección habilitada.
`GET /health` devuelve `200 {"status":"ok"}`; `{ health }` devuelve `"ok"`.
El playground GET no forma parte de esta entrega. Salud indica vida del Gateway,
no disponibilidad de dependencias. Inicia aun sin URLs ni servicios externos.

Una sola raíz Query y Mutation en `base/schema.graphql`. La declaración
`type Mutation` sin campos se completa mediante `extend type Mutation` en los
dominios; el esquema final es válido y no agrega campos técnicos al contrato.

```graphql
type Query {
  health: String!
  user(id: ID!): User
  channels: [Channel!]!
  channel(id: ID!): Channel
  messages(channelId: ID!): [Message!]!
  replies(channelId: ID!, messageId: ID!): [Reply!]!
  integrals(limit: Int = 20, offset: Int = 0, status: String): IntegralPage!
  integral(id: ID!): Integral
  poll(id: ID!): Poll
}

type Mutation {
  createUser(displayName: String!): User!
  createChannel(name: String!): Channel!
  sendMessage(channelId: ID!, authorId: ID!, content: String!): Message!
  createReply(channelId: ID!, messageId: ID!, authorId: ID!, content: String!): Reply!
  calculateIntegral(latex: String!): Integral!
  createPoll(input: CreatePollInput!, idempotencyKey: String!): Poll!
  votePoll(pollId: ID!, voterId: ID!, optionId: ID!): Vote!
  closePoll(pollId: ID!, authorId: ID!): Poll!
}

type User {
  id: ID!
  displayName: String!
}

type Channel {
  id: ID!
  name: String!
}

type Message {
  id: ID!
  channelId: ID!
  authorId: ID!
  content: String!
  createdAt: String!
}

type Reply {
  id: ID!
  channelId: ID!
  messageId: ID!
  authorId: ID!
  content: String!
  createdAt: String!
}

type Integral {
  id: ID!
  latex: String!
  status: String!
  result: IntegralResult
  error: IntegralError
  source: IntegralSource!
  durationMs: Int!
  createdAt: String!
}

type IntegralResult {
  latex: String!
  numeric: Float
  indefinite: Boolean!
}

type IntegralError {
  code: String!
  message: String!
}

type IntegralSource {
  kind: String!
  channelId: ID
  authorId: ID
  messageId: ID
}

type IntegralPage {
  items: [Integral!]!
  total: Int!
  limit: Int!
  offset: Int!
}

type Poll {
  pollId: ID!
  channelId: ID!
  authorId: ID!
  question: String!
  options: [PollOption!]!
  status: String!
  durationMinutes: Int!
  closesAt: String!
  createdAt: String!
  closedAt: String
  totalVotes: Int!
  creationError: String
}

type PollOption {
  optionId: ID!
  position: Int!
  text: String!
  voteCount: Int!
}

type Vote {
  pollId: ID!
  voterId: ID!
  optionId: ID!
  castAt: String!
}

input CreatePollInput {
  channelId: ID!
  authorId: ID!
  question: String!
  options: [String!]!
  durationMinutes: Int = 5
}
```

Convenciones: GraphQL camelCase; DTOs REST conservan snake_case y se convierten
explícitamente al retornar desde un resolver. IDs opacos, no parsearlos ni
asumir ObjectId/UUID. Fechas de dominio: strings ISO 8601 UTC. No convertir
nullable a non-null ni cambiar argumentos/defaults sin acuerdo y nueva versión.
Un error en campo non-null propaga null según GraphQL; no reemplazarlo por `[]`.
El snapshot `gateway/tests/contract_v1.graphql` comprueba tipos, argumentos,
defaults y nullabilidad; nunca regenerarlo solo para hacer pasar una prueba.

## Registro modular sin conflictos

Cada carpeta `gateway/app/graphql/<dominio>/` contiene:

- `schema.graphql`: SDL de dominio, extendiendo las raíces.
- `resolvers.py`: bindables de Ariadne (ObjectType) propios.
- `module.py`: exporta `module = GraphQLModule(type_defs, bindables)`.

El registro descubre automáticamente `*/module.py`, ordenado por ruta. No hay
lista central que A y B deban modificar. Un módulo nuevo copia ese patrón y añade
pruebas propias. Los nombres GraphQL deben ser únicos. No importar `app` de
Thread Service; usar imports relativos al Gateway. No capturar fallas de carga
silenciosamente: un SDL incompatible debe fallar en las pruebas y el arranque.

### Ejemplo 1: consulta o mutación de Polls

`poll`, `createPoll`, `votePoll` y `closePoll` ya están declaradas. Para implementarlas,
reemplazar su placeholder, sin volver a declarar el campo. Una ampliación
**posterior, acordada** podría agregar en `polls/schema.graphql`:

```graphql
extend type Query { pollsByChannel(channelId: ID!): [Poll!]! }
```

No se incluye esa operación en v1. Actualizar contrato y sus pruebas solo si el
cambio fue acordado; mantener fechas/IDs/nullabilidad. Una mutación nueva sigue
el mismo patrón con `extend type Mutation` y `mutation.set_field`.

### Ejemplo 2: registrar un resolver sin modificar otros módulos

En `polls/resolvers.py`, quitar `poll` de la lista placeholder y registrar:

```python
@query.field("poll")
async def resolve_poll(_, info, id):
    client = info.context["clients"]["polls"]
    dto = await client.get_poll(id)  # método que B implementará
    return map_poll(dto)            # conversión explícita snake_case → camelCase
```

`query` y `mutation` ya se exportan en `bindables`; `module.py` no cambia.
Mantener placeholders solo para operaciones todavía pendientes. No registrar
el mismo campo dos veces: el último binding podría ocultar el anterior.
Los ejemplos son orientación para futuros PRs, no funciones ya implementadas.

### Ejemplo 3: cliente HTTP de Integrales

`IntegralsClient` ya se registra automáticamente como `clients["integrals"]`.
Agregar métodos únicamente en `gateway/app/clients/integrals.py`, por ejemplo,
**después de comprobar la ruta REST real**:

```python
from pydantic import BaseModel, ValidationError
from .base import RestClient

class IntegralDTO(BaseModel):
    id: str
    latex: str
    status: str

class IntegralsClient(RestClient):
    service = "integrals"

    async def get_integral(self, integral_id: str) -> IntegralDTO:
        from urllib.parse import quote
        dto = await self.request_json(
            "GET", f"/api/v1/integrals/{quote(integral_id, safe='')}")
        try:
            return IntegralDTO.model_validate(dto)
        except ValidationError:
            raise self.bad_response() from None
```

El DTO del ejemplo es parcial: completar con el contrato REST real. El transporte
comprueba HTTP y JSON; **cada cliente debe validar la estructura y semántica**.
No usar un AsyncClient por request; el lifespan comparte uno con timeout y cierre.
No hacer llamadas en importación, constructor o arranque. Usar MockTransport
para probar URLs, parámetros, errores y DTOs de cada cliente de manera aislada.

## Errores compartidos

Formato de un error público controlado:

```json
{"errors":[{"message":"Recurso no encontrado","extensions":{"code":"NOT_FOUND","service":"polls","httpStatus":404}}]}
```

`GatewayError(message, ErrorCode.NOT_FOUND, service="polls", http_status=404)`.
`service` y `httpStatus` son opcionales (no inventar estado HTTP en fallas de red).
`httpStatus` corresponde al upstream; el HTTP de la respuesta GraphQL no tiene
por qué coincidir. Errores de ejecución suelen devolver HTTP 200 con `errors`.
Las pantallas deben procesar `errors` aunque la respuesta HTTP sea exitosa.

| Código | Origen común |
|---|---|
| `VALIDATION_ERROR` | GraphQL inválido; REST 400/422 |
| `NOT_FOUND` | REST 404 |
| `FORBIDDEN` | REST 403 |
| `CONFLICT` | REST 409 |
| `GONE` | REST 410 |
| `UPSTREAM_TIMEOUT` | httpx timeout; REST 504 |
| `UPSTREAM_UNAVAILABLE` | Error de transporte, URL no configurada; REST 503 |
| `BAD_UPSTREAM_RESPONSE` | JSON/DTO inválido, redirecciones u otros estados REST |
| `INTERNAL_ERROR` | Excepción inesperada, mensaje público genérico |
| `NOT_IMPLEMENTED` | Solo scaffold; reemplazar al implementar cada campo |

El formateador no expone trazas, excepciones, cuerpos de upstream ni extensiones
arbitrarias, aun con debug=True. No interpolar URLs, credenciales o cuerpos
externos en GatewayError. No seguir redirects hacia endpoints desconocidos.

## Frontend: convenciones y ejemplos

Idioma español, tema claro, CSS Modules por componente y variables globales en
`styles/global.css`. Layout, navegación semántica, enlace para saltar al contenido,
foco visible, tokens, Button, LoadingIndicator, ErrorMessage y EmptyState son
compartidos. Evitar estilos globales de dominio y clientes GraphQL alternativos.

Rutas: `/`, `/channels/:channelId`, `/integrals`, `/integrals/:id`, `/polls/:pollId`.
Chat y encuestas de la navegación usan el ID literal `pendiente` solo para abrir
la pantalla placeholder, sin simular recursos existentes. A/B sustituirán esos
enlaces cuando existan canales y encuestas reales. Todas las pantallas indican
que la función está pendiente y no presentan formularios ni operaciones falsas.

### Ejemplo 4: pantalla React de Polls o Integrales

Crear `features/polls/PollResultsPage.tsx` con export default. En
`features/polls/routes.tsx` añadir su import y un RouteObject con la nueva ruta.
El router encuentra automáticamente `features/*/routes.tsx`; no editar App.tsx.
Las rutas existentes se implementan reemplazando su pantalla placeholder.
Para secciones nuevas en la navegación global, coordinar el cambio de layout.

```tsx
import { EmptyState } from '../../components/ui';
export default function PollResultsPage() {
  return <section><h1>Resultados</h1><EmptyState>Sin resultados disponibles.</EmptyState></section>;
}
```

### Ejemplo 5: GraphQL y TanStack Query

En un PR funcional de Polls, agregar un hook dentro de features/polls, usando
siempre `lib/graphql.ts` y el proveedor de `app/Providers.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';
import { graphqlClient, gql } from '../../lib/graphql';

interface PollSummary { pollId: string; question: string }
const query = gql`query Poll($id: ID!) { poll(id: $id) { pollId question } }`;
export function usePoll(id: string) {
  return useQuery({
    queryKey: ['polls', id],
    enabled: Boolean(id),
    queryFn: () => graphqlClient.request<{ poll: PollSummary | null }>(query, { id }),
  });
}
```

La pantalla consume isPending/isError/data con los componentes compartidos.
Distinguir null (recurso ausente) de error. Mutaciones futuras usan useMutation
e invalidan queryKey del dominio; no reintentar escrituras automáticamente.
No agregar estos hooks al scaffold activo hasta tener el resolver real.

## Variables de entorno

| Variable | Uso / valor por defecto |
|---|---|
| `USERS_BASE_URL` | URL REST opcional de Users |
| `CHANNELS_BASE_URL` | URL REST opcional de Channels |
| `MESSAGES_BASE_URL` | URL REST opcional de Messages |
| `THREADS_BASE_URL` | URL REST opcional de Threads |
| `INTEGRALS_BASE_URL` | URL REST opcional de Integrales |
| `POLLS_BASE_URL` | URL REST opcional de Polls |
| `HTTP_TIMEOUT_SECONDS` | Timeout HTTP positivo; 5 |
| `CORS_ORIGINS` | Arreglo JSON; `["http://localhost:5173"]` |
| `UVICORN_PORT` | Puerto al ejecutar uvicorn sin --port; ejemplo 5000 |
| `GATEWAY_PROXY_TARGET` | Solo servidor Vite; http://localhost:5000 en local |

Omitir URLs cuando no estén configuradas (no asignar strings vacíos: Pydantic
valida AnyHttpUrl). Los `.env.example` contienen ejemplos de desarrollo sin
credenciales; no asumir puertos reales de Integrales/Polls. Compose proporciona
URLs internas por entorno, reemplazables mediante variables del shell o
`--env-file`. En Kubernetes serán otras URLs; no se implementa ese despliegue.
No usar variables VITE_* para datos privados: quedan incorporadas al bundle.
El cliente de navegador construye la URL absoluta de `/graphql` desde window.location.origin (requerido por graphql-request), sin URLs de microservicios.

## Arranque local

Desde la raíz del repositorio:

```sh
python3.12 -m venv /tmp/thread-gateway-venv
/tmp/thread-gateway-venv/bin/pip install -r gateway/requirements-dev.txt
cp gateway/.env.example gateway/.env
cd gateway
/tmp/thread-gateway-venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 5000
```

Este `app` se resuelve dentro de gateway/; desde la raíz usar
`uvicorn gateway.app.main:app --port 5000`. Pydantic carga `.env` del directorio
actual. En otra terminal desde raíz:

```sh
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Abrir http://localhost:5173. Vite conserva `/graphql` y reenvía al Gateway.
La imagen frontend ejecuta Vite para **desarrollo local**, sin bind mounts; tras
cambiar código reconstruir. Para publicar dist/ será necesario configurar
fallback SPA a index.html y reverse proxy de `/graphql` en el hosting final.
`vite preview` no incluye el proxy de desarrollo y no es la integración Compose.

## Docker Compose independiente

```sh
# Si todavía no existe la red compartida (se hace una sola vez):
docker network create microsvcs
docker compose -f integration/compose.yaml config --quiet
docker compose -f integration/compose.yaml up --build -d
curl --fail http://localhost:5000/health
curl --fail -H 'Content-Type: application/json' -d '{"query":"{ health }"}' http://localhost:5000/graphql
docker compose -f integration/compose.yaml down
```

Frontend 5173, Gateway 5000; no se ocupa 8004. Gateway no depende del arranque de
otros microservicios; frontend solo espera su salud. No incorpora MongoDB,
RabbitMQ ni copias de servicios externos. No eliminar la red compartida al bajar
este Compose. B puede añadir overrides para conectar servicios por DNS sin
cambiar los repositorios externos ni el Compose original de Threads.

## Pruebas

```sh
# Gateway, desde raíz
/tmp/thread-gateway-venv/bin/python -m pytest -c gateway/pytest.ini gateway/tests -q -W error
# Frontend, desde frontend/
npm ci
npm test
npm run build
# Thread Service, entorno independiente, desde raíz
python3.12 -m venv /tmp/thread-original-venv
/tmp/thread-original-venv/bin/pip install -r requirements-dev.txt
/tmp/thread-original-venv/bin/python -m pytest -q -W error
/tmp/thread-original-venv/bin/python -m pytest scripts/test_k8s_rendering.py -q -W error
```

Gateway: lifespan sin red, salud REST/GraphQL, introspección completa, snapshot
independiente de v1, cada operación NOT_IMPLEMENTED, CORS y errores/transportes.
Frontend: acceso a todas las rutas, enlaces y estados activos, sin fetch de
dominio, cliente único, TypeScript y build. El workflow nuevo tarea6.yml valida
ambos proyectos y sus imágenes sin cambiar workflows existentes.
Las pruebas reales de Threads requieren MongoDB/RabbitMQ de prueba y omiten
casos cuando faltan sus variables; nunca apuntarlas al clúster existente.
El test del generador Kubernetes es offline y no ejecuta operaciones en clúster.
Resultados de esta entrega: [VALIDACION.md](VALIDACION.md).

## Ramas y Pull Requests

Base compartida: `feature/tarea6-base-compartida` → PR a main, sin merge automático.
Después de su revisión e integración por el equipo, cada integrante:

```sh
git switch main
git pull --ff-only origin main
git switch -c feature/tarea6-polls  # ejemplo de B; usar otra rama por funcionalidad
```

A trabaja chat/threads; B integrals/polls. No editar módulos ajenos para registrar
los propios. Actualizar main antes de cada rama y sincronizar antes de abrir PR.
Toda funcionalidad se integra por PR con pruebas, alcance y limitaciones.
Revisar archivos compartidos y cambios de contrato con el otro integrante.
No hacer commits directos a main; no versionar .env, tokens, node_modules, dist,
entornos virtuales, Secrets ni copias de repositorios externos.
