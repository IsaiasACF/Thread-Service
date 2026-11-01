
# Thread Service

### Integrantes
* Andrés Jablonca 202173578-K
* Isaías Carte 202273606-2

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

## Tarea 5: despliegue Kubernetes

Implementación individual para `cluster-inf326-2026-2`, exclusivamente en
`grupo-threads`. Esta etapa prepara los archivos: **no despliega al clúster**.
Enunciado: <https://github.com/rmasad/microservicios/tree/main/05_Despliegue>.
Ejemplo: <https://github.com/rmasad/microservicios/tree/main/05_Despliegue/demo_05/api-gateway>.
Acceso: <https://gist.github.com/sebastianguerra/fe3cbc472cae1064548b456bb857bcf8>.

### Arquitectura y archivos

- `k8s/api.yaml`: Deployment `thread-api` con 2 réplicas iniciales, Service
  ClusterIP en 8000 y HPA `autoscaling/v2`, 2–3 réplicas, CPU objetivo 70 %.
- `k8s/worker.yaml`: `thread-worker`, una réplica, comando
  `python -m app.workers.outbox`. Usa exactamente la misma imagen, Secret,
  base `threads` y colección `replies` que la API.
- `k8s/mongodb.yaml`: StatefulSet de una instancia, Service headless y PVC
  `thread-mongodb-data`, 1Gi, `do-block-storage`, `ReadWriteOnce`.
  MongoDB 7 usa un cache WiredTiger de 0.25Gi; vigilar memoria y espacio.
- `k8s/rabbitmq.yaml`: Deployment de una instancia, Service ClusterIP 5672,
  RabbitMQ 4 sin interfaz de administración y `emptyDir` de 256Mi.
- `k8s/configmap.yaml`: URLs de Users y Messages en `servicios-base`, parámetros
  compartidos. No se despliegan copias ni se accede a sus bases.
- `k8s/kustomization.yaml`: ensambla los recursos. El Ingress pendiente y los
  Secrets se generan aparte; **no usar `kubectl apply -f k8s/`**.
- `scripts/prepare_k8s.py`: genera manifiestos locales ignorados por Git,
  exige digest GHCR y host confirmado y solicita credenciales sin eco.
- `scripts/validate_k8s.py`: comprueba referencias y presupuesto sin conectarse
  al clúster. Requiere Python, PyYAML y `kubectl kustomize`.

Flujo HTTP: Internet → Traefik → Service `thread-api` → réplicas API → MongoDB.
API → Users/Messages de servicios-base. Worker → misma MongoDB → RabbitMQ.
MongoDB es una sola instancia persistente, sin alta disponibilidad ni backup
incluido. No borrar su PVC durante actualizaciones o rollback.

El 1 de noviembre de 2026 se consultaron permisos, cuotas, Services e Ingresses:
se permite administrar los recursos requeridos en el namespace; estaba vacío
salvo un ConfigMap. Traefik tiene IP pública **134.199.176.3**. No existe un host
asignado a Threads. Otros grupos usan nip.io, pero eso no asigna un dominio a
este servicio: `PENDING_PUBLIC_HOST` es una plantilla excluida del conjunto base.
Antes de desplegar, confirmar el dominio con el administrador y comprobar que
resuelva a la IP vigente. No se configura TLS hasta confirmar dominio y política
de certificados; el Ingress preparado utiliza HTTP.

La consulta de Services de todos los namespaces no identificó un RabbitMQ
compartido autorizado. Los brokers visibles pertenecen a otros grupos; no se
usaron ni se inspeccionaron sus credenciales. Por eso se prepara el broker local.
Si el administrador entrega un broker compartido, quitar `rabbitmq.yaml` de
Kustomize y configurar su URL AMQP mediante el Secret antes de desplegar.

**RabbitMQ efímero pierde colas y mensajes al reemplazar o perder su Pod**.
Un evento ya confirmado y marcado publicado en MongoDB no se reenvía por esa
pérdida. No es una solución tolerante a pérdidas de Pods. La outbox conserva
los eventos aún no confirmados y reintenta, con posible entrega duplicada.
El disco efímero se limita a 256Mi; observar alarmas de memoria/disco y backlog.
Para durabilidad real se necesita broker persistente autorizado o más PVC.

### Recursos, actualizaciones y probes

| Componente | Réplicas | CPU request | Memoria request | CPU limit | Memoria limit |
|---|---:|---:|---:|---:|---:|
| API, por Pod | 2–3 | 100m | 96Mi | 250m | 192Mi |
| Worker | 1 | 50m | 96Mi | 200m | 192Mi |
| MongoDB | 1 | 100m | 256Mi | 300m | 512Mi |
| RabbitMQ | 1 | 100m | 192Mi | 300m | 512Mi |
| Total inicial | 5 | 450m | 736Mi | 1300m | 1600Mi |
| Total HPA máximo | 6 | 550m | 832Mi | 1550m | 1792Mi |
| Máximo + 1 API terminando | 7 | 650m | 928Mi | 1800m | 1984Mi |
| Cuota | 10 | 1000m | 1024Mi | 2000m | 2048Mi |

