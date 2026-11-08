# Tarea 6 — Integración real de Chat y Threads

## Resultado y autorización de merge

El PR #6 se fusionó con autorización expresa del autor, tras verificar destino
main, ausencia de conflictos y cinco checks SUCCESS. Commit resultante:
**`47a05ce942c88934c3bcadec1f8061962602d13a`**. Esta rama
`feature/tarea6-chat-integration` parte de ese main actualizado. No autoriza
fusionar este nuevo PR ni el trabajo de Andrés.

**Se ejecutaron servicios reales, pero el E2E estricto no está aprobado.**
Las cinco consultas y createReply funcionan; createUser, createChannel y
sendMessage guardan datos, pero sus servicios docentes responden HTTP 500 por
serialización de ObjectId. El Gateway y React comunican correctamente el error;
no se convirtieron fallas en éxitos, no se modificaron esos servicios y no se
introdujeron mocks para conseguir el recorrido.

## Arquitectura realmente utilizada

Docker CLI está instalado, pero no hay daemon/socket operativo. El intento
rootless falló por ausencia de `newuidmap`; sudo no está disponible sin contraseña.
En lugar de usar Kubernetes se ejecutó este stack **como procesos locales**:

```text
Chromium → Vite :15173 → /graphql → Gateway :15000
                                      ├─ Users :18001 ─── chat_users (MongoDB)
                                      ├─ Channels :18002 ─ chat_channels (MongoDB)
                                      ├─ Messages :18003 ─ chat_messages (MongoDB) + RabbitMQ
                                      └─ Threads :18004 ── chat_integration_threads (MongoDB)
                                                           └─ worker → RabbitMQ :15679
```

MongoDB real escucha en 127.0.0.1:27027 y usa un directorio nuevo de datos. El
fallback utiliza una instancia dedicada para cuatro bases separadas; Compose
prepara cuatro contenedores MongoDB con volúmenes independientes. Ninguna API
consulta directamente la base de otra: la inspección MongoDB se hace únicamente
en el script de diagnóstico de este entorno privado.

Todos los listeners del fallback quedan en loopback: APIs, Gateway, frontend,
MongoDB, AMQP, EPMD :14379 y distribución Erlang :25679. No se usan datos,
credenciales, bases, volúmenes o procesos preexistentes de otros proyectos.
Los directorios de estado se crean fuera del repositorio, con permisos privados;
los scripts conservan los datos al detenerse. No se usó Kubernetes en esta etapa.

La prueba de las nueve operaciones atraviesa el cliente HTTP real del proceso
Gateway: demuestra conectividad desde ese proceso a las cuatro APIs, no solo
GET de salud desde el host. La variante Docker **solo se validó sintácticamente**;
no se afirma que sus contenedores o DNS se hayan ejecutado aquí.

## Servicios y versiones comprobadas

