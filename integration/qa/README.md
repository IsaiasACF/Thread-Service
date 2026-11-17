# QA de Threads con el chat base

El lanzador prepara fuentes verificadas, ejecuta contratos en proceso y demuestra por HTTP el flujo real de Threads con Users, Channels y Messages en Docker Compose.

Se requiere Python 3.12 con `requirements-dev.txt` instalado y Docker Engine con Compose v2. Ejecutar desde la raíz del repositorio. El directorio de trabajo debe ser nuevo y externo al repositorio. En Windows, activar UTF-8 para las rutas con acentos. `integration/qa/sources.py` verifica las copias privadas con rutas portables usando el lock y las definiciones del parche existentes en main.

```powershell
$env:PYTHONUTF8 = '1'
$qa = Join-Path $env:TEMP ('tarea7-qa-' + [guid]::NewGuid().ToString('N'))
python integration/qa/run.py prepare --directory $qa
python integration/qa/run.py contract --directory $qa
python integration/qa/run.py integration --directory $qa
```

En Linux, con un directorio externo nuevo:

```sh
python3 integration/qa/run.py prepare --directory /var/tmp/tarea7-qa-ejecucion1
python3 integration/qa/run.py contract --directory /var/tmp/tarea7-qa-ejecucion1
python3 integration/qa/run.py integration --directory /var/tmp/tarea7-qa-ejecucion1
```

## Fuentes y contratos

`prepare` reutiliza el preparador de `integration/chat/` y su lock del commit docente `d15f2e20ced1007099b90bf59b720e97be3d2d4a`. Conserva el original y prepara copias privadas corregidas para los POST de Docker. El cambio consiste en insertar copias de los diccionarios para evitar devolver `_id` agregado por PyMongo. Los hashes y la identidad del parche se guardan en `evidence/sources.json`.

`contract` comprueba los hashes originales y configura `THREAD_QA_SOURCE`. Ejecuta los seis casos de `tests/test_qa_contract.py`. Las rutas originales corren con persistencia sustituida. Las pruebas verifican la estructura mínima de respuestas y el comportamiento de los adaptadores reales de Threads. Las dependencias y fuentes se preparan antes de pytest.

## Integración y persistencia

`integration` construye las imágenes y espera las comprobaciones de salud. Un runner interno crea Andrés, Isaías, Grupo de estudio, un mensaje raíz y una respuesta. Verifica su lectura, pertenencia, fecha, separación respecto de los mensajes raíz y rechazos 422/404 sin respuestas adicionales.

El host reinicia el contenedor de Threads y registra `StartedAt` antes y después. Un segundo runner espera la recuperación y consulta el mismo reply por HTTP. Las bases y el worker pertenecen al proyecto QA. Las APIs se comunican por la red privada del proyecto y Threads también se conecta a `microsvcs`. El entorno se ejecuta con puertos internos.

Los resultados quedan en el subdirectorio `evidence/` del directorio elegido:

| Archivo | Contenido |
|---|---|
| `contrato.xml` | Seis casos de contrato |
| `integracion.xml` | Flujo positivo y negativo por HTTP |
| `persistencia.xml` | Lectura de la misma respuesta tras reinicio |
| `before-restart.json`, `after-restart.json` | Datos obtenidos de APIs y comparaciones |
| `integration-summary.json` | Proyecto, revisión del código, modo de fuente y tiempos de arranque |
| `sources.json` | Hashes originales/corregidos y metadatos del parche |
| `compose-status.json`, `images.json`, `dependencies.txt` | Servicios, imágenes y dependencias observadas |

El primer paso que falla devuelve código distinto de cero. La limpieza se ejecuta al finalizar, incluso si una prueba falla. Los archivos de resultados y las fuentes permanecen disponibles.

## Inspección y limpieza

Para conservar el proyecto al finalizar y revisarlo, añadir `--keep` al comando de integración. Después ejecutar:

```sh
python integration/qa/run.py cleanup --directory <DIRECTORIO_QA>
```

La limpieza utiliza el nombre de proyecto aleatorio guardado en `qa.json` y verifica su asociación con este repositorio. Elimina contenedores, red privada y volúmenes propios. La red compartida `microsvcs` se conserva. La limpieza sigue disponible aunque se haya alterado una fuente externa después de probar.

`qa.env` y `compose.env` contienen credenciales locales de prueba. Los reportes seleccionados para Git deben revisarse antes de copiarlos. La documentación y los resultados de Andrés están en [la guía de contrato e integración](../../docs/tarea7/contrato-integracion.md).
