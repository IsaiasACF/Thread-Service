# Tarea 7 — Pruebas de servicio y aislamiento de BD (Integrante A)

## Auditoría inicial (antes de implementar)

Base: `main` en `3b9a16b`; árbol limpio, `fetch` y `pull --ff-only` realizados.
El merge `d85a0e2` del PR #10 es ancestro de esta base. Rama de trabajo:
`feature/tarea7-qa-service`.

Fuentes revisadas: [enunciado y rúbrica oficiales](https://github.com/rmasad/microservicios/blob/main/07_QA/README.md)
y [ejemplo docente](https://github.com/rmasad/microservicios/blob/main/07_QA/demo_07_chat/README.md).
El directorio del ejemplo publicado contiene un README descriptivo, sin código de pruebas.
La rúbrica exige dos pruebas por endpoint, una de error (40), aislamiento de BD (25),
contrato (20), integración Compose (10) y legibilidad (5).

En la tabla, “existente” significa cobertura encontrada por inspección; los resultados
de ejecución se registran por separado más abajo. Las rutas de negocio son las dos
operaciones sobre replies y `/health`; `/docs`, `/redoc` y `/openapi.json` son rutas
automáticas de documentación.

| Endpoint | Caso exitoso | Caso de error | Aislamiento utilizado | Estado |
|---|---|---|---|---|
| POST `/api/v1/channels/{channel_id}/messages/{message_id}/replies` | 201, campos y evento: `test_replies_api.py::test_create_reply_and_retrieve_it`; persistencia operativa: `test_asgi.py::test_operational_lifespan_wires_service_indexes_and_closes` | 404 raíz, 422 autor/entrada, 502/503 gateways; validación sin escrituras | Fakes nuevos por cliente; lifespan con MongoClient sustituido por mongomock | Existente; reforzar fixture, limpieza y evidencia de outbox en BD aislada |
| GET `/api/v1/channels/{channel_id}/messages/{message_id}/replies` | Respuesta creada y lista vacía: `test_create_reply_and_retrieve_it`, `test_get_empty_thread` | `test_cannot_list_missing_root` (404), `test_gateway_error_contract` (502/503 Messages) | Fakes; mongomock para repositorio | Existente; falta comprobar orden desde HTTP con persistencia real del servicio |
| GET `/health` | `test_app_without_injected_adapters_is_docs_only`: JSON ok, sin comprobar status explícito | No hay caso de método incorrecto | Factory sin adaptadores | Completar 200, 405 y evidencia de liveness |

### Suite reutilizada sin modificaciones

- `tests/test_replies_api.py`: TestClient, repositorio/Users/Messages fake; validaciones
  parametrizadas, campos faltantes, límites, errores y ausencia de filas/eventos.
- `tests/test_asgi.py`: TestClient con lifespan operativo, mongomock y gateways mock;
  inserción, lectura, índices y retiro del servicio al cerrar.
- `tests/test_thread_service.py`: reglas de servicio con mocks de puertos, referencias
  antes de persistir y evento correspondiente a la respuesta.
- `tests/test_mongo_replies.py`: repositorio real del proyecto con mongomock; orden,
  separación de threads, outbox, índices, duplicados, leases y fencing.
- `tests/test_core_errors.py`: colección mock; traducción de fallos de driver a HTTP,
  cursor diferido, no filtración de detalles y un solo insert para respuesta/evento.
- `tests/test_integrations.py`: adaptadores REST reales con `httpx.MockTransport`,
  publicación RabbitMQ mock y recuperación del worker. No levanta servicios reales.
  Se reutiliza en regresión; no se añaden contratos del integrante B.
- `tests/test_mongo_concurrency.py`: cinco pruebas opt-in con MongoDB real y
  colecciones UUID, borradas al terminar; requieren infraestructura independiente.
- `tests/test_delivery_real.py`: una prueba opt-in con MongoDB y RabbitMQ reales;
  colección, exchange y cola propios. No equivale a mongomock.

No se requiere cambiar arquitectura, rutas, esquemas ni código de producción.

## A. Cobertura por endpoint

`R` = `/api/v1/channels/{channel_id}/messages/{message_id}/replies`.
Cada referencia siguiente identifica archivo y función; los parámetros generan
casos independientes de pytest.

| Ruta | Método | Test exitoso | Test de error | Resultado esperado |
|---|---|---|---|---|
| R | POST | `tests/test_qa_service.py::test_post_persists_exactly_one_reply_and_matching_outbox` | `tests/test_qa_service.py::test_reference_errors_leave_isolated_reply_and_outbox_empty[root-404-Root message not found in channel]` | 201 con campos normalizados, una respuesta y evento correspondiente; 404 sin respuesta ni outbox |
| R | POST | El mismo test exitoso | `tests/test_qa_service.py::test_reference_errors_leave_isolated_reply_and_outbox_empty` (parámetro `author`) | 422 `Author does not exist`, sin respuesta ni outbox |
| R | POST | El mismo test exitoso | `tests/test_replies_api.py::test_invalid_input_never_writes`, `test_missing_fields` | 422 para vacío/blancos, >4000 caracteres, tipos inválidos, autor inválido y campos faltantes; cero filas/eventos |
| R | POST | El mismo test exitoso | `tests/test_qa_service.py::test_validation_error_leaves_isolated_reply_and_outbox_empty` | 422 para content numérico; almacenamiento mongomock y outbox vacíos; sin invocar gateways |
| R | POST | El mismo test exitoso | `tests/test_replies_api.py::test_gateway_error_contract` | 503 indisponibilidad y 502 respuesta incorrecta de Users o Messages; cuerpo exacto y cero filas/eventos |
| R | GET | `tests/test_qa_service.py::test_post_persists_exactly_one_reply_and_matching_outbox` | `tests/test_replies_api.py::test_cannot_list_missing_root` | 200 y lista con la respuesta completa; 404 si raíz inexistente |
| R | GET | `tests/test_qa_service.py::test_get_returns_chronological_data_and_only_requested_thread` | `tests/test_replies_api.py::test_gateway_error_contract` (parámetro `messages`) | 200 en orden fecha/id, conserva todos los campos y excluye otro canal/mensaje; 503/502 con cuerpo exacto ante Messages indisponible/inválido |
| R | GET | `tests/test_qa_service.py::test_new_fixture_starts_with_empty_thread_and_no_outbox` | Los errores GET anteriores | 200 `[]` para mensaje válido sin respuestas; sin eventos pendientes |
| `/health` | GET (éxito), POST (acceso erróneo) | `tests/test_qa_service.py::test_health_is_liveness_without_storage_or_gateway_checks` | `tests/test_qa_service.py::test_health_rejects_post_with_method_not_allowed` | GET 200 `{"status":"ok"}`; POST 405 `{"detail":"Method Not Allowed"}` y Allow incluye GET |

Así se cumple el mínimo de dos casos por endpoint, incluido uno de error. El 405 de
`/health` verifica acceso con método incorrecto; no simula un fallo de salud inexistente.

### Qué se agregó y por qué

Solo `tests/test_qa_service.py`: siete funciones / ocho casos por la parametrización
de referencias. Se refuerzan persistencia HTTP/outbox, ausencia de escrituras ante
referencias o validación inválidas, orden y filtrado desde GET, estado inicial vacío
y los dos casos de `/health`. Las pocas repeticiones respecto de los fakes existentes
aportan evidencia sobre el repositorio Mongo del proyecto dentro del lifespan.
Se reutilizan los parámetros exhaustivos de validación y 502/503 existentes.
No se agrega otra implementación de repositorio ni otra arquitectura de testing.

## B. Aislamiento de base de datos

La fixture `isolated_service` tiene ámbito `function`. Crea un nuevo
`mongomock.MongoClient()` por caso y una aplicación nueva con
`create_app(lifespan=asgi.lifespan)`. Reutiliza el mismo punto de sustitución de
`tests/test_asgi.py`: `monkeypatch` reemplaza `app.asgi.mongo_client` antes del
arranque de TestClient. El `repository(...)`, los índices, `ThreadService`, las
rutas, el manejo de errores y Pydantic son los del servicio.

No es necesario introducir un override adicional: la fixture cumple la alternativa
de creación y destrucción de almacenamiento de prueba exigida por la rúbrica.
El nombre `qa_service.replies` es fijo pero el cliente en memoria es distinto por
caso, por lo que no comparte datos. Se reemplaza también `get_settings` con ajustes
explícitos: no se usa el cache de configuración ni las URLs de producción/Compose.
La fábrica de MongoDB real en `app.runtime.MongoClient` queda protegida con un mock
que falla si se intenta construirla.

Users y Messages son mocks nuevos de sus puertos por caso; sus constructores se
reemplazan antes del lifespan. Se configuran resultados o errores sin HTTP externo.
El lifespan abre/cierra sus clientes HTTP, pero los gateways sustituidos no envían
solicitudes. TestClient transporta las peticiones directamente hacia ASGI. No se
inicia worker, conexión RabbitMQ ni contenedor.

Antes de cada test se comprueba que la colección esté vacía. Al terminar, incluso
si falla una aserción o el arranque, `finally` elimina la BD en memoria y cierra el
cliente. El contexto de TestClient ejecuta el cierre del lifespan y sus clientes;
se verifica `application.state.thread_service is None`. Pytest restaura todos los
parches al finalizar el caso. Respuesta y `_outbox` están en el mismo documento,
de modo que la limpieza incluye ambos.

Evidencia concreta de independencia:

- `test_post_persists_exactly_one_reply_and_matching_outbox` parte vacío, escribe
  exactamente un documento y verifica el evento embebido completo, pendiente y con
  cero intentos. Recupera la misma respuesta por GET sin campos privados.
- `test_new_fixture_starts_with_empty_thread_and_no_outbox` obtiene `[]`, cero
  documentos y ningún evento reclamable. No presupone que otro test haya corrido.
- Ambos pasan dentro de la suite (escritura antes de almacenamiento vacío), solos
  en procesos independientes y juntos en el orden inverso. Una fixture que
  conservara el documento entre casos fallaría al comprobar la colección inicial.

`/health` es liveness: se comprueba que devuelve ok sin ejecutar operaciones de
repositorio, comando de BD ni consultas de gateways, usando mocks que fallarían si
se invocaran. Esto no promete readiness, conectividad MongoDB ni disponibilidad
de dependencias. El arranque operativo puede necesitar Mongo para crear índices;
la respuesta del endpoint por sí sola no diagnostica esa conectividad.

## C. Ejecución reproducible

Desde la raíz de Thread-Service, PowerShell, Python 3.12 o superior:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

# Solo pruebas nuevas, sin infraestructura externa.
python -m pytest tests/test_qa_service.py -q -W error

# Toda la suite de Thread Service; pytest.ini limita el descubrimiento a tests/.
python -m pytest -q -W error -ra

# Persistencia/outbox, incluyendo casos opt-in reales cuando estén configurados.
python -m pytest tests/test_mongo_replies.py tests/test_core_errors.py tests/test_integrations.py tests/test_mongo_concurrency.py tests/test_delivery_real.py -q -W error -ra

# Evidencia individual y en orden inverso.
python -m pytest tests/test_qa_service.py::test_new_fixture_starts_with_empty_thread_and_no_outbox -q -W error
python -m pytest tests/test_qa_service.py::test_post_persists_exactly_one_reply_and_matching_outbox -q -W error
python -m pytest tests/test_qa_service.py::test_new_fixture_starts_with_empty_thread_and_no_outbox tests/test_qa_service.py::test_post_persists_exactly_one_reply_and_matching_outbox -q -W error

# Estilo (Ruff es una herramienta local opcional; no cambia requirements).
python -m pip install ruff==0.17.5
python -m ruff check tests/test_qa_service.py
python -m pip check
git diff --check
```

Sin `THREAD_TEST_MONGODB_URL` y `THREAD_TEST_RABBITMQ_URL`, los seis casos de
infraestructura real se omiten explícitamente. Para ejecutarlos, configurar esas
variables con URLs de **instancias de prueba propias e independientes**, nunca del
Compose principal ni de producción. Después:

```powershell
# Requiere THREAD_TEST_MONGODB_URL; crea/borra colecciones UUID en thread_core_tests.
python -m pytest tests/test_mongo_concurrency.py -q -W error -ra
# Requiere ambas URLs; crea/borra también exchange/cola propios con sufijo UUID.
python -m pytest tests/test_delivery_real.py -q -W error -ra
```

Una URL configurada con un servicio roto produce fallo, no skip. Aquí no se
configuraron esas variables ni se intervino infraestructura ajena.

## D. Resultados observados

Fecha local: 16 de noviembre de 2026. Windows, PowerShell, Python 3.13.2, entorno
virtual `.venv`; pytest 9.2.0, FastAPI 0.163.1, Starlette 1.10.0, Pydantic 2.14.3,
PyMongo 4.20.0, mongomock 4.3.0, httpx 0.28.1 y httpx2 2.16.2.
Dependencias instaladas desde `requirements-dev.txt`; `pip check` correcto.

| Ejecución local | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Nuevas (`tests/test_qa_service.py`) | 8 | 0 | 0 |
| Suite completa `pytest -q -W error -ra`, incluye las nuevas | 109 | 0 | 6 |
| Selección MongoDB/outbox de C, con `-p no:cacheprovider` | 62 | 0 | 6 |
| Caso de almacenamiento vacío, solo | 1 | 0 | 0 |
| Caso de escritura, solo | 1 | 0 | 0 |
| Vacío y escritura, orden inverso | 2 | 0 | 0 |

Las filas se superponen y no deben sumarse. La suite completa incluye los tests
existentes de rutas, servicio, lifespan, persistencia, outbox, adaptadores y errores.
Los cinco casos MongoDB real y el caso MongoDB + RabbitMQ real se omitieron por
ausencia de URLs de infraestructura propia. Docker CLI está instalado, pero no
hay daemon disponible en el endpoint predeterminado. **No se ejecutó integración
real local ni se presenta mongomock como sustituto de esa evidencia.**

Ruff y `git diff --check` correctos. El ajuste de estilo se limitó a imports y al
alias `UTC`; se repitió la regresión completa después: 109 passed, 6 skipped.
Una ejecución de la selección MongoDB/outbox terminó con error de permisos Windows
al escribir `.pytest_cache` durante el cierre de pytest. No se cuenta esa ejecución
como aprobada. Se repitió con `-p no:cacheprovider`: 62 passed, 6 skipped, código de
salida 0. Desactivar el caché local no modifica pruebas, expectativas ni tratamiento
de warnings. Puede usarse esa opción si se reproduce el problema de permisos.

### Compatibilidad con CI

`.github/workflows/tests.yml` y `.github/workflows/container.yml` se disparan para
`pull_request`, instalan `requirements-dev.txt` y ejecutan `pytest -q -W error`.
`pytest.ini` descubre `tests/test_qa_service.py` automáticamente. Los workflows ya
incluyen mongomock y crean MongoDB/RabbitMQ efímeros para los seis casos opt-in.
Los casos nuevos siguen aislados aunque CI configure URLs de MongoDB real.
No se modificó CI ni se añadió un workflow redundante.

Evidencia remota sobre el commit de implementación `ed6359e` del
[PR #11](https://github.com/IsaiasACF/Thread-Service/pull/11):

| Ejecución CI | Aprobadas | Fallidas | Omitidas | Entorno |
|---|---:|---:|---:|---|
| [Thread service tests #38](https://github.com/IsaiasACF/Thread-Service/actions/runs/43945650301) | 115 | 0 | 0 | Ubuntu, CPython 3.12.16, MongoDB 7 y RabbitMQ 4 efímeros del job |

El log registra `115 passed in 1.81s`. Incluye los 109 casos locales y los seis
casos reales antes omitidos: cinco de MongoDB y uno de MongoDB + RabbitMQ.
Los ocho casos nuevos siguen usando mongomock; su éxito no se confunde con esos
seis casos de infraestructura real. También pasaron validación Compose y build
runtime en el mismo job. El workflow
[Tarea 6 scaffold #20](https://github.com/IsaiasACF/Thread-Service/actions/runs/43945650182)
terminó correctamente para Gateway y frontend. Esta evidencia corresponde al
commit indicado; la actualización documental posterior vuelve a disparar CI.

## E. Rúbrica, alcance y limitaciones

| Criterio oficial | Puntos | Evidencia / alcance |
|---|---:|---|
| Dos pruebas por endpoint, al menos un error | 40 | Cubierto por tabla A: POST 201/404/422/502/503, GET 200/404/502/503, health 200/405 |
| Aislamiento de BD mediante override o fixture | 25 | Cubierto por fixture function, nuevo MongoClient mongomock, limpieza finally, gateways controlados y casos de independencia |
| Prueba de contrato con chat base | 20 | Responsabilidad de Andrés; sin cambios ni afirmación de cumplimiento por este PR |
| Integración con Docker Compose | 10 | Responsabilidad de Andrés; sin cambios ni afirmación de cumplimiento por este PR |
| Pruebas legibles y ordenadas | 5 | Nombres descriptivos, preparación independiente, casos concretos y Ruff correcto; evaluación final docente |

Los **65 puntos a cargo del integrante A** tienen evidencia automatizada. La
asignación definitiva de puntaje corresponde al docente. Las nuevas pruebas usan
gateways controlados y no verifican los contratos reales de Users/Messages, la
entrega real al broker ni concurrencia real de MongoDB; permanecen disponibles las
pruebas existentes opt-in y la infraestructura efímera de CI.

Solo se agregan `tests/test_qa_service.py` y este documento. No se modifican tests
existentes, código de producción, contratos, Compose, `integration/final/`, Gateway,
React, servicios externos ni Kubernetes. No había modificaciones locales previas;
al revisar GitHub no había PRs abiertos. El aislamiento por archivos evita solapar
este cambio con las tareas de Andrés; no permite garantizar cambios futuros aún
no publicados. No se detectó un defecto de producción que requiriera corrección.
El PR debe permanecer abierto, sin merge.