Fuente docente inalterada:
[commit d15f2e20ced1007099b90bf59b720e97be3d2d4a](https://github.com/rmasad/microservicios/tree/d15f2e20ced1007099b90bf59b720e97be3d2d4a/03_Comunicaci%C3%B3n/demo).
El archivo `integration/chat/source.lock.json` registra SHA-256 de los tres
main.py, requirements y Dockerfiles. prepare.py y el lanzador verifican esos
hashes. No se versionaron copias del código externo.

| Componente | Versión observada en el fallback |
|---|---|
| MongoDB | 7.0.14, binario oficial Ubuntu 22.04 ejecutado en Ubuntu 24.04 x86_64 |
| RabbitMQ | 3.12.1, paquete Ubuntu extraído en /tmp |
| Erlang/OTP | 25.3.2.8, paquetes Ubuntu extraídos en /tmp |
| Users/Channels/Messages | FastAPI 0.115.12, PyMongo 4.12.1, Uvicorn 0.34.2 |
| Messages AMQP | Pika 1.3.2 |
| Gateway | FastAPI 0.115.12, Ariadne 0.26.2, httpx 0.28.1 |
| Thread Service | Código del merge #6, FastAPI 0.162.2, PyMongo 4.19.0, Pika 1.4.4 |
| Node | 22.23.4 |

Más versiones y hashes de paquetes descargados:
[versions.json](evidencia_chat_integration/versions.json). Los límites de versiones
de las dependencias originales no se cambiaron. Compose propone mongo:7.0.14 y
rabbitmq:4-management; este último coincide con el stack original y CI, pero
**no fue el broker ejecutado en el fallback**.

## Configuración Docker Compose aislada

Archivos nuevos bajo `integration/chat/`; no se modifica integration/compose.yaml
ni los overrides previstos para Andrés. No se usa container_name fijo. Los
volúmenes se prefijan por un proyecto generado y la red compartida conserva el
nombre exacto **microsvcs**. Los aliases chat-it-* están solo en una red privada
por proyecto, para evitar resolver APIs de otro stack conectado a microsvcs.

| Servicio | Puerto interno | Host, loopback por defecto |
|---|---:|---:|
| chat-users | 8000 | 18001 |
| chat-channels | 8000 | 18002 |
| chat-messages | 8000 | 18003 |
| chat-threads | 8000 | 18004 |
| chat-gateway | 5000 | 15000 |
| chat-frontend | 5173 | 15173 |
| MongoDB (cuatro contenedores) | 27017 | No publicado |
| RabbitMQ | 5672 | No publicado |

Los builds de Users/Channels/Messages usan el código docente verificado. Solo
se configura su command de Uvicorn y variables; no hay parches ni monkeypatches.
Threads y worker usan el Dockerfile original, target runtime. Los puertos internos
8000 no se confunden con los publicados 18001–18004 ni con 8004 del stack original.

Variables principales:

- CHAT_BASE_SOURCE: carpeta absoluta del demo docente verificado.
- CHAT_PROJECT_NAME: nombre de proyecto único generado por prepare.py.
- CHAT_RABBIT_USER / CHAT_RABBIT_PASSWORD: usuario local y contraseña aleatoria;
  se escriben en un env privado fuera del repositorio, nunca en un commit.
- CHAT_*_PORT: opcionales, publicados solo en 127.0.0.1.
- Gateway: USERS_BASE_URL=http://chat-it-users:8000,
  CHANNELS_BASE_URL=http://chat-it-channels:8000,
  MESSAGES_BASE_URL=http://chat-it-messages:8000,
  THREADS_BASE_URL=http://chat-it-threads:8000, timeout 2 s.
- Messages: MONGODB_URL, USERS_URL, CHANNELS_URL y RABBITMQ_URL.
- Threads: THREAD_MONGODB_URL, THREAD_MONGODB_DATABASE, THREAD_USERS_URL,
  THREAD_MESSAGES_URL y THREAD_RABBITMQ_URL; worker comparte esa configuración.
- Vite: GATEWAY_PROXY_TARGET=http://chat-it-gateway:5000. El navegador conserva
  /graphql; no recibe URLs REST ni credenciales de mensajería.

### Preparar y arrancar con Docker (cuando esté disponible)

Desde raíz, Python 3.12 y Docker Engine/Compose operativos:

```sh
export CHAT_IT_PARENT="$(mktemp -d /tmp/thread-chat-it.XXXXXX)"
python3 integration/chat/prepare.py --directory "$CHAT_IT_PARENT/assets"
# Crea microsvcs SOLO si no existe; no la elimines al terminar.
docker network inspect microsvcs >/dev/null 2>&1 || docker network create microsvcs

dc() { docker compose --env-file "$CHAT_IT_PARENT/assets/compose.env" -f integration/chat/compose.yaml "$@"; }
dc config --quiet
python3 integration/chat/verify_compose.py --env-file "$CHAT_IT_PARENT/assets/compose.env"
dc up --build -d --wait
```

Abrir http://127.0.0.1:15173. Comprobar acceso **desde el Gateway**:

```sh
dc exec chat-gateway python -c 'import os,urllib.request; names=["USERS","CHANNELS","MESSAGES","THREADS"]; [print(n,urllib.request.urlopen(os.environ[n+"_BASE_URL"]+"/health",timeout=3).status) for n in names]'
```

Para detener exclusivamente este proyecto, conservando datos:

```sh
dc down
```

No usar down -v, volume prune, system prune ni borrar bases o volúmenes. No
imprimir compose.env ni la configuración expandida con contraseñas: utilizar
config --quiet. Cada prepare.py requiere un directorio nuevo y genera un
proyecto distinto; para reabrir el mismo conjunto, conservar su compose.env.
Los errores de creación descritos abajo son propios de la fuente fijada y no
se solucionan por usar Docker.

## Fallback reproducible sin Docker

Esta ruta fue la **ejecutada realmente**. Requiere Linux x86_64 compatible con
MongoDB/Erlang, Node >=22.12 y Python 3.12. Los comandos apt-get download solo
descargan paquetes; no instalan ni ejecutan scripts de instalación del sistema.
Se usaron los índices Ubuntu 24.04 disponibles; los hashes exactos están en la
evidencia de versiones. En otro sistema, usar el Compose o runtimes compatibles.

Primero preparar fuentes y dependencias (desde raíz):

```sh
export CHAT_IT_PARENT="$(mktemp -d /tmp/thread-chat-it.XXXXXX)"
python3 integration/chat/prepare.py --directory "$CHAT_IT_PARENT/assets"
export CHAT_IT_SOURCE="$CHAT_IT_PARENT/assets/source/microservicios-d15f2e20ced1007099b90bf59b720e97be3d2d4a/03_Comunicación/demo"
mkdir -p "$CHAT_IT_PARENT/runtime/debs" "$CHAT_IT_PARENT/runtime/mongo" "$CHAT_IT_PARENT/runtime/rabbit"
python3 -m venv "$CHAT_IT_PARENT/base-python"
"$CHAT_IT_PARENT/base-python/bin/pip" install -r "$CHAT_IT_SOURCE/users/requirements.txt" -r "$CHAT_IT_SOURCE/channels/requirements.txt" -r "$CHAT_IT_SOURCE/messages/requirements.txt"
python3 -m venv "$CHAT_IT_PARENT/thread-python"
"$CHAT_IT_PARENT/thread-python/bin/pip" install -r requirements-dev.txt
python3 -m venv "$CHAT_IT_PARENT/gateway-python"
"$CHAT_IT_PARENT/gateway-python/bin/pip" install -r gateway/requirements-dev.txt
(cd frontend && npm ci)
```

MongoDB oficial, verificando el checksum del artefacto ejecutado:

```sh
curl --fail --location https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-7.0.14.tgz -o "$CHAT_IT_PARENT/runtime/mongo.tgz"
printf '%s  %s\n' b4cf8caae108785135ecc8b86ad8ed6df5d6efb84b9b95a50ecba2fc246ce084 "$CHAT_IT_PARENT/runtime/mongo.tgz" | sha256sum -c -
tar -xzf "$CHAT_IT_PARENT/runtime/mongo.tgz" -C "$CHAT_IT_PARENT/runtime/mongo"
```

RabbitMQ/Erlang extraídos sin instalación global (Ubuntu 24.04):

```sh
(cd "$CHAT_IT_PARENT/runtime/debs" && apt-get download erlang-base erlang-asn1 erlang-crypto erlang-eldap erlang-inets erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key erlang-runtime-tools erlang-ssl erlang-syntax-tools erlang-tools erlang-xmerl erlang-snmp rabbitmq-server)
for package in "$CHAT_IT_PARENT/runtime/debs/"*.deb; do dpkg-deb -x "$package" "$CHAT_IT_PARENT/runtime/rabbit"; done
```

Arrancar en una terminal y conservar las variables de rutas:

```sh
"$CHAT_IT_PARENT/thread-python/bin/python" integration/chat/process_stack.py \
  --source "$CHAT_IT_SOURCE" \
  --mongod "$CHAT_IT_PARENT/runtime/mongo/mongodb-linux-x86_64-ubuntu2204-7.0.14/bin/mongod" \
  --rabbit-runtime "$CHAT_IT_PARENT/runtime/rabbit" \
  --base-python "$CHAT_IT_PARENT/base-python/bin/python" \
  --thread-python "$CHAT_IT_PARENT/thread-python/bin/python" \
  --gateway-python "$CHAT_IT_PARENT/gateway-python/bin/python" \
  --node "$(command -v node)" \
  --state "$CHAT_IT_PARENT/state"
```

El lanzador comprueba puertos y hashes, publica STACK_READY y crea manifest.json
sin contraseñas. Mantiene binarios, credenciales temporales, logs y datos fuera
del repositorio. Ctrl+C detiene solo los procesos creados por él. Para abrir
otra vez **sus propios datos**, repetir el comando con --resume. Un marcador de
propiedad protege frente a reutilizar directorios ajenos y no se borran datos.
En esta sesión se comprobó también un cierre y reanudación completos.

### Probar GraphQL real

En otra terminal, con las mismas variables:

```sh
"$CHAT_IT_PARENT/thread-python/bin/python" integration/chat/probe.py \
  --manifest "$CHAT_IT_PARENT/state/manifest.json" \
  --output "$CHAT_IT_PARENT/state/graphql-report.json" \
  --allow-local-writes --diagnose-upstream --faults-and-restart
```

Este comando **sale con código 1** mientras las creaciones externas respondan
500: no oculta el fallo del E2E. Con --diagnose-upstream continúa tras el primer
error, leyendo únicamente la base privada para recuperar el ID del usuario
real que sí se guardó. Recupera canal y mensaje mediante consultas GraphQL.
Esto es diagnóstico administrativo del fixture, **no una solución en el Gateway**.
Ningún resolver incorpora acceso directo a MongoDB.

El script comprueba las nueve operaciones, campos/IDs/fechas UTC, thread vacío,
respuesta publicada y recuperada, referencias inválidas, autor inválido, contenido
vacío, caída de conexión, timeout real pausando nuestro Users, dependencia 503,
entrega AMQP real y persistencia después de reiniciar MongoDB y las APIs. Los
controles de parada/reinicio solo se aceptan en el directorio privado del lanzador.
No se aplica este comando a servicios reales de terceros o al clúster.

### Recorrido de navegador sin interceptar respuestas

Instalar la herramienta de QA fuera del repositorio:

```sh
npm install --prefix "$CHAT_IT_PARENT/browser" playwright@1.65.0
export PLAYWRIGHT_BROWSERS_PATH="$CHAT_IT_PARENT/browser-cache"
node "$CHAT_IT_PARENT/browser/node_modules/playwright/cli.js" install chromium
node integration/chat/browser_check.cjs \
  "$CHAT_IT_PARENT/state/manifest.json" \
  "$CHAT_IT_PARENT/state/graphql-report.json" \
  "$CHAT_IT_PARENT/state/browser-report.json" \
  "$CHAT_IT_PARENT/state/screenshots" \
  "$CHAT_IT_PARENT/browser/node_modules/playwright"
```

Este script reproduce los **bloqueos conocidos de la fuente fijada**, no
intercepta requests ni simula respuestas. También sale 1 al no aprobar el E2E
estricto; una falla inesperada del propio diagnóstico sale 2. Para una futura
versión corregida del chat base, revisar la referencia fijada y actualizar el
recorrido para exigir creaciones confirmadas, sin conservar expectativas de error.

Pasos observados desde React:

1. Crear usuario: HTTP 500 externo; nombre retenido, sin seleccionar identidad,
   exactamente un POST. El usuario sí queda en la MongoDB real.
2. Continuación diagnóstica con un ID real existente, obtenido por inspección
   de la base privada tras el POST fallido. Selección, cierre, recuperación y
   revalidación tras recarga funcionan. No se inventa el ID ni una respuesta.
3. Crear canal: HTTP 500 externo; actualizar lista recupera el canal real.
   Seleccionarlo abre el canal y consulta su existencia.
4. Enviar mensaje: HTTP 500 externo; borrador retenido. El polling recupera el
   mensaje guardado realmente, con el mismo autor y canal.
5. Abrir Threads, publicar respuesta: éxito confirmado; consultar de nuevo
   devuelve la respuesta del mensaje raíz correcto.
6. Recargar: identidad validada, canal, mensaje y respuesta recuperados del
   backend real. Tras parar nuestro Users, se conserva el ID, se bloquea envío,
   el chat sigue legible y la revalidación permite recuperarse al arrancarlo.
7. Network: solo POST /graphql del mismo origen para los datos; cero llamadas
   REST del navegador a las cuatro APIs, cero errores de página o consola.

## Resultados reales y evidencias

| Operación | Resultado real |
|---|---|
| user | Correcta, ID y nombre del usuario persistido |
| channels | Correcta, arreglos sin envelope |
| channel | Correcta, canal por ID |
| messages | Correcta, mensajes persistidos y fechas UTC |
| replies | Correcta, vacío válido y respuesta posterior |
| createReply | Correcta, respuesta persistida y evento confirmado |
| createUser | **Bloqueada**: HTTP 500 externo después de insertar |
| createChannel | **Bloqueada**: HTTP 500 externo después de insertar |
| sendMessage | **Bloqueada**: HTTP 500 externo después de insertar |

- [Informe GraphQL real](evidencia_chat_integration/graphql-report.json): respuestas
  reales y 15 comprobaciones diagnósticas, incluidas conexión, timeout y AMQP.
- [Informe del navegador](evidencia_chat_integration/browser-report.json): pasos,
  IDs reales de prueba, solicitudes de datos y un solo POST por creación.
- [Prueba después del cierre/reinicio completo](evidencia_chat_integration/persistence-after-restart.json):
  consultas reales de los registros creados desde GraphQL y React, con los mismos
  IDs y relaciones. El evento de la respuesta del navegador siguió en RabbitMQ.
- [Bloqueo de creación de usuario](evidencia_chat_integration/01-bloqueo-users-real.png).
- [Mensaje guardado con error y respuesta confirmada](evidencia_chat_integration/02-chat-error-mensaje-y-respuesta-real.png).
- [Recarga y respuesta real](evidencia_chat_integration/03-recarga-y-respuesta-real.png).
- [Indisponibilidad real de nuestro Users](evidencia_chat_integration/04-users-no-disponible-real.png).

Las capturas de esta carpeta usan servicios reales. Las de evidencia_frontend/
del PR anterior usaban mocks; no deben confundirse. Los IDs son datos ficticios
de prueba generados por las APIs; no hay usuarios o datos del curso. No se
incluyeron credenciales, env privados, dumps MongoDB ni logs completos.

## Problemas encontrados y correcciones

### Bloqueos que requieren coordinación externa

En los tres servicios docentes se ejecuta insert_one(documento) sobre el mismo
dict que después se devuelve o publica. PyMongo agrega `_id: ObjectId(...)`.

- Users/Channels: FastAPI falla al serializar el dict retornado. Logs observados:
  `TypeError: 'ObjectId' object is not iterable` y error de jsonable_encoder.
- Messages: json.dumps(event) falla en publish con
  `TypeError: Object of type ObjectId is not JSON serializable`.
- En los tres casos la inserción ya ocurrió. Repetir POST puede duplicar datos;
  el Gateway no reintenta y React mantiene el aviso de resultado incierto.

Se necesita que el responsable del chat base mantenga `_id` fuera de los DTOs
HTTP y eventos, por ejemplo persistiendo una copia del dict o construyendo
explícitamente el DTO público. La corrección debe cubrir respuesta **y evento**.
**No se aplicó ningún parche al código externo, ni se compensó leyendo MongoDB
desde Gateway.** Hasta tener una revisión corregida, la creación normal desde
la interfaz no puede declararse completada.

### Ajustes propios del entorno de prueba

Se corrigieron problemas del lanzador, no de los servicios:

- Preservar la ruta bin/python del virtualenv; resolver su symlink utilizaba
  el Python del sistema sin sus dependencias. Hay regresión con un venv real.
- Permitir reanudación tras TIME_WAIT con SO_REUSEADDR, manteniendo rechazo de
  listeners activos; ambas situaciones se prueban con sockets propios.
- Reubicar Erlang, cookie/configuración y crash dumps dentro del estado privado;
  usar epmd sin una opción -foreground inexistente en ese paquete y evitar un
  argumento -home duplicado. Se comprobó el arranque/reanudación real final.
- Conservar UTF-8 literal al escribir el env de Compose: los escapes JSON de
  Unicode convertían la ruta Comunicación en un contexto inexistente. Hay
  regresión de acentos/espacios, permisos privados y rechazo de sobrescritura;
  verify_compose.py comprueba los contextos reales sin imprimir secretos.
- Limitar también el puerto de distribución de RabbitMQ a 127.0.0.1; verificado
  con listeners reales. No se modificó la instalación global del sistema.

No se cambió lógica de Gateway, frontend ni Thread Service para acomodar las
fallas externas. Sus pruebas y el snapshot GraphQL siguen intactos.

## Regresión y comprobaciones

| Suite | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Frontend | 48 | 0 | 0 |
| Gateway | 263 | 0 | 0 |
| Thread Service, con MongoDB/RabbitMQ propios reales | 107 | 0 | 0 |
| Kubernetes offline | 20 | 0 | 0 |
| Regresiones del lanzador y preparador | 4 | 0 | 0 |
| **Total de regresión** | **442** | **0** | **0** |

npm ci, TypeScript/build, Compose principal y Compose de Chat, validador estático
Kubernetes y git diff --check correctos. Las seis pruebas antes omitidas se
activaron con las URLs del MongoDB/RabbitMQ privados. No se cambiaron pruebas
antiguas ni sus expectativas. El workflow nuevo Chat integration setup valida
el lanzador, fuentes y sintaxis Compose; **no presenta sus checks como E2E**.

Separadamente, la validación funcional real dio **6 operaciones exitosas y 3
bloqueadas**. Tanto el probe estricto como el recorrido estricto de navegador
salen 1; sus fases diagnósticas completaron las comprobaciones indicadas. No
sumar esas fallas externas como si fueran regresiones unitarias aprobadas.

Comandos de regresión desde raíz (entornos preparados arriba):

```sh
"$CHAT_IT_PARENT/gateway-python/bin/python" -m pytest -c gateway/pytest.ini gateway/tests -q -W error
"$CHAT_IT_PARENT/thread-python/bin/python" -m pytest -q -W error
"$CHAT_IT_PARENT/thread-python/bin/python" -m pytest scripts/test_k8s_rendering.py -q -W error
"$CHAT_IT_PARENT/thread-python/bin/python" -m pytest integration/chat/test_launcher.py -q -W error
"$CHAT_IT_PARENT/thread-python/bin/python" scripts/validate_k8s.py
(cd frontend && npm test && npm run build)
git diff --check
```

La suite original habilita infraestructura mediante THREAD_TEST_MONGODB_URL y
THREAD_TEST_RABBITMQ_URL. Con el fallback propio activo, ejecutar desde raíz:

```sh
"$CHAT_IT_PARENT/thread-python/bin/python" - "$CHAT_IT_PARENT/state" <<'PYTHON'
import json, os, subprocess, sys
from pathlib import Path
from urllib.parse import quote
state = Path(sys.argv[1])
manifest = json.loads((state / 'manifest.json').read_text())
credentials = json.loads((state / 'runtime-credentials.json').read_text())
url = ('amqp://' + quote(credentials['username'], safe='') + ':'
       + quote(credentials['password'], safe='')
       + '@127.0.0.1:' + str(manifest['ports']['rabbitmq']) + '/%2F')
env = dict(os.environ, THREAD_TEST_MONGODB_URL=manifest['mongo_url'],
           THREAD_TEST_RABBITMQ_URL=url)
raise SystemExit(subprocess.run([sys.executable, '-m', 'pytest', '-q', '-W', 'error'], env=env).returncode)
PYTHON
```

La contraseña se lee solo en memoria y se pasa mediante env del proceso, nunca
por argumentos ni salida. Sin esas variables, seis pruebas se omiten como antes.
No usar URLs del clúster.

## Limitaciones y coordinación con Andrés

- E2E normal pendiente de corregir el contrato de creación del chat base y
  repetir las nueve operaciones sin recuperación administrativa del fixture.
- Docker Compose preparado/validado, pero no ejecutado por falta de daemon.
- RabbitMQ del fallback difiere del de Compose; la evidencia identifica ambos.
- No se despliega Kubernetes ni se publican servicios externos. Los datos del
  fallback se conservaron fuera del repositorio; los procesos se detienen al
  cerrar el lanzador, sin eliminar volúmenes o bases.
- Integrales/Polls, su frontend, clientes, resolvers y contrato v1 permanecen
  intactos. No se modifican integration/compose.yaml ni integration/overrides/.
- Andrés puede partir del main con PR #6. Su integración puede usar un override
  propio y la red microsvcs; acordar URLs/aliases si combina varios proyectos,
  evitando nombres genéricos que resuelvan a otro stack. No debe depender de
  que este entorno diagnóstico esté ejecutándose.
- Este nuevo PR se deja abierto para revisión: **no se fusiona automáticamente**.
