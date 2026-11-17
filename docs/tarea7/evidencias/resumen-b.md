# Resultados de contrato e integración de Andrés

Ejecuciones del 16 de noviembre de 2026 en la rama `feature/tarea7-qa-integration`. Base de trabajo `335d42e`. Primer commit de contratos `df823d9`.

| Validación | Resultado |
|---|---|
| Contratos de Users/Messages con fuentes configuradas | 6 aprobadas en cada ejecución |
| Suite existente y contratos, `pytest -q -W error tests` | 107 aprobadas, 6 omitidas de infraestructura real opcional |
| Suite sin ruta de proveedor | 105 aprobadas, 8 omitidas, incluidas dos de proveedor |
| Regresión de preparador y lanzador Chat, con fuente original configurada | 23 aprobadas en Python 3.12 de WSL |
| Flujo HTTP del primer proyecto Docker | 1 aprobada |
| Persistencia tras reinicio del primer proyecto | 1 aprobada |
| Flujo HTTP del segundo proyecto Docker | 1 aprobada |
| Persistencia tras reinicio del segundo proyecto | 1 aprobada |
| Suite conjunta con PR #11 integrado en main | 115 aprobadas, 6 omitidas de infraestructura opcional |
| Verificador portable propio de Tarea 7 | 4 aprobadas |
| Flujo HTTP y persistencia de la versión final | 1 aprobada en cada fase |

## Dos ejecuciones independientes

| Ejecución | Proyecto | Reply obtenido por HTTP | Evidencia |
|---|---|---|---|
| Primera | `tarea7-qa-4bd39270f4cf` | `d0014d41-607a-4acb-8cc1-0a6ee5a2803d` | [Resumen y reinicio](b-run1/integration-summary.json) |
| Segunda | `tarea7-qa-a7e1fc485050` | Consultar `reply.id` en el reporte | [Flujo y referencias](b-run2/before-restart.json) |

En cada proyecto, el reply leído después del reinicio coincide por completo con el creado. Los tiempos `StartedAt` cambian y los IDs pertenecen a registros creados mediante las APIs de esa ejecución.

Los reportes JUnit de [contrato](b-run2/contrato.xml), [flujo](b-run2/integracion.xml) y [persistencia](b-run2/persistencia.xml) permiten revisar los casos individuales. El [reporte de fuentes](b-run2/sources.json) identifica el parche local y sus hashes. Se conservan también las [imágenes](b-run2/images.json) y las [dependencias del runner](b-run2/dependencies.txt).

## Trazabilidad del contenido probado

Las pruebas se ejecutaron antes de incorporar los archivos de integración al segundo commit. Por eso `projectCommit` registra `df823d9`. El [segundo resumen](b-run2/integration-summary.json) registra además el árbol con cambios y los SHA-256 de ocho archivos probados. Estos hashes corresponden a los bytes del checkout usado durante la ejecución. La primera ejecución precede a la incorporación de ese inventario.

El código docente se fija en `d15f2e20ced1007099b90bf59b720e97be3d2d4a`. Los contratos ejecutan sus rutas originales con persistencia sustituida. Los proyectos Docker usan las tres copias corregidas por el parche de serialización documentado en `sources.json`.

## Reproducción

Se ejecutaron `prepare`, `contract` e `integration` con el lanzador `integration/qa/run.py`, usando un directorio externo nuevo por proyecto. En Windows se utilizó Python 3.12 local con `PYTHONUTF8=1`. El procedimiento completo está en [la guía de ejecución](../../../integration/qa/README.md).

La suite y la regresión se ejecutaron con estos argumentos, configurando previamente las fuentes:

```sh
python -m pytest -q -W error tests
python -m pytest -q -W error integration/chat/test_patch.py integration/chat/test_launcher.py
```

`THREAD_QA_SOURCE` configura las pruebas de contrato. `CHAT_TEST_ORIGINAL_SOURCE` configura los casos de regresión del parche. En la regresión se utilizó Python completo de WSL porque el intérprete portable de Windows carece de `venv`.

La limpieza del lanzador eliminó ambos proyectos QA. Los archivos privados de entorno y las fuentes descargadas permanecen en sus directorios temporales externos. Los contenedores y volúmenes de otras tareas conservan su propio ciclo de vida.

## Versión final preparada para publicar

La versión final parte de main en `8056cb2`, con el PR #11 de Isaías incorporado. La comparación publicable comprende `docs/tarea7/`, `integration/qa/` y los dos módulos de contrato en `tests/`.

La preparación portable se encuentra en `integration/qa/sources.py`. Sus cuatro pruebas verifican una copia válida y el rechazo de alteraciones. Los archivos compartidos de preparación se utilizan en la revisión existente de main.

La ejecución `tarea7-qa-c988e48ae6cb` completó los contratos, el flujo HTTP y la lectura de la misma respuesta tras reinicio. Su [reporte final](b-final/integration-summary.json) registra hashes del código probado y los tiempos de arranque. Las evidencias de las dos ejecuciones anteriores se conservan como antecedentes del desarrollo.

La revisión del PR de Isaías se encuentra en [revision-pr-isaias.md](../revision-pr-isaias.md). Quedan pendientes la revisión remota de la rama de Andrés, CI de esa publicación y el video de Tarea 7.
