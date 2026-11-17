# Contenido demostrado en el video de Tarea 7

El video presenta las pruebas de calidad de Thread Service, la capacidad que agrega respuestas de un nivel a los mensajes del chat. Muestra comandos ejecutados y sus resultados reales, con encabezados neutrales y sin narración.

El código corresponde a la revisión integrada `7131caf19c963b062e5330966bad31e9ef2b956c`. La grabación utiliza un proyecto Docker QA nuevo y conserva sus resultados para comprobar el flujo y la persistencia.

## Archivo y duración

El archivo local es `artifacts/video-demo/tarea7-neutral/tarea7-qa-neutral.mp4` y dura aproximadamente **2:05**. La resolución es de 1440 × 900 píxeles. Los tiempos corresponden al MP4 editado y el corte de espera de Docker se identifica en pantalla.

## Recorrido del video

| Tiempo aproximado | Bloque demostrado |
|---|---|
| 0:00–0:09 | Aislamiento · fixture del servicio |
| 0:09–0:22 | Servicio · POST 201 / 404 / 422 · GET · Salud 200 / 405 |
| 0:22–0:30 | Contratos · rutas originales de Users y Messages |
| 0:30–0:37 | Verificación de fuentes · archivos y hashes del proveedor |
| 0:37–0:43 | Docker Compose · arranque de instancias QA independientes |
| 0:43–1:28 | Integración real · espera de arranque recortada |
| 1:28–1:39 | Persistencia · la misma respuesta después de reiniciar Threads |
| 1:39–1:48 | Reinicio real · identidad y relaciones conservadas |
| 1:48–2:05 | Suite conjunta · servicio y contratos |

## 1. Alcance de la demostración

El recorrido agrupa cuatro comprobaciones de la capacidad de respuestas.

- Pruebas HTTP de servicio para creación, consulta y salud.
- Aislamiento del almacenamiento entre casos.
- Contratos con Users y Messages.
- Integración Docker desde la creación de usuarios hasta la lectura de una respuesta después del reinicio.

## 2. Aislamiento de datos

Se muestra un fragmento de la fixture real `isolated_service` de `tests/test_qa_service.py`.

La fixture crea un cliente `mongomock.MongoClient()` por caso, configura el repositorio y sustituye los gateways de Users y Messages antes de activar el lifespan. También protege la construcción de MongoDB real con un mock que falla si se invoca.

El fragmento muestra la colección inicialmente vacía, la aplicación ejecutada mediante `TestClient`, el cierre del lifespan y la limpieza de la base de prueba con `drop_database` y `close` dentro de `finally`.

## 3. Pruebas de servicio

Se ejecuta la suite nueva de servicio con salida detallada.

```sh
python -m pytest -v -W error tests/test_qa_service.py
```

| Comprobación | Resultado verificado por las aserciones |
|---|---|
| POST válido | HTTP 201, contenido normalizado, relaciones correctas y una respuesta persistida |
| Outbox | Evento embebido correspondiente al reply, pendiente de publicación y con cero intentos |
| Lectura posterior | GET devuelve la misma respuesta completa |
| Raíz inexistente | HTTP 404, almacenamiento y outbox vacíos |
| Autor inexistente | HTTP 422, almacenamiento y outbox vacíos |
| Tipo de contenido inválido | HTTP 422 antes de consultar gateways o escribir |
| Fixture nueva | GET devuelve lista vacía y no hay eventos reclamables |
| Orden y pertenencia | GET ordena por fecha e ID y excluye otros canales o mensajes raíz |
| Salud | GET `/health` devuelve 200 sin consultar las dependencias |
| Método incorrecto en salud | POST `/health` devuelve 405 y `Allow` incluye GET |

La salida muestra **8 casos aprobados**. Algunos casos reúnen varias de las comprobaciones de la tabla. El 405 corresponde al rechazo de un método incorrecto en la ruta de salud.

## 4. Contratos con el chat base

Se ejecutan las pruebas de contrato con las fuentes originales verificadas configuradas en `THREAD_QA_SOURCE`.

```sh
python -m pytest -v -W error tests/test_qa_contract.py
```

Las rutas originales de los proveedores se cargan en proceso con persistencia sustituida. Las respuestas de esas rutas se entregan a los adaptadores REST reales de Threads.

| Contrato | Comprobación |
|---|---|
| Users | GET correcto, usuario válido con ID string coincidente y usuario inexistente con 404 |
| Messages | Lista con IDs y canales string, pertenencia de la raíz al canal y ausencia de referencias |
| Compatibilidad | Campos adicionales en respuestas válidas aceptados por el consumidor |
| Users incompatible | ID numérico o ausente rechazado |
| Messages incompatible | `channel_id` ausente o ID numérico rechazado |