Se crean 3 Deployments/10, 1 StatefulSet/3, 1 HPA/5, 3 Services/10,
1 PVC/1 y 1Gi/1Gi de almacenamiento; con Ingress: 1/5. ConfigMap: 1 nuevo
más 1 existente /20. Secret: 1/20; un registry privado requeriría otro.
Todos los contenedores declaran requests y limits inferiores al LimitRange.

API usa `maxSurge: 0`, `maxUnavailable: 1`. Worker y RabbitMQ usan `Recreate`;
MongoDB reemplaza su único Pod en el StatefulSet. Esto evita réplicas de surge
intencionales; worker, broker y base tienen interrupción al actualizarse.
Los Pods terminando pueden seguir contando contra la cuota. Un API adicional
cabe; dos API adicionales sumarían límites de 2176Mi y **no caben**. Kubernetes
puede retrasar admisiones por cuota durante terminaciones lentas. No se promete
cero downtime ni avance inmediato del rollout: actualizar componentes de a uno,
esperar que desaparezcan los Pods anteriores y revisar eventos antes de seguir.
No elevar `maxSurge` ni lanzar rollouts concurrentes. El HPA no reserva recursos
para otros workloads: volver a consultar cuota antes de cada despliegue.

API tiene startup/readiness/liveness HTTP `/health`. El lifespan inicializa los
índices de MongoDB antes de servir. Después del arranque `/health` solo confirma
el proceso HTTP, no la salud de dependencias: validar también operaciones reales.
MongoDB usa ping; RabbitMQ usa diagnóstico del nodo y estado running. Worker
comprueba su proceso PID 1; esto no prueba publicación ni avance de la outbox.
Se evita reiniciarlo por indisponibilidad del broker porque ya reintenta con
backoff. Validar publicación y backlog tras desplegar. Worker dispone de 70 s
para SIGTERM, frente a 60 s de lease; las conexiones AMQP tienen sus propios
timeouts. No hay initContainers ni Pods auxiliares que consuman cuota.

### CI y publicación en GHCR

Se conserva `.github/workflows/tests.yml`. El workflow adicional `container.yml`
ejecuta las pruebas con MongoDB y RabbitMQ aislados, valida referencias/cuotas y
construye el target `runtime` del **Dockerfile existente**. En pushes a `main` o
`feature/tarea5-kubernetes` publica
`ghcr.io/isaiasacf/thread-service:sha-<SHA completo>` con `GITHUB_TOKEN` y
`packages: write`. Los PR solo prueban y construyen, sin publicar. No hay
kubeconfig ni despliegue automático en Actions.

Consultar Actions y el paquete tras el push. La publicación puede requerir
habilitar permisos de escritura de paquetes en el repositorio. Configurar el
paquete como público o preparar un imagePullSecret local con token de solo
lectura y referenciarlo en ambos Deployments (no guardar ese token en Git).
Verificar descarga desde el clúster antes de considerar el despliegue listo.
El resumen del paso build-push muestra el digest; usarlo para API y worker.

### Preparación y validación sin cambios al clúster

