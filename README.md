
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
`grupo-threads`. Codex implementó y validó los archivos del repositorio; el autor
realizó manualmente el despliegue y las pruebas en Kubernetes. Los resultados y
sus evidencias se registran a continuación; los comandos posteriores se conservan
como referencia técnica para repetir operaciones de forma controlada.
Enunciado: <https://github.com/rmasad/microservicios/tree/main/05_Despliegue>.
Ejemplo: <https://github.com/rmasad/microservicios/tree/main/05_Despliegue/demo_05/api-gateway>.
Acceso: <https://gist.github.com/sebastianguerra/fe3cbc472cae1064548b456bb857bcf8>.

### Despliegue realizado y evidencias

El autor ejecutó manualmente el despliegue desde WSL y verificó estos resultados
en Kubernetes. Codex incorporó las capturas originales y documentó las
observaciones proporcionadas por el autor; esta actualización documental no
repitió operaciones sobre el clúster ni generó Secrets.

| Comprobación | Resultado observado |
|---|---|
| Namespace | `grupo-threads` |
| Thread API | Dos réplicas disponibles (`2/2`) |
| MongoDB | StatefulSet de una instancia; PVC de 1 GiB (`1Gi`), `Bound` |
| RabbitMQ y worker | Funcionando, Pods `1/1 Running` |
| Ingress | Traefik, IP `134.199.176.3` |
| URL pública | [Swagger de Thread Service](http://threads.134.199.176.3.nip.io/docs) |
| Salud y documentación | `GET /health`: HTTP 200; Swagger público: HTTP 200 |
| API REST | POST y GET probados satisfactoriamente |
| Persistencia | Tras reemplazar el Pod de MongoDB, el GET público recuperó una respuesta almacenada previamente, conservando el PVC |
| Probes MongoDB | Corrección aplicada; último Pod observado con cero reinicios |
| Autoscaling | CPU objetivo 70 %; escalamiento observado de 2 → 3 → 2 réplicas |
| GitHub Actions | Cinco checks aprobados en el commit anterior `0d582cc`; la captura no corresponde al commit documental final |

Durante la prueba manual de HPA se observó CPU inicial de **3 %** y, bajo carga,
lecturas de **66 %, 115 % y 112 %**. Se observó el aumento automático de **2 a 3
réplicas** y, después de finalizar la carga y transcurrir la ventana de
estabilización de **300 segundos**, el retorno a **2 réplicas**. Son observaciones
de la prueba realizada, no una secuencia temporal contenida en una sola captura.
En particular, **la cuarta imagen muestra la configuración y el estado del HPA,
no el momento del escalamiento**.

Las cinco capturas originales se conservan en
[docs/Evidencia_despliegue/](docs/Evidencia_despliegue/):

| Evidencia | Alcance de la captura |
|---|---|
| [01 — GitHub Actions](docs/Evidencia_despliegue/01-github-actions.png) | Cinco checks aprobados del commit anterior y PR en draft |
| [02 — Swagger público](docs/Evidencia_despliegue/02-swagger-publico.png) | Interfaz Swagger accesible mediante el Ingress Traefik |
| [03 — Despliegue Kubernetes](docs/Evidencia_despliegue/03-despliegue-kubernetes.png) | Pods, Deployments, HPA, Ingress y PVC; API con dos réplicas y volumen Bound |
| [04 — HPA Kubernetes](docs/Evidencia_despliegue/04-hpa-kubernetes.png) | Configuración y estado: objetivo 70 %, mínimo 2, máximo 3, estabilización de bajada 300 s y CPU 3 % en esa captura; no demuestra por sí sola el escalamiento |
| [05 — Persistencia MongoDB](docs/Evidencia_despliegue/05-persistencia-mongodb.png) | MongoDB Running con cero reinicios y GET público HTTP 200 recuperando una respuesta existente después de la prueba de reemplazo |

El hostname está operativo en la prueba, pero su **autorización formal sigue
pendiente**. El acceso es **HTTP, sin TLS y sin autenticación propia de Thread
Service**. Se mantienen los trade-offs: Recreate interrumpe el servicio durante
actualizaciones, RabbitMQ usa almacenamiento efímero y puede perder eventos ya
publicados al perder su Pod, y MongoDB no tiene alta disponibilidad ni un backup
incluido. La prueba de persistencia confirma reutilización del PVC, no tolerancia
a pérdida del volumen.

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
- `k8s/kustomization.yaml`: ensambla los recursos. El Ingress parametrizable y
  los Secrets se generan aparte; **no usar `kubectl apply -f k8s/`**.
- `scripts/prepare_k8s.py`: genera manifiestos locales ignorados por Git,
  exige digest GHCR y host confirmado, separa siete etapas en
  `k8s/rendered/stages/` y solicita credenciales sin eco cuando se pide un Secret.
- `scripts/validate_k8s.py`: comprueba referencias y presupuesto sin conectarse
  al clúster. Requiere Python, PyYAML y `kubectl kustomize`.

Flujo HTTP: Internet → Traefik → Service `thread-api` → réplicas API → MongoDB.
API → Users/Messages de servicios-base. Worker → misma MongoDB → RabbitMQ.
MongoDB es una sola instancia persistente, sin alta disponibilidad ni backup
incluido. No borrar su PVC durante actualizaciones o rollback.

En el preflight del 1 de noviembre de 2026 se consultaron permisos, cuotas,
Services e Ingresses: el namespace estaba vacío salvo un ConfigMap. Esa era la
situación previa al despliegue manual documentado arriba. Traefik expone la IP
pública **134.199.176.3**, utilizada en las pruebas. El hostname
`threads.134.199.176.3.nip.io` funciona, pero sigue **pendiente de autorización
formal**; resolver DNS y recibir HTTP no sustituyen la confirmación del
administrador. `PENDING_PUBLIC_HOST` permanece como plantilla excluida del conjunto
base; confirmar la política de hostname antes de nuevas exposiciones. No se
configuró TLS: su configuración depende de confirmar dominio y política de
certificados.

La consulta de Services de todos los namespaces no identificó un RabbitMQ
compartido autorizado. Los brokers visibles pertenecen a otros grupos; no se
usaron ni se inspeccionaron sus credenciales. Por eso se utiliza el broker local.
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
| API, por Pod | 2–3 | 100m | 80Mi | 200m | 128Mi |
| Worker | 1 | 50m | 96Mi | 200m | 192Mi |
| MongoDB | 1 | 100m | 256Mi | 300m | 512Mi |
| RabbitMQ | 1 | 100m | 192Mi | 300m | 512Mi |
| Total inicial | 5 | 450m | 704Mi | 1200m | 1472Mi |
| Total HPA máximo | 6 | 550m | 784Mi | 1400m | 1600Mi |
| Recreate: 3 API antiguas terminando, 0 nuevas | 6 | 550m | 784Mi | 1400m | 1600Mi |
| Recreate: 0 API antes de crear las nuevas | 3 | 250m | 544Mi | 800m | 1216Mi |
| Recreate: 3 API nuevas, 0 antiguas | 6 | 550m | 784Mi | 1400m | 1600Mi |
| Cuota | 10 | 1000m | 1024Mi | 2000m | 2048Mi |

Se crean 3 Deployments/10, 1 StatefulSet/3, 1 HPA/5, 3 Services/10,
1 PVC/1 y 1Gi/1Gi de almacenamiento; con Ingress: 1/5. ConfigMap: 1 nuevo
más 1 existente /20. Secret: 1/20; un registry privado requeriría otro.
Todos los contenedores declaran requests y limits inferiores al LimitRange.

La opción C utiliza **Recreate en API**, worker y RabbitMQ; MongoDB reemplaza
su único Pod en el StatefulSet. En una actualización de versión, la API espera
la terminación de la revisión anterior antes de crear la nueva. Se conservan
dos réplicas mínimas en operación normal y HPA 2–3 al 70 %, pero durante cada
actualización hay una **interrupción completa de HTTP**, que dura hasta que las
nuevas API estén listas. Acordar una ventana; esto no es alta disponibilidad.

Los requests y limits por contenedor se conservan. Al máximo normal y durante
una actualización Recreate controlada, el margen es:

| Cuota | Uso máximo | Margen restante |
|---|---:|---:|
| Pods | 6/10 (60 %) | 4 (40 %) |
| Requests CPU | 550m/1000m (55 %) | 450m (45 %) |
| Requests memoria | 784Mi/1024Mi (76,56 %) | 240Mi (23,44 %) |
| Limits CPU | 1400m/2000m (70 %) | 600m (30 %) |
| Limits memoria | 1600Mi/2048Mi (78,12 %) | 448Mi (21,88 %) |

El validador exige al menos 20 % de margen de cómputo y Pods en esas fases.
No hay margen de PVC ni almacenamiento: 1 PVC y 1Gi consumen toda esa cuota.
Los cálculos suponen actualizaciones secuenciales, sin otros workloads del grupo,
sin borrados manuales ni actualizaciones concurrentes. Recreate no garantiza el
mismo límite ante reemplazos por borrado manual de Pods; no forzar eliminaciones.
La cuota del namespace tampoco reserva capacidad física de los nodos.

Los 128Mi de límite de API y el consumo de probes aún necesitan medición bajo
carga en Kubernetes. No se bajó memoria para obtener este margen. Si aparece
OOMKilled, detener la carga, medir y revisar límites/cuota antes de aumentar
memoria. No recortar MongoDB o RabbitMQ como compensación. Antes de cada etapa,
volver a consultar cuota, capacidad de nodos y eventos.

API tiene startup/readiness/liveness HTTP `/health`. El lifespan inicializa los
índices de MongoDB antes de servir. Después del arranque `/health` solo confirma
el proceso HTTP, no la salud de dependencias: validar también operaciones reales.
MongoDB usa TCP 27017 para startup (60 fallos cada 10 s, timeout 5 s y demora
inicial 10 s, aproximadamente 10 minutos) y liveness (6 fallos cada 30 s,
timeout 5 s, aproximadamente 3 minutos de fallos continuos). Esto evita lanzar
`mongosh` para decidir reinicios en un contenedor con CPU limitada. TCP solo
confirma que el puerto acepta conexiones: puede no detectar un servidor que
acepta sockets pero no procesa operaciones. Readiness conserva el ping funcional
con `mongosh`, timeout 15 s, intervalo 20 s y 3 fallos; si falla, retira el Pod
de endpoints sin reiniciarlo. Startup y liveness todavía pueden reiniciar ante
un listener inaccesible persistente. No sustituye las pruebas de persistencia/REST.
Actualizar el StatefulSet reemplaza su único Pod, con interrupción temporal,
pero conserva la identidad y el PVC existente. No borrar el Pod ni el volumen.

RabbitMQ comprueba TCP 5672 en startup y readiness, sin ejecutar
`rabbitmq-diagnostics` periódicamente ni configurar liveness. La
[guía oficial de RabbitMQ](https://www.rabbitmq.com/docs/monitoring#health-checks-as-readiness-probes)
recomienda readiness TCP y ausencia de liveness para evitar sobrecarga de las CLI
y reinicios por falsos positivos. Startup espera aproximadamente 10 minutos
(60 fallos, intervalo 10 s, timeout TCP 5 s y demora inicial 10 s); si nunca abre
el puerto, puede reiniciar el contenedor. Tras startup, readiness cada 10 s marca
Unready después de tres fallos, sin reiniciarlo. TCP solo demuestra que el puerto
acepta conexiones: comprobar autenticación, alarmas y publicación outbox aparte.
Un proceso bloqueado después de startup requiere diagnóstico e intervención;
la salida del proceso sí activa la política normal de reinicio del Deployment.
Cambiar estas probes reemplaza el Pod por Recreate y pierde el contenido de su
`emptyDir`; coordinar la actualización si ya contiene eventos.
Worker
comprueba su proceso PID 1; esto no prueba publicación ni avance de la outbox.
Se evita reiniciarlo por indisponibilidad del broker porque ya reintenta con
backoff. Validar publicación y backlog tras desplegar. Worker dispone de 70 s
para SIGTERM, frente a 60 s de lease; las conexiones AMQP tienen sus propios
timeouts. No hay initContainers ni Pods auxiliares que consuman cuota.

Para regenerar **solo la etapa local de RabbitMQ**, sin host, digest de API ni
Secret nuevos, ejecutar desde la raíz del repositorio:

```bash
mkdir -p k8s/rendered/stages
cp k8s/rabbitmq.yaml k8s/rendered/stages/03-rabbitmq.yaml
```

Después, únicamente con autorización para modificar el clúster, aplicar esa
etapa; no reaplicar el consolidado ni MongoDB. Comandos de referencia, no ejecutados por Codex:

```bash
k() { kubectl --context cluster-inf326-2026-2 -n grupo-threads "$@"; }
k apply -f k8s/rendered/stages/03-rabbitmq.yaml
k rollout status deployment/thread-rabbitmq --timeout=900s
k get pods -l app=thread-rabbitmq
k get endpointslices -l kubernetes.io/service-name=thread-rabbitmq
```

Este atajo actualiza únicamente el archivo de RabbitMQ; no sincroniza el
consolidado local, que debe regenerarse si se decide usarlo en otra ocasión.
El PVC y los Secrets existentes no forman parte de esta etapa.

Para regenerar solo la etapa MongoDB sin tocar Secrets ni otras etapas:

```bash
mkdir -p k8s/rendered/stages
cp k8s/mongodb.yaml k8s/rendered/stages/02-mongodb.yaml
```

Antes de aplicar, comprobar con `k diff -f k8s/rendered/stages/02-mongodb.yaml`
que el único cambio real sean las probes del StatefulSet (diff usa 1 si hay
cambios). Si aparecen diferencias de PVC, imagen, args o recursos, detenerse.
Los siguientes comandos son para una etapa autorizada; Codex no los ejecutó:

```bash
k apply -f k8s/rendered/stages/02-mongodb.yaml
k rollout status statefulset/thread-mongodb --timeout=900s
k get pod thread-mongodb-0
k get pvc thread-mongodb-data
```

La etapa conserva Service y PVC sin cambios; no usar `--force`, borrar volúmenes
ni reaplicar el consolidado. Verificar Ready, PVC Bound, eventos y lectura de un
dato previamente guardado tras la sustitución. Este atajo no actualiza el consolidado.

### CI y publicación en GHCR

Se conserva `.github/workflows/tests.yml`. El workflow adicional `container.yml`
ejecuta las pruebas con MongoDB y RabbitMQ aislados, valida referencias/cuotas,
ejecuta pruebas offline del generador por etapas y de las probes de MongoDB/RabbitMQ y construye el target `runtime` del **Dockerfile existente**. En pushes a `main` o
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
python -m pytest scripts/test_k8s_rendering.py -q -W error
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
install -d -m 700 "$HOME/.local/share/thread-service"
export THREAD_SECRET_FILE="$HOME/.local/share/thread-service/secret.yaml"
python scripts/prepare_k8s.py --image "$THREAD_IMAGE" --host "$THREAD_PUBLIC_HOST" --secret-file "$THREAD_SECRET_FILE"
```

Ingresar usuario y contraseña MongoDB y usuario y contraseña RabbitMQ cuando se
soliciten. Se genera `$THREAD_SECRET_FILE`, modo 0600, fuera del repositorio y OneDrive, y
siete archivos en `k8s/rendered/stages/`, ignorados por Git y Docker.
También se genera `k8s/rendered/workloads.yaml`, un consolidado equivalente. El script rechaza rutas
de Secrets dentro del repositorio o OneDrive. Guardar el Secret en un directorio
privado del filesystem Linux de WSL; Git ignore no impide sincronización. No imprimir el archivo ni usar `set -x`. No versionar secretos,
kubeconfig, logs sensibles ni la salida de `kubectl get secrets -o yaml`.
El Secret contiene URLs con credenciales codificadas; MongoDB requiere
`authSource=admin`. Su usuario root es exclusivo de esta base del servicio;
para producción crear un usuario de aplicación con privilegios mínimos.
Usar un usuario RabbitMQ distinto de `guest`; el generador lo exige. El
directorio padre debe ser privado y estar fuera de cualquier otro repositorio Git
y carpeta sincronizada: el script solo detecta este repositorio y rutas OneDrive.
Cambiar credenciales en el Secret no rota usuarios ya inicializados en el PVC.

Validar también el archivo renderizado con kubeconform. Revisar que host, imagen
y credenciales coincidan, sin pegar el Secret en logs o revisiones.

### Procedimiento de despliegue progresivo

**Referencia técnica: el despliegue inicial ya fue ejecutado manualmente por el
autor. Codex no ejecutó estos comandos sobre Kubernetes.** No repetir sobre el
entorno existente sin revisar su estado y autorizar los cambios. Primero
confirmar hostname, digest, recursos libres y funcionamiento del CSI. Validar
los siete archivos con kubeconform. No aplicar la carpeta entera ni el consolidado
si se utiliza el procedimiento progresivo: se perderían las esperas entre etapas.
El consolidado es una alternativa, no un octavo paso. Cada uno de los 11 recursos
pertenece a una sola etapa; el Secret queda fuera de todos los manifiestos públicos.

| Etapa | Archivo en `k8s/rendered/stages/` | Recursos / condición para continuar |
|---|---|---|
| 1 | `01-config.yaml` | ConfigMap; Secret privado creado por separado |
| 2 | `02-mongodb.yaml` | Service, PVC y StatefulSet; PVC Bound y MongoDB Ready |
| 3 | `03-rabbitmq.yaml` | Service y Deployment; broker Ready |
| 4 | `04-api.yaml` | Service y Deployment; dos réplicas Ready, probar REST |
| 5 | `05-worker.yaml` | Deployment; Ready y evidencia de publicación outbox |
| 6 | `06-ingress.yaml` | Ingress; host autorizado y prueba HTTP externa |
| 7 | `07-hpa.yaml` | HPA; métricas disponibles y escalamiento verificable |

No avanzar si una espera falla. `Available` no sustituye las pruebas REST o de
eventos; las probes del worker solo comprueban que el proceso existe.

```bash
k() { kubectl --context cluster-inf326-2026-2 -n grupo-threads "$@"; }
# THREAD_SECRET_FILE: ruta privada al Secret generado anteriormente.
k apply -f "$THREAD_SECRET_FILE"
k apply -f k8s/rendered/stages/01-config.yaml

k apply -f k8s/rendered/stages/02-mongodb.yaml
k wait --for=jsonpath='{.status.phase}'=Bound pvc/thread-mongodb-data --timeout=180s
k wait --for=condition=Ready pod/thread-mongodb-0 --timeout=300s

k apply -f k8s/rendered/stages/03-rabbitmq.yaml
k wait --for=condition=Available deployment/thread-rabbitmq --timeout=300s

k apply -f k8s/rendered/stages/04-api.yaml
k wait --for=jsonpath='{.status.readyReplicas}'=2 deployment/thread-api --timeout=300s
# Comprobar endpoints, HTTP y REST antes de continuar.
# En otra terminal: k port-forward service/thread-api 8004:8000
# curl --fail http://127.0.0.1:8004/health

k apply -f k8s/rendered/stages/05-worker.yaml
k wait --for=condition=Available deployment/thread-worker --timeout=300s
# Verificar publicación de un evento de prueba antes de continuar.

k apply -f k8s/rendered/stages/06-ingress.yaml
k get ingress thread-api
curl --fail --max-time 10 "http://$THREAD_PUBLIC_HOST/health"
# Probar también POST/GET público con IDs de prueba válidos.

k apply -f k8s/rendered/stages/07-hpa.yaml
k get hpa thread-api
k describe hpa thread-api
```

Revisar entre etapas, siempre dentro de `grupo-threads`:

```bash
k get pods -o wide
k get deployments,statefulsets,services,ingresses,hpa,pvc
k get endpointslices
k get resourcequota
k top pods --containers
k get events --sort-by=.metadata.creationTimestamp
k describe pod <pod>
k logs deployment/thread-api --tail=100
k logs deployment/thread-worker --tail=100
# Si hubo un reinicio: k logs <pod> --previous --tail=100
```

Revisar los logs localmente antes de compartirlos; no imprimir Secrets, kubeconfig
ni variables con credenciales. Las pruebas REST crean/leen una respuesta del propio
servicio usando IDs existentes de Users/Messages, sin modificar sus bases. Para
outbox, correlacionar respuesta, evento y publicación confirmada en la misma MongoDB;
una probe Ready no demuestra entrega. Un broker local tampoco establece por sí
solo comunicación con consumidores de otros servicios. La prueba de persistencia
tras reemplazo de MongoDB ya se verificó manualmente, según el apartado de
evidencias; repetirla requiere autorización específica y conservar el PVC.

### Validación en Freelens y diagnóstico

Seleccionar `cluster-inf326-2026-2` y filtrar `grupo-threads`. Revisar:

- MongoDB: PVC Bound, volumen montado, Pod Ready y eventos del CSI.
- RabbitMQ: readiness, reinicios, uso de memoria y alarmas de disco/memoria.
- API: dos réplicas listas antes del HPA, imagen por digest y endpoints del Service.
- Worker: proceso Ready, errores de reintento y publicación comprobada aparte.
- Ingress: clase traefik, host autorizado, Service y puerto 8000; probar desde WSL.
- HPA: métricas CPU, condiciones AbleToScale/ScalingActive y réplicas deseadas.
- General: consumo por contenedor, cuota restante y eventos de cada workload.

| Falla | Revisar y proceder |
|---|---|
| Pending | Eventos del Pod y ReplicaSet: Insufficient CPU/memory, taints, PVC sin Bound o FailedAttachVolume. Comprobar nodos y CSI; detener la progresión y coordinar capacidad. No reducir memoria para forzar scheduling. |
| FailedCreate | Eventos de Deployment/ReplicaSet y ResourceQuota/LimitRange: puede no existir aún un Pod que inspeccionar. No continuar mientras falte cuota. |
| OOMKilled | Last State, exit code, reinicios, memoria y logs previos. Detener carga; medir picos y revisar límites/cuota. No reiniciar repetidamente ni reducir otros componentes. |
| ImagePullBackOff | Digest exacto, Events y acceso a GHCR desde el nodo. Distinguir imagen inexistente, fallo DNS/red y autorización. Usar un imagePullSecret privado solo si el paquete lo requiere. |

Para la demostración de HPA, generar carga externa desde WSL sobre `/health`,
sin Pods auxiliares ni llamadas repetitivas a servicios base. Empezar con 5,
luego 10 y 20 solicitudes/s, concurrencia máxima 2 y ventanas cortas acordadas.
Observar `k get hpa -w`, latencia, errores y memoria; detener ante fallas o falta
de capacidad. El objetivo 70 % corresponde a 70m CPU medios por API, no al 70 %
del límite. Si la carga acotada no lo alcanza, registrar el resultado sin saturar
el clúster. Observar la bajada tras la estabilización de 300 segundos.

### Actualizaciones y rollback

Guardar el digest anterior. Preparar una nueva versión sin `--secret-file` para
preservar credenciales. API y worker interrumpen servicio durante su Recreate;
acordar una ventana también para rollback. En actualizaciones no reaplicar `replicas: 2` sobre el
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

### Validación previa del repositorio

Durante la preparación y corrección de probes con la opción C: la suite local y las pruebas offline del generador dieron
**121 passed, 6 skipped** (101 pruebas existentes y 20 de empaquetado/probes;
las seis omitidas requieren MongoDB/RabbitMQ de prueba). Las pruebas de etapas
se ejecutan por separado en CI para conservar el target de pruebas del Dockerfile
existente, que solo empaqueta la aplicación y sus pruebas funcionales.

El validador confirma Recreate, HPA 2–3 al 70 %, referencias, cuotas y un margen
mínimo de 20 % en Pods/cómputo durante operación y actualización controlada.
Los recursos por contenedor se compararon con la revisión anterior: sin cambios.
Kubeconform 0.7.0 estricto validó los **11 recursos en 7 archivos de etapas** y
los mismos **11 recursos en el consolidado**, usando host reservado de prueba y
sin Secrets. El conjunto base sigue conteniendo 10 recursos sin Ingress.
Esto valida esquemas, no admisión, scheduling ni funcionamiento en Kubernetes.
Actionlint 1.7.7 pasó para ambos workflows. Codex no generó credenciales reales.

El hostname utilizado sigue pendiente de autorización formal. Codex no ejecutó
`kubectl apply`, `delete`, `rollout`, `set image` ni cambios de recursos del clúster.
El despliegue y las pruebas reales fueron ejecutados manualmente por el autor y
quedan documentados en «Despliegue realizado y evidencias».

## Tarea 6: Gateway e interfaz

Gateway FastAPI + Ariadne y frontend React + TypeScript + Vite independientes
de Thread Service. Contrato, responsabilidades de A/B, entorno, ejemplos de
extensión y pruebas: [CONTRATO_COMPARTIDO.md](docs/tarea6/CONTRATO_COMPARTIDO.md).
Chat y Threads incluyen identidad local, canales, mensajes y panel de respuestas.
Guía de uso, pruebas, capturas y límites de integración real:
[CHAT_FRONTEND.md](docs/tarea6/CHAT_FRONTEND.md).
Integrales y Polls conservan sus placeholders hasta la implementación de Andrés.
Salud e introspección del Gateway funcionan sin servicios externos.

```sh
# Crear solo si la red no existe:
docker network create microsvcs
docker compose -f integration/compose.yaml up --build -d
# Frontend http://localhost:5173; Gateway http://localhost:5000/health
# GraphQL POST http://localhost:5000/graphql, consulta { health }
```

Para desarrollo sin Docker, instalación y pruebas consultar el contrato.
La configuración nueva no ocupa el puerto 8004 ni modifica el Compose original.
Resultados de validación: [docs/tarea6/VALIDACION.md](docs/tarea6/VALIDACION.md).
