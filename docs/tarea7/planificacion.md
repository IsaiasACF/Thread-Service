# Planificación de la Tarea 7: QA de Thread Service

## Objetivo y alcance

Agregar y acreditar pruebas de servicio, contrato e integración para **Threads**, la capacidad de respuestas de un nivel a mensajes del chat. Esta planificación permite trabajar en paralelo a Isaías, integrante A, y a Andrés, integrante B, y reunir después las evidencias de la rúbrica.

Estado: **plan de implementación; las nuevas pruebas y sus resultados están pendientes**. Revisión del 16 de noviembre de 2026 sobre el checkout local `a7626e168f43f40d9723da8cf23aa299aeefc8fe`. No se modifican aquí aplicaciones, contratos ni infraestructura.

El flujo a demostrar es: crear usuarios → crear canal → publicar mensaje raíz → publicar respuesta con Threads → consultar la respuesta y comprobar sus relaciones y persistencia. El frontend, Gateway GraphQL, Integrales, Polls y Kubernetes quedan fuera del entorno mínimo de esta tarea. Las pruebas HTTP operan directamente sobre las APIs REST.

## Fuentes y criterio de adaptación

- [Enunciado y rúbrica de Unidad 7](https://github.com/rmasad/microservicios/blob/main/07_QA/README.md): dos pruebas por endpoint, una negativa; aislamiento de BD; contrato con el chat base; integración Docker Compose.
- [Ejemplo demo_07_chat](https://github.com/rmasad/microservicios/blob/main/07_QA/demo_07_chat/README.md): describe pruebas de notificaciones y del evento `chat.message.created`. En la revisión, esa carpeta contiene únicamente su README; no se atribuyen a ella scripts de pruebas que no están publicados allí.
- Imágenes proporcionadas: reparto A/B de 65/30 puntos, 5 puntos compartidos y dos ramas con PR independientes desde el mismo `main`.
- Código local: [endpoints](../../app/api/replies.py), [aplicación y salud](../../app/main.py), [servicio](../../app/services/thread_service.py), [clientes REST](../../app/integrations/rest.py) y [esquemas](../../app/schemas/reply.py).

Se aplica el enfoque del ejemplo a Threads. **No se implementa Notifications ni se añade un consumidor de `chat.message.created`**: Threads consulta Users y Messages por HTTP y publica `chat.thread.reply.created` mediante outbox y worker.

## Rúbrica y responsables

| Criterio | Puntos | Responsable | Evidencia prevista |
|---|---:|---|---|
| Dos pruebas por endpoint, al menos una negativa | 40 | A: Isaías | Matriz método/ruta → tests concretos y JUnit |
| Aislamiento de BD mediante override o fixture | 25 | A: Isaías | Fixtures nuevas por caso, cierre y limpieza verificables |
| Contrato con el chat base | 20 | B: Andrés | Contratos Users/Messages y pruebas vinculadas al proveedor fijado |
| Integración con Docker Compose | 10 | B: Andrés | Flujo REST completo, comprobación de persistencia y reporte |
| Pruebas legibles y ordenadas | 5 | Ambos | Organización, instrucciones reproducibles y revisión de PR |

La distribución de puntos no representa horas de trabajo: A parte de numerosas pruebas existentes; B debe preparar fuentes externas, verificación de contratos y el entorno Docker.

## Diagnóstico del repositorio

| Elemento existente | Qué aporta | Qué falta acreditar en Tarea 7 |
|---|---|---|
| `tests/test_replies_api.py` | POST/GET válidos, raíz inexistente, autor inexistente, validaciones, errores de dependencias y OpenAPI | Matriz explícita, fixtures comunes y cobertura de salud |
| `tests/test_mongo_replies.py` | Repositorio con `mongomock`, índices, persistencia y outbox | Usar el repositorio real también en las nuevas pruebas HTTP aisladas |
| `tests/test_asgi.py` | Lifespan operativo con Mongo sustituido por `mongomock` | Demostrar independencia entre casos y limpieza del estado |
| `tests/test_core_errors.py` | Traducción de errores de almacenamiento y respuestas HTTP seguras | Revisar fallos sin escrituras adicionales ni eventos nuevos |
| `tests/test_integrations.py` | Clientes reales con `httpx.MockTransport`, rutas y formatos esperados | Vincular expectativas a un proveedor publicado; un mock inventado por el consumidor no demuestra por sí solo compatibilidad |
| `tests/test_mongo_concurrency.py`, `tests/test_delivery_real.py` | Mongo/Rabbit reales opcionales con recursos específicos de prueba | Separarlos del nivel de servicio sin infraestructura y declarar cuándo se omiten |
| `integration/chat/` y `integration/final/` | Descarga verificada, Compose, comprobaciones y diagnóstico de una integración anterior | Reutilizar criterios y utilidades estables sin ejecutar todo Tarea 6 ni modificar el trabajo compartido |
| `.github/workflows/tests.yml` | Suite Python, Mongo/Rabbit de CI y construcción de imagen | Integrar los niveles de Tarea 7 y sus reportes al final |

No se asume que el número de pruebas de Tarea 6 sea el resultado de esta tarea. Los conteos y estados se obtienen al implementar y ejecutar cada suite.

## Organización de Git y propiedad de archivos

Ambos parten del mismo SHA actualizado de `main`, registrado antes de comenzar:

```text
main
 ├─ feature/tarea7-qa-service       → PR de A (Isaías)
 └─ feature/tarea7-qa-integration   → PR de B (Andrés)
                    ↓
             main → QA conjunta
```

| Responsable | Archivos propuestos bajo su propiedad |
|---|---|
| A: Isaías | `tests/test_qa_service.py`, `tests/qa_fixtures.py`, `docs/tarea7/servicio.md` |
| B | `tests/test_qa_contract.py`, `tests/qa_contract_support.py`, `integration/qa/`, `docs/tarea7/contrato-integracion.md` |
| Coordinación | `docs/tarea7/planificacion.md`, README raíz, requisitos, configuración pytest, Dockerfile y workflows |

Los archivos propuestos todavía deben crearse. Cada integrante evita editar las pruebas, fixtures y scripts propios del otro. Las fixtures nuevas se importan o registran explícitamente desde su módulo; no se introduce un `tests/conftest.py` global que cambie suites ajenas accidentalmente.

Cada PR incluye **What**, **Why**, comandos ejecutados, resultados y limitaciones. Los cambios compartidos de dependencias y CI se acuerdan y reúnen al final. Antes de mezclar trabajo, se preservan los cambios locales existentes; no se incluyen carpetas de demostración ni videos ajenos a Tarea 7. No se hace push directo a `main` como parte de esta planificación.

## Trabajo de A (Isaías): pruebas de servicio y aislamiento

### Inventario por método y ruta

| Método y endpoint propio | Éxito mínimo | Error mínimo y comprobaciones adicionales |
|---|---|---|
| `POST /api/v1/channels/{channel_id}/messages/{message_id}/replies` | 201; respuesta normalizada, ID, fecha UTC, relaciones correctas y lectura posterior | 422 por contenido inválido o autor inexistente; 404 por raíz ausente. Respuestas y eventos sin cambios |
| `GET /api/v1/channels/{channel_id}/messages/{message_id}/replies` | 200; lista vacía para raíz existente o lista ordenada con respuestas | 404 por raíz ausente; comprobar que no hay escrituras |
| `GET /health` | 200 y `{"status":"ok"}` | Petición con método no permitido, por ejemplo `POST /health`, devuelve 405; verificar `Allow` incluyendo GET |

**Particularidad de salud:** `/health` es liveness y no consulta Mongo, Users ni Rabbit. El 405 prueba el rechazo de un método inválido en la ruta, no un error de dominio de `GET /health`. A debe dejarlo explícito en la matriz. Si el evaluador exige un error del propio GET, se debe aclarar ese criterio antes del cierre; no se inventa un 503 ni se cambia liveness para aparentar cobertura. Añadir un readiness sería un cambio separado, no una necesidad demostrada por este enunciado.

`/docs`, `/redoc` y `/openapi.json` son rutas automáticas de documentación, no operaciones de negocio a duplicar para esta matriz. No hay autenticación por contraseña en Threads: los casos de error se basan en entradas y referencias reales, sin introducir credenciales ficticias.

### Diseño de fixtures

1. Crear un `mongomock.MongoClient()` por prueba, colección nueva y `MongoReplyRepository` real con sus índices.
2. Construir `ThreadService` con ese repositorio y dobles explícitos de Users/Messages.
3. Inyectarlo con `create_app(service)` o con `dependency_overrides[get_thread_service]`; si se usa override, limpiarlo en `finally`.
4. Abrir y cerrar `TestClient` mediante contexto. Las pruebas de lifespan sustituyen `app.asgi.mongo_client` antes de activar la aplicación operativa.
5. Al terminar, limpiar la colección de prueba, cerrar el cliente y restaurar overrides/parches. No conectar estas fixtures a las URLs Mongo de desarrollo.
6. Verificar que una fixture nueva empieza vacía y que los fallos de validación/referencias no agregan documentos ni outbox. Comparar estado antes/después también cuando ya existan datos.

Casos a auditar antes de agregar tests duplicados: límites de contenido 1/4000 tras trim, autor vacío, tipos inválidos, campos faltantes, canal equivocado, raíz que sea una respuesta, orden estable por fecha/ID, dependencia 502/503, almacenamiento 500/503 y ausencia de campos internos en la respuesta.

Los tests de fallos durante escritura no deben prometer rollback cuando el resultado de la operación sea incierto: distinguir rechazo previo a escribir de un timeout posterior a una posible persistencia. No reintentar POST automáticamente.

Aceptación de A: cada operación tiene casos identificados; las pruebas de servicio corren sin Mongo/Rabbit reales ni acceso de red; ejecutarlas dos veces no comparte datos. Los tests reales opcionales existentes se informan por separado.

## Trabajo de B: contratos con Users y Messages

### Contratos elegidos

El mínimo es un contrato con el chat base; se planifican dos para cubrir las dependencias directas:

| Proveedor e interacción | Contrato consumido | Conducta esperada en el cliente de Threads |
|---|---|---|
| Users: `GET /api/v1/users/{id}` | 200, JSON objeto con `id` string igual al solicitado; 404 para usuario inexistente | `RestUserGateway.exists` devuelve verdadero/falso según corresponda |
| Messages: `GET /api/v1/channels/{channel_id}/messages` | 200, JSON lista con `id` y `channel_id` strings por mensaje | `RestMessageGateway.exists_in_channel` solo acepta raíz y canal coincidentes; lista sin raíz devuelve falso |

El proveedor fijado de Messages devuelve una lista vacía si no hay mensajes, incluso para un canal sin registros: **no se exige un 404 de canal que esa ruta no promete**. El adaptador también tolera 404, pero ese caso se documenta como defensa del consumidor, no como garantía del proveedor.

### Verificación sin levantar el sistema

1. Fijar versión y hashes de las fuentes del chat. Partir del lock existente en `integration/chat/source.lock.json`: commit `d15f2e20ced1007099b90bf59b720e97be3d2d4a`, subdirectorio `03_Comunicación/demo`. Registrar cualquier actualización deliberada y su impacto.
2. Escribir expectativas independientes de las clases de producción: ruta, método, códigos, forma mínima y tipos de los campos consumidos. No exigir igualdad de todos los campos: agregar un campo opcional compatible no debe romper el contrato.
3. Ejecutar los adaptadores REST reales con transporte controlado para capturar las solicitudes y probar aceptación, 404 y rechazo de respuestas malformadas. Conservar los casos útiles existentes, sin copiar toda la suite.
4. Verificar además esas interacciones contra las rutas reales de Users/Messages de la revisión fijada, cargadas aisladamente en proceso. Sustituir el acceso de persistencia por un stub en memoria **antes de importar** sus módulos, que construyen `MongoClient` al importar. Aislar sus nombres de módulo para no colisionar con nuestro paquete `app`.
5. El stub devuelve registros de prueba y lista vacía/ausencia según el caso. La prueba invoca las rutas por `TestClient` o transporte ASGI; no llama Mongo ni consulta una BD ajena. Tampoco levanta Threads, el frontend ni el resto del sistema.
6. Contrastar las respuestas producidas por esas rutas con las expectativas independientes y con la aceptación del consumidor. No usar `create_user`/POST como preparación del contrato GET ni parchear la respuesta HTTP del proveedor para forzar un éxito.
7. Demostrar sensibilidad: una respuesta con ID numérico o sin `channel_id` debe ser rechazada. Una respuesta compatible con campos adicionales debe seguir siendo aceptada.

Esto produce verificación local de un proveedor fijado con persistencia sustituida; **no se presenta como un pacto Pact verificado en el CI del equipo docente**. Pact puede quedar como mejora posterior, no como requisito para esta entrega.

Si las fuentes no están disponibles o sus hashes no coinciden, el comando obligatorio de contratos falla con un diagnóstico. No convertir la ausencia del proveedor en un skip exitoso. Las fuentes se preparan explícitamente fuera del repositorio; no se descargan silenciosamente durante `pytest`.

Un contrato adicional del evento `chat.thread.reply.created` es opcional. No reemplaza los contratos con Users/Messages: comprobar solo nuestro propio esquema no demuestra compatibilidad con el chat base.

## Trabajo de B: integración real con Docker Compose

### Entorno y archivos previstos

Crear `integration/qa/` con `compose.yaml`, un preparador/lanzador `run.py`, `test_flow.py`, un lock de fuentes y un README de ejecución. El diseño puede reutilizar funciones verificadas de `integration/chat/`, sin editar su Compose ni sus pruebas.

| Contenedor | Función |
|---|---|
| `qa-users`, `qa-channels`, `qa-messages` | Servicios reales del chat base, desde fuentes verificadas |
| `qa-threads` | Imagen operativa de este repositorio, `app.asgi:app` |
| `qa-worker` | Publicación del outbox de Threads |
| Mongo de Users, Channels, Messages y Threads | Datos independientes, propiedad del proyecto QA |
| `qa-rabbitmq` | Broker propio para Messages y worker |
| `qa-tests` | Runner HTTP con pytest; devuelve fallo si falla el flujo |

Usar proyecto Compose exclusivo `tarea7-qa-<ejecucion>` y volúmenes dedicados. No reutilizar los contenedores `thread-b-*` ni los datos de Tarea 6. Mantener la red compartida llamada **`microsvcs`** y agregar una red privada del proyecto para dependencias internas, con aliases específicos de QA para evitar resolver servicios ajenos.

Crear `microsvcs` solo si no existe; no eliminarla al terminar porque es compartida. Evitar `container_name`, puertos fijos innecesarios y credenciales de clúster. Los tests pueden ejecutarse dentro de Compose sin publicar las APIs al host. Generar credenciales locales de prueba y excluir el archivo privado de Git.

Los healthchecks comprueban APIs, Mongo y Rabbit; la preparación del flujo espera disponibilidad con plazo máximo. El orden de arranque por sí solo no garantiza disponibilidad. No usar pausas fijas largas como única sincronización.

### Dependencia externa conocida

Las copias docentes fijadas usan `insert_one(documento)` y devuelven ese mismo diccionario. PyMongo añade `_id`, que puede romper la serialización HTTP del POST aunque la escritura ocurra. La integración anterior ya incluye un parche de pruebas explícito: insertar `documento.copy()` en Users, Channels y Messages.

Antes de implementar, comprobar si una revisión más reciente compatible resuelve el problema. Si se conserva la revisión fijada, reutilizar el parche mínimo de `integration/chat/apply_test_patch.py` en **copias privadas de prueba**, registrando hashes originales, hashes corregidos y diff. No alterar contratos, leer Mongo para recuperar IDs ni reportar un 500 como creación correcta. El modo original sirve como diagnóstico separado y no acredita la integración positiva.

Las evidencias deben indicar si se ejecutó contra fuente original o copia corregida. Este punto se resuelve y documenta al preparar fuentes, antes de afirmar que el flujo funciona sin intervención.

### Flujo obligatorio y aserciones

1. Crear Andrés e Isaías con `POST /api/v1/users` y `display_name`; exigir 201 y tomar IDs de las respuestas.
2. Crear `Grupo de estudio` con `POST /api/v1/channels`; exigir 201 y guardar su ID.
3. Crear el mensaje raíz con `POST /api/v1/channels/{channel_id}/messages`, `author_id` de Andrés y contenido natural; exigir 201 y guardar el ID.
4. Consultar Users y Messages por HTTP para confirmar las referencias utilizadas por Threads.
5. Publicar respuesta de Isaías por `POST /api/v1/channels/{channel_id}/messages/{message_id}/replies`; exigir 201, ID no vacío, fecha válida y coincidencia de autor, canal, raíz y contenido.
6. Consultar GET de replies con una nueva solicitud y comprobar que contiene exactamente esa respuesta una vez. Consultar Messages y comprobar que la respuesta no se convirtió en un mensaje raíz.
7. Reiniciar únicamente `qa-threads`, esperar salud y volver a consultar por HTTP: mismo ID, contenido y relaciones. Esto demuestra persistencia fuera de la memoria del proceso.
8. Intentar respuesta con autor inexistente: 422; raíz inexistente o raíz de otro canal: 404. Usar otro canal real para el caso de canal equivocado. Confirmar por GET que los errores no agregaron respuestas.
9. Guardar reporte de cada paso y finalizar con código distinto de cero ante discrepancias, timeout o servicio no disponible. No repetir POST si su resultado es incierto.

Como ampliación, comprobar el evento publicado con una cola temporal enlazada **antes** del POST y correlación por ID de respuesta. Esperar con timeout, validar tipo y datos y tolerar posibles redeliveries por semántica al menos una vez. La prueba no debe exigir entrega exactamente una vez ni consumir una cola de otro entorno. Esta ampliación no bloquea el flujo REST mínimo.

### Limpieza y repetibilidad

El lanzador registra el proyecto que crea y verifica su propiedad antes de detenerlo o limpiar volúmenes. Recoge reportes y logs sanitizados antes de limpiar. Se eliminan únicamente los recursos desechables de esa ejecución; no usar `prune`, borrado global ni `down -v` sobre proyectos existentes.

Ejecutar el flujo dos veces en entornos nuevos y conservar ambos resultados. La evidencia de persistencia es HTTP tras reinicio; no se accede a las bases de Users/Channels/Messages administrativamente.

## Secuencia de implementación y dependencias

| Paso | Responsable | Trabajo | Condición de salida |
|---|---|---|---|
| 1 | Ambos | Actualizar y registrar el mismo main; auditar rutas, tests y reparto de archivos | Matriz acordada y ramas independientes |
| 2A | A: Isaías | Crear fixtures y completar casos HTTP/repo que falten | Suite de servicio aislada y repetible |
| 2B | B | Preparar fuentes, fijar contrato y escribir verificación consumidor/proveedor | Contratos pasan sin Docker, red ni BD real durante pytest |
| 3B | B | Resolver fuente original/corregida y construir Compose QA | Configuración validada y servicios disponibles |
| 4B | B | Automatizar flujo HTTP y reinicio de Threads | Flujo positivo y negativo con reporte verificable |
| 5 | Cada integrante | Documentar y abrir su PR con What/Why | Checks y evidencias asociados al SHA del PR |
| 6 | Ambos | Integrar PR, resolver archivos compartidos y ejecutar QA final | Reportes nuevos sobre el mismo main integrado |

La integración Docker no depende de que A termine sus fixtures. B no importa fixtures de servicio de A para ejecutar proveedores reales. La CI compartida se ajusta después de estabilizar los comandos de cada nivel.

## Interfaz de ejecución prevista

Los siguientes comandos son **objetivos del diseño**, no comandos ya implementados. `python` representa el intérprete del entorno virtual (usar `python3` donde corresponda). La preparación de fuentes debe funcionar sin modificar archivos docentes en este repositorio.

```sh
# Dependencias del proyecto y descubrimiento de pruebas existentes
python -m pip install -r requirements-dev.txt
python -m pytest --collect-only -q tests

# A: suite aislada, sin variables de acceso a infraestructura real
python -m pytest -q -W error tests/test_qa_service.py --junitxml=docs/tarea7/evidencias/servicio.xml

# B: preparar fuentes verificadas fuera del repositorio y ejecutar contratos
python integration/qa/run.py prepare --directory <DIRECTORIO_QA_EXTERNO>
python integration/qa/run.py contract --directory <DIRECTORIO_QA_EXTERNO>

# B: construir, arrancar, probar, reiniciar Threads y recoger resultados
python integration/qa/run.py integration --directory <DIRECTORIO_QA_EXTERNO>

# Limpiar exclusivamente el proyecto creado por el lanzador
python integration/qa/run.py cleanup --directory <DIRECTORIO_QA_EXTERNO>
```

El comando de contratos debe invocar `tests/test_qa_contract.py` con la ruta de proveedor explícita. El comando de integración debe recoger el código de salida de `qa-tests`, manejar el reinicio desde el host sin montar el socket Docker en el runner, y garantizar limpieza incluso ante fallo.

Al cierre, ejecutar también la suite existente. Las pruebas Mongo/Rabbit reales opcionales se ejecutan en infraestructura QA dedicada con `THREAD_TEST_MONGODB_URL` y `THREAD_TEST_RABBITMQ_URL`; no heredar URLs personales ni afirmar que los skips equivalen a pruebas aprobadas. Cualquier dependencia o cambio de imagen necesario para los nuevos runners se registra en el PR correspondiente.

## Evidencias y criterios de entrega

Guardar resultados en `docs/tarea7/evidencias/`, con fecha, SHA del proyecto, revisión del proveedor, modo de fuentes y comandos. Versionar reportes pequeños sanitizados; excluir dumps, fuentes descargadas, credenciales y salidas voluminosas.

| Archivo propuesto | Contenido |
|---|---|
| `matriz-endpoints.md` | Método/ruta, prueba positiva, negativa, fixture y resultado; nota de salud |
| `servicio.xml`, `contrato.xml`, `integracion.xml` | Reportes JUnit por nivel, sin ocultar fallos ni skips |
| `integracion.json` | IDs devueltos por API, pasos, estados HTTP y lecturas antes/después del reinicio |
| `fuentes.json` | SHA y hashes, modo original/corregido y parche aplicado si corresponde |
| `resumen.md` | Comandos finales, conteos, omisiones, limitaciones y enlace a cada PR |

Lista de aceptación conjunta:

- [ ] Cada operación propia está inventariada; positivos y negativos identificados, incluido el tratamiento explícito de salud.
- [ ] Las pruebas de servicio tienen una BD de prueba nueva por caso y no abren infraestructura real.
- [ ] Usuarios o raíces inválidos no crean respuestas ni eventos nuevos.
- [ ] Al menos un contrato comprueba una interacción con el chat base y tiene trazabilidad a su proveedor; se entregan preferentemente Users y Messages.
- [ ] Los contratos no levantan el sistema ni acceden a una base ajena y detectan respuestas incompatibles.
- [ ] Compose ejecuta Users, Channels, Messages y Threads reales con recursos exclusivos de QA y red `microsvcs`.
- [ ] El flujo crea y consulta la respuesta con IDs obtenidos por API; sobrevive al reinicio de Threads.
- [ ] El problema conocido del proveedor y cualquier copia corregida quedan visibles en las evidencias.
- [ ] Dos ejecuciones independientes pasan y la limpieza no afecta otros proyectos.
- [ ] Ambos PR se revisan y la QA final se repite sobre el SHA integrado, con documentación y comandos consistentes.

## Primer paso para Andrés

Comenzar por `feature/tarea7-qa-integration`: preparar las fuentes fijadas, definir las expectativas GET de Users/Messages y construir la primera prueba de contrato verificable. Después preparar `integration/qa/` y automatizar el flujo REST. La implementación de los casos de servicio y sus fixtures corresponde a A; no es necesario esperar su PR para avanzar en contrato e integración.
