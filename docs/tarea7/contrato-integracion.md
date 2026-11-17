# Contrato e integración de Andrés

## Implementación y avance

Trabajo del integrante B en `feature/tarea7-qa-integration`, desde `main` en `335d42e`. Isaías mantiene las pruebas de servicio y sus fixtures según la planificación compartida.

La primera etapa verifica los contratos de Users y Messages. La segunda etapa implementa el flujo Docker y la comprobación HTTP de persistencia tras reiniciar Threads.

## Contratos implementados

Los archivos `tests/test_qa_contract.py` y `tests/qa_contract_support.py` cargan las rutas originales de los proveedores en módulos propios, con `MongoClient` sustituido antes de importar. Los registros se suministran mediante una colección de prueba controlada. `TestClient` ejecuta las rutas y el transporte del consumidor entrega esas respuestas a los adaptadores REST reales de Threads.

La revisión docente es `d15f2e20ced1007099b90bf59b720e97be3d2d4a`, subdirectorio `03_Comunicación/demo`. La fixture comprueba los hashes de `integration/chat/source.lock.json`. Cambiar un archivo fijado hace fallar la prueba.

| Caso | Verificación |
|---|---|
| Users válido y ausente | GET correcto, 200 con ID string coincidente, 404 y `User not found`, aceptación y rechazo del consumidor |
| Messages válido y ausente | Lista de mensajes con IDs y canal string, pertenencia a canal y raíz, lista vacía para canal sin registros |
| Users incompatible, dos variantes | ID numérico o ID ausente rechazados por expectativas independientes y adaptador |
| Messages incompatible, dos variantes | `channel_id` ausente o ID numérico rechazados por expectativas y adaptador |

Los casos válidos incluyen campos adicionales para comprobar compatibilidad con extensiones. Se capturan las rutas y métodos solicitados por el consumidor. Las colecciones verifican que los GET no llaman a `insert_one`. La fixture del módulo bloquea `socket.create_connection` y las pruebas usan transporte en proceso.

Las pruebas verifican una revisión local del proveedor con persistencia sustituida. No constituyen un pacto publicado y verificado en el CI docente.

### Ejecución directa de contratos

Instalar `requirements-dev.txt` en un entorno Python 3.12. Preparar primero las fuentes mediante la herramienta existente, usando un directorio nuevo fuera del repositorio.

```sh
python integration/chat/prepare.py --directory <DIRECTORIO_EXTERNO> --mode original
```

Asignar `THREAD_QA_SOURCE` al subdirectorio original indicado por el preparador y ejecutar pytest. En PowerShell:

```powershell
$env:THREAD_QA_SOURCE = '<RUTA_ORIGINAL_DEL_CHAT>'
python -m pytest -q -W error tests/test_qa_contract.py
```

En Linux/WSL:

```sh
THREAD_QA_SOURCE='<RUTA_ORIGINAL_DEL_CHAT>' python3 -m pytest -q -W error tests/test_qa_contract.py
```

La suite general permite omitir las dos verificaciones de proveedor cuando no hay ruta configurada. El comando de contrato de Tarea 7 configura la ruta explícitamente y requiere que los seis casos pasen. Una ruta configurada incorrecta o con hashes distintos produce un fallo.

## Registro de trabajo

1. Se revisó `main`, se creó la rama acordada y se conservaron los cambios locales de la sesión anterior.
2. Se implementaron las verificaciones de proveedor y consumidor. La ejecución inicial completó **6 pruebas aprobadas** mediante Python 3.12 en WSL y fuentes originales verificadas.
3. Se preparó un entorno QA independiente con copias docentes corregidas. El parche documentado de `insert_one(documento.copy())` se aplica a las copias de Users, Channels y Messages utilizadas por Docker. Los contratos GET utilizan las fuentes originales.
4. Docker Desktop se inició para ejecutar la integración. La distribución WSL disponible tiene deshabilitada su integración con Docker. Se preparó Python local en `.venv/python-win/` para ejecutar el lanzador desde Windows. Las dependencias y archivos privados permanecen en directorios de trabajo locales.

