# Thread Service — Tarea 7

Microservicio FastAPI para crear y consultar respuestas de un nivel a mensajes del chat. Utiliza MongoDB para persistir respuestas y outbox, y un worker publica los eventos en RabbitMQ.

La Tarea 7 verifica esta capacidad mediante pruebas de servicio con almacenamiento aislado, contratos HTTP con Users y Messages e integración real con Users, Channels y Messages en Docker Compose.

Link video demostración tarea 7: https://usmcl-my.sharepoint.com/:v:/g/personal/andres_jablonca_usm_cl/IQAeXd8p4o9PQrJNO0_SUDENAQgSdCuw76TPXrrcyRs_ATE?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=amz8S5

La documentación anterior completa, incluida la entrega de Tarea 6, se conserva en [readme-tarea-6.md](readme-tarea-6.md).

## Integrantes

- Andrés Jablonca — 202173578-K.
- Isaías Carte — 202273606-2.

## Requisitos y cobertura

| Requisito de Tarea 7 | Implementación | Documentación |
|---|---|---|
| Dos pruebas por endpoint, incluyendo un error | Casos POST/GET de replies y salud, junto con los casos existentes | [Pruebas de servicio](docs/tarea7/QA_SERVICIOS_A.md) |
| Aislamiento de BD | Fixture function con mongomock nuevo, aplicación nueva, gateways sustituidos y limpieza en finally | [Tests de servicio](tests/test_qa_service.py) |
| Contrato con el chat base | Rutas originales de Users/Messages en proceso, persistencia sustituida y adaptadores reales de Threads | [Contratos](tests/test_qa_contract.py) |
| Integración Docker Compose | Usuarios → canal → mensaje raíz → respuesta → reinicio de Threads → lectura del mismo reply | [Lanzador QA](integration/qa/README.md) |
| Organización y evidencia | Reportes JUnit, fuentes verificadas, hashes, resultados y comandos reproducibles | [Resumen de evidencias](docs/tarea7/evidencias/resumen-b.md) |

## Preparar el entorno

Se requiere Python 3.12 y las dependencias de desarrollo. La integración requiere además Docker Engine con Compose v2 operativo.

Desde la raíz del repositorio, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

En Linux, usar `python3` para crear el entorno y `source .venv/bin/activate` para activarlo.

## Ejecutar pruebas de servicio

```sh
python -m pytest -q -W error tests/test_qa_service.py
```

Los ocho casos usan el lifespan operativo, las rutas y el repositorio del servicio. Cada caso recibe un MongoClient mongomock nuevo y dobles de Users/Messages. La fixture comprueba el estado inicial vacío, limpia la base de prueba y cierra los recursos al terminar.

Se verifican creación HTTP 201, respuesta y outbox coincidentes, rechazos 404/422 sin escrituras, consulta ordenada y filtrada y salud. El caso negativo de `/health` comprueba HTTP 405 por método incorrecto.

Para ejecutar toda la suite de Threads:

```sh
python -m pytest -q -W error tests
```

Las dos verificaciones de proveedor se omiten si `THREAD_QA_SOURCE` está ausente. Las seis pruebas opcionales de Mongo/Rabbit reales requieren `THREAD_TEST_MONGODB_URL` y `THREAD_TEST_RABBITMQ_URL`, según el caso. Una dependencia configurada que falla produce un error de prueba. Las instrucciones y los resultados por nivel están en [la guía de servicio](docs/tarea7/QA_SERVICIOS_A.md) y [la guía de contrato e integración](docs/tarea7/contrato-integracion.md).

## Ejecutar contratos e integración

El lanzador prepara las fuentes y credenciales en un directorio externo nuevo. Para PowerShell:

```powershell
$env:PYTHONUTF8 = '1'
$qa = Join-Path $env:TEMP ('tarea7-qa-' + [guid]::NewGuid().ToString('N'))

python integration/qa/run.py prepare --directory $qa
python integration/qa/run.py contract --directory $qa
python integration/qa/run.py integration --directory $qa
```

En Linux:

```sh
python3 integration/qa/run.py prepare --directory /var/tmp/tarea7-qa-ejecucion1
python3 integration/qa/run.py contract --directory /var/tmp/tarea7-qa-ejecucion1
python3 integration/qa/run.py integration --directory /var/tmp/tarea7-qa-ejecucion1
```

Elegir una ruta nueva en cada ejecución independiente. `prepare` descarga y verifica la revisión docente fijada. `contract` configura las fuentes originales y ejecuta los seis casos de contrato en proceso.