La salida muestra **6 casos aprobados**. Los casos de respuestas incompatibles aprueban cuando detectan y rechazan el formato inválido esperado.

## 5. Verificación de fuentes de prueba

Se ejecuta el verificador propio de las copias QA.

```sh
python -m pytest -v -W error integration/qa/test_sources.py
```

La salida muestra **4 casos aprobados**. Se acepta una copia cuyo contenido y metadatos coinciden con el parche documentado. Se rechazan un archivo adicional, código modificado fuera del parche y metadatos alterados.

Las fuentes se fijan mediante el lock existente del repositorio. Los contratos usan las rutas originales. La integración Docker usa copias privadas con `insert_one(documento.copy())` para evitar que `_id`, agregado por PyMongo, rompa la serialización de las respuestas de creación.

## 6. Integración real en Docker Compose

Se presenta el entorno QA con Users, Channels, Messages, Threads, el worker, cuatro MongoDB y RabbitMQ. La red compartida se llama `microsvcs` y las dependencias del flujo se comunican en la red privada de su proyecto.

El comando del lanzador se ejecuta sobre el directorio preparado para esa toma.

```sh
python integration/qa/run.py integration --directory "$QA_DIR"
```

`QA_DIR` representa el directorio privado externo de la ejecución. El video identifica el recorte de la espera de construcción y arranque. Después muestra las comprobaciones de salud, las pruebas HTTP, el reinicio y la limpieza.

El primer caso automatizado realiza el flujo completo.

1. Crea dos usuarios mediante la API de Users.
2. Crea el canal `Grupo de estudio` y un segundo canal para comprobar pertenencia.
3. Publica un mensaje raíz mediante Messages.
4. Consulta las referencias de usuarios y mensajes por HTTP.
5. Comprueba que el hilo empieza vacío.
6. Publica una respuesta mediante Threads y exige HTTP 201.
7. Verifica ID, canal, raíz, autor, contenido y fecha de la respuesta.
8. Recupera la respuesta mediante GET y comprueba que aparece una vez.
9. Consulta Messages y comprueba que el reply conserva su separación respecto de los mensajes raíz.
10. Prueba autor inexistente, raíz inexistente y raíz de otro canal, obteniendo 422, 404 y 404.
11. Confirma que esos rechazos conservan la lista de respuestas existente.

La salida del primer runner muestra **1 caso aprobado**. Las operaciones están automatizadas dentro de ese caso. Los IDs utilizados se obtienen de las respuestas HTTP de esa ejecución.

## 7. Persistencia tras reinicio

El lanzador reinicia el contenedor de Threads y registra `StartedAt` antes y después. Un segundo runner espera su recuperación y consulta la respuesta por HTTP.

La salida muestra **1 caso aprobado** de persistencia. Después se presentan los datos leídos de `before-restart.json` y `after-restart.json`.

La comparación exige igualdad completa de la respuesta, incluyendo ID, contenido, canal, mensaje raíz, autor y fecha. También se muestran los dos tiempos de arranque distintos, el proyecto QA, la revisión del código y los estados de error comprobados.

El resumen de usuarios se presenta como un conteo. Los encabezados del video identifican el proyecto y las comprobaciones.

## 8. Suite conjunta

El recorrido termina ejecutando la suite completa de Threads con los contratos de proveedor configurados.

```sh
python -m pytest -q -W error tests
```

La salida muestra **115 pruebas aprobadas y 6 omitidas**. Las seis omisiones corresponden a las pruebas opcionales de MongoDB/RabbitMQ que requieren sus URLs de infraestructura. La integración Docker del bloque anterior tiene sus propias instancias y sus resultados se muestran por separado.

La suite conjunta incluye además los casos existentes de GET con raíz inexistente, errores de dependencias, repositorio y entrega de eventos. Su salida final es resumida. Los conteos de los bloques se superponen porque la suite conjunta vuelve a ejecutar las pruebas de servicio y contrato.

## Evidencias de la toma y validación del archivo

El directorio local del video conserva `recording.json`, con los comandos, sus códigos de salida, los segmentos y el reporte de integración. El directorio QA externo conserva los reportes HTTP, JUnit, fuentes, imágenes y dependencias de esa ejecución.

La exportación genera `video-validation.json` y un archivo de subtítulos opcional con los nombres de los bloques. La validación comprueba la decodificación completa del MP4. La grabación se entrega sin audio.