5. La preparación inicial detectó diferencias de rutas y codificación en Windows. La versión final resuelve ambos casos en `integration/qa/sources.py`, que lee el lock en UTF-8 y normaliza las rutas con `as_posix()`. La preparación reutiliza la descarga original y las definiciones del parche ya disponibles en main. Cuatro pruebas propias verifican la copia y el rechazo de archivos extra, código alterado y metadatos inválidos. La regresión inicial de las herramientas existentes completó 23 casos en Linux.
6. La suite `tests/` pasó con **107 aprobadas y 6 omitidas** al configurar las fuentes de proveedor. Las seis omitidas corresponden a los tests opcionales de Mongo/Rabbit reales. La ejecución sin ruta de proveedor tuvo 105 aprobadas y 8 omitidas, incluyendo las dos verificaciones de proveedor.
7. La integración pasó en dos proyectos nuevos, `tarea7-qa-4bd39270f4cf` y `tarea7-qa-a7e1fc485050`. Cada uno completó un caso de flujo y un caso de persistencia tras reinicio. Ambos finalizaron con eliminación de sus contenedores y volúmenes QA. Los resultados seleccionados están en [el resumen de evidencias de B](evidencias/resumen-b.md).
8. Se incorporó `origin/main` en `8056cb2`, que contiene el PR #11 de Isaías. La suite conjunta completó **115 pruebas aprobadas y 6 omitidas** de infraestructura opcional. Se preparó una versión publicable limitada a `docs/tarea7/`, `integration/qa/` y los dos archivos de contrato. El historial anterior se conserva en una rama local de respaldo.

## Lanzador de Tarea 7

El procedimiento reproducible y las opciones de inspección están en [integration/qa/README.md](../../integration/qa/README.md). Los comandos se ejecutan desde la raíz con Python 3.12 y Docker Compose v2.

```sh
python integration/qa/run.py prepare --directory <DIRECTORIO_QA_EXTERNO_NUEVO>
python integration/qa/run.py contract --directory <DIRECTORIO_QA_EXTERNO_NUEVO>
python integration/qa/run.py integration --directory <DIRECTORIO_QA_EXTERNO_NUEVO>
```

En Windows se utilizó el intérprete local `.venv/python-win/python.exe` con `PYTHONUTF8=1`. Las fuentes descargadas, credenciales y dependencias permanecen en directorios privados externos o ignorados.

Cada ejecución tiene nombre de proyecto y cuatro volúmenes Mongo propios. El flujo utiliza Users, Channels y Messages reales, el ASGI operativo de Threads y su worker. El runner accede a las APIs por la red privada. Threads también participa en `microsvcs`.

El flujo crea Andrés e Isaías, Grupo de estudio, un mensaje de Andrés y una respuesta de Isaías. Verifica relaciones, fecha, lectura exacta y que la respuesta se almacene como reply. Prueba autor inexistente, raíz inexistente y raíz de otro canal, con 422/404 y lista de replies sin cambios. El host reinicia Threads y un runner nuevo recupera la misma respuesta por HTTP. El reporte contiene los dos valores distintos de `StartedAt`.

El lanzador devuelve un error ante un fallo y ejecuta la limpieza por proyecto en `finally`. Los reportes y las fuentes se conservan en el directorio de ejecución. `--keep` permite inspeccionar el entorno y `cleanup` elimina después sus recursos, conservando `microsvcs`.

## Alcance de la evidencia

Los contratos verifican las fuentes originales. La integración positiva utiliza copias locales corregidas mediante `insert_one(documento.copy())`. Los reportes de fuentes contienen hashes originales y corregidos y el identificador del parche. El repositorio docente remoto conserva su revisión original.

Los reportes se generan antes de los commits de documentación y publicación. `projectCommit` identifica el commit existente durante cada prueba. La segunda ejecución agrega `worktreeDirty` y hashes de los archivos probados. Las dos ejecuciones iniciales se conservan como antecedentes. La ejecución final valida la preparación exclusiva de Tarea 7 con los archivos compartidos de main.

La comprobación de publicación Rabbit con cola temporal queda como ampliación del plan. El flujo acredita las APIs REST y la persistencia de Threads. El trabajo de servicio de Isaías ya está integrado en main y fue incluido en la validación local conjunta. La revisión del PR de Andrés, CI y la grabación de Tarea 7 continúan como pasos de entrega.