`integration` levanta Users, Channels, Messages, Threads, su worker, cuatro MongoDB y RabbitMQ en un proyecto QA propio. Utiliza la red compartida `microsvcs` y una red privada para el flujo. Las APIs conservan sus puertos internos y el runner se ejecuta dentro de Compose.

El flujo crea los registros por HTTP, verifica sus relaciones y comprueba los errores de autor o raíz inexistentes y raíz de otro canal. Después reinicia Threads y exige recuperar la misma respuesta completa. Los reportes registran los tiempos de arranque antes y después.

La limpieza automática elimina los recursos del proyecto QA y conserva los reportes y la red compartida. Para inspeccionar el entorno, añadir `--keep` al comando de integración y limpiarlo después con:

```powershell
python integration/qa/run.py cleanup --directory $qa
```

Los resultados quedan en `evidence/` dentro del directorio elegido. La ejecución detallada y sus opciones se describen en [integration/qa/README.md](integration/qa/README.md).

### Fuentes del chat base

El lock fija el commit docente `d15f2e20ced1007099b90bf59b720e97be3d2d4a`. Los contratos verifican las rutas originales con persistencia sustituida. La integración positiva usa copias privadas con el parche de serialización `insert_one(documento.copy())` en Users, Channels y Messages.

Los hashes originales y corregidos y la identidad del parche quedan en `sources.json`. El código de los servicios base se prepara fuera del repositorio. La verificación de esas copias tiene cuatro pruebas propias, ejecutables después de `prepare` en PowerShell:

```powershell
$env:THREAD_QA_SOURCE = (Get-Content (Join-Path $qa 'qa.json') -Raw -Encoding UTF8 | ConvertFrom-Json).original
python -m pytest -q -W error integration/qa/test_sources.py
```

## Resultados registrados

| Validación | Resultado |
|---|---|
| Nuevas pruebas de servicio | 8 aprobadas |
| Contratos Users/Messages con fuentes configuradas | 6 aprobadas |
| Verificación de copias QA | 4 aprobadas |
| Suite local conjunta con contratos configurados | 115 aprobadas, 6 omitidas de infraestructura opcional |
| CI del PR #12, con Mongo/Rabbit efímeros | 119 aprobadas, 2 omitidas de proveedor sin fuentes configuradas |
| Integración Docker y persistencia | Flujo y lectura tras reinicio aprobados en ejecuciones independientes |

Los conteos se superponen porque la suite conjunta vuelve a ejecutar pruebas de servicio y contrato. Los workflows existentes ejecutan la suite general. La integración específica de `integration/qa/` tiene evidencia local documentada.

Las fuentes, imágenes, reportes HTTP, JUnit y hashes del código probado se conservan en [las evidencias finales](docs/tarea7/evidencias/b-final/). CI y la revisión del cambio están registrados en el [PR #12](https://github.com/IsaiasACF/Thread-Service/pull/12).

## Video y documentos de la entrega

El [video de demostración de Tarea 7](video-qa-t7.mp4) dura aproximadamente **2:05**. Muestra las pruebas, la integración Docker y la lectura del mismo reply tras reiniciar Threads, con encabezados neutrales y sin narración.

- [Contenido del video, tiempos y resultados](docs/tarea7/contenido-video.md).
- [Guion de grabación](docs/tarea7/guion-video.md).
- [Planificación y reparto de responsabilidades](docs/tarea7/planificacion.md).
- [Servicio y aislamiento de BD](docs/tarea7/QA_SERVICIOS_A.md).
- [Contratos e integración](docs/tarea7/contrato-integracion.md).
- [Revisión del PR de servicio](docs/tarea7/revision-pr-isaias.md).

## API de Thread Service

| Método | Ruta | Resultado |
|---|---|---|
| POST | `/api/v1/channels/{channel_id}/messages/{message_id}/replies` | 201 con el reply creado |
| GET | `/api/v1/channels/{channel_id}/messages/{message_id}/replies` | 200 con replies ordenados por fecha e ID |
| GET | `/health` | 200 como comprobación de vida |

POST recibe `{"author_id":"user-id","content":"Texto de respuesta"}`. La respuesta incluye `id`, `channel_id`, `message_id`, `author_id`, `content` y `created_at`. El servicio valida referencias mediante las APIs de Users y Messages y persiste reply y evento pendiente en un documento MongoDB.

La configuración operativa, los eventos RabbitMQ y las instrucciones anteriores de Docker, Kubernetes e interfaz se conservan en [readme-tarea-6.md](readme-tarea-6.md). La entrega integrada de interfaz se documenta en [ENTREGA_FINAL.md](docs/tarea6/ENTREGA_FINAL.md).