Ejecutar desde la raíz del repositorio:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt PyYAML==6.0.3
pytest -q -W error
python scripts/validate_k8s.py
kubectl kustomize k8s > /tmp/thread-k8s.yaml
# Si se dispone de kubeconform:
kubeconform -strict -summary /tmp/thread-k8s.yaml
kubectl --context cluster-inf326-2026-2 -n grupo-threads auth can-i --list
kubectl --context cluster-inf326-2026-2 -n grupo-threads get resourcequota,limitrange
```

Las pruebas de integración requieren instancias **locales de prueba** de MongoDB
y RabbitMQ; sin `THREAD_TEST_MONGODB_URL`/`THREAD_TEST_RABBITMQ_URL` se omiten.
No apuntar esas variables a servicios o bases del clúster. Con Docker disponible:

```bash
docker compose config --quiet
docker compose --profile test run --build --rm tests
docker build --target runtime -t thread-service:local .
```

Una vez confirmados host y digest, preparar archivos (aún sin tocar el clúster):

```bash
export THREAD_PUBLIC_HOST='<host confirmado>'
export THREAD_IMAGE='ghcr.io/isaiasacf/thread-service@sha256:<digest publicado>'
umask 077
mkdir -p /tmp/thread-private
export THREAD_SECRET_FILE=/tmp/thread-private/thread-secret.yaml
python scripts/prepare_k8s.py --image "$THREAD_IMAGE" --host "$THREAD_PUBLIC_HOST" --secret-file "$THREAD_SECRET_FILE"
```

Ingresar usuario y contraseña MongoDB y usuario y contraseña RabbitMQ cuando se
soliciten. Se genera `$THREAD_SECRET_FILE`, modo 0600, fuera del repositorio y OneDrive, y
`k8s/rendered/workloads.yaml`, ignorado por Git y Docker. El script rechaza rutas
de Secrets dentro del repositorio o OneDrive. Guardar el Secret en un directorio
privado del filesystem Linux de WSL; Git ignore no impide sincronización. No imprimir el archivo ni usar `set -x`. No versionar secretos,
kubeconfig, logs sensibles ni la salida de `kubectl get secrets -o yaml`.
El Secret contiene URLs con credenciales codificadas; MongoDB requiere
`authSource=admin`. Su usuario root es exclusivo de esta base del servicio;
para producción crear un usuario de aplicación con privilegios mínimos.
Cambiar credenciales en el Secret no rota usuarios ya inicializados en el PVC.

Validar también el archivo renderizado con kubeconform. Revisar que host, imagen
y credenciales coincidan, sin pegar el Secret en logs o revisiones.

### Despliegue futuro — requiere autorización de la siguiente etapa

**Estos comandos se documentan; no se ejecutaron en esta implementación.**
Usar un archivo Secret privado fuera de OneDrive y ajustar `THREAD_SECRET_FILE`.

```bash
export THREAD_SECRET_FILE='<ruta privada al Secret generado>'
kubectl --context cluster-inf326-2026-2 -n grupo-threads apply -f "$THREAD_SECRET_FILE"
kubectl --context cluster-inf326-2026-2 -n grupo-threads apply -f k8s/rendered/workloads.yaml
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout status statefulset/thread-mongodb --timeout=300s
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout status deployment/thread-rabbitmq --timeout=300s
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout status deployment/thread-api --timeout=300s
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout status deployment/thread-worker --timeout=300s
kubectl --context cluster-inf326-2026-2 -n grupo-threads get pods,services,ingresses,hpa,pvc
kubectl --context cluster-inf326-2026-2 -n grupo-threads top pods
kubectl --context cluster-inf326-2026-2 -n grupo-threads get events --sort-by=.metadata.creationTimestamp
curl --fail "http://$THREAD_PUBLIC_HOST/health"
```

En Freelens seleccionar contexto y namespace; revisar Pods, recursos, PVC,
HPA y eventos. Validar creación/lectura de una respuesta con IDs de prueba
válidos de Users/Messages sin modificar sus bases. Confirmar que el worker
publique y que el consumidor esperado pueda conectarse al broker: un RabbitMQ
local no establece por sí solo integración con brokers de otros servicios.
Para validar HPA, acordar carga acotada y observar `kubectl get hpa -w`; 70 %
significa 70m CPU media por réplica, no 70 % del límite de CPU.

### Actualizaciones y rollback

Guardar el digest anterior. Preparar una nueva versión sin `--secret-file` para
preservar credenciales. En actualizaciones no reaplicar `replicas: 2` sobre el
Deployment ya controlado por HPA: usar `set image` por componente, en secuencia.

```bash
kubectl --context cluster-inf326-2026-2 -n grupo-threads set image deployment/thread-api api="$THREAD_IMAGE"
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout status deployment/thread-api --timeout=300s
# Comprobar que no queden Pods API anteriores terminando antes de continuar.
kubectl --context cluster-inf326-2026-2 -n grupo-threads get pods
kubectl --context cluster-inf326-2026-2 -n grupo-threads set image deployment/thread-worker worker="$THREAD_IMAGE"
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout status deployment/thread-worker --timeout=300s
```

Para volver a una revisión previa (revisar `rollout history` primero):

```bash
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout history deployment/thread-api
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout undo deployment/thread-api
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout status deployment/thread-api --timeout=300s
# Esperar eliminación de Pods anteriores antes de restaurar worker.
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout undo deployment/thread-worker
kubectl --context cluster-inf326-2026-2 -n grupo-threads rollout status deployment/thread-worker --timeout=300s
```

Si no hay revisión previa, usar el digest anterior con `set image`. El rollback
de Deployments no restaura datos, configuración ni Secrets. No borrar PVC ni
recrear MongoDB/RabbitMQ para revertir la API; RabbitMQ efímero pierde sus mensajes
al reemplazarse. Restaurar ConfigMap/Secrets de forma controlada si cambiaron.

### Validación de esta etapa

El 1 de noviembre de 2026: `pytest -q -W error` local dio **101 passed,
6 skipped** (integraciones optativas sin procesos MongoDB/RabbitMQ locales).
El validador de referencias/cuotas pasó. Kubeconform 0.7.0 en modo estricto validó
los 10 recursos base y 11 al incluir un Ingress renderizado con datos sintéticos;
esto valida el esquema, no las políticas de admisión del clúster. Actionlint
1.7.7 pasó para ambos workflows. El generador de Secret se comprobó con valores
sintéticos fuera del repositorio y permisos 0600. Docker no pudo conectarse al
daemon local; la construcción e integraciones reales se verifican en Actions.
No se ejecutaron `kubectl apply`, `delete`, ni cambios de recursos del clúster.
