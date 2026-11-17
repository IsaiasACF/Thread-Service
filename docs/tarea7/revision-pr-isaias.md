# Revisión del PR #11 de Isaías

Se revisó el [PR #11](https://github.com/IsaiasACF/Thread-Service/pull/11), fusionado en `8056cb2cdf35ab5d373837843fbc6cc1d6fecc09`. Incluye dos archivos agregados, `tests/test_qa_service.py` y `docs/tarea7/QA_SERVICIOS_A.md`, con 430 líneas en total.

## Resultado de la revisión

No se encontraron defectos funcionales que requieran corregir las pruebas del PR. Se verificaron por inspección y ejecución el arranque operativo de ASGI, la persistencia del reply y su outbox, los rechazos sin escritura, el filtrado y orden de GET y la semántica de liveness.

| Aspecto | Comprobación |
|---|---|
| Aislamiento | Fixture function, cliente mongomock nuevo y aplicación nueva por caso |
| Mongo real | Constructor protegido con un mock que falla si se invoca |
| Dependencias HTTP | Puertos Users/Messages sustituidos antes del lifespan |
| Limpieza | Contexto de TestClient, retirada del servicio de app.state y drop/close en finally |
| POST válido | 201, reply completo, un documento y outbox embebido coincidente |
| POST inválido | 404/422, colección vacía y ausencia de evento reclamable |
| GET | Estado vacío inicial, orden por fecha/ID y filtro por canal y raíz |
| Salud | GET 200 y POST 405 con Allow incluyendo GET |

El caso negativo de salud verifica un método no permitido en la ruta. La aceptación de ese caso para el criterio «error por endpoint» depende de la interpretación de la rúbrica. La documentación del PR ya distingue este caso de la salud de las dependencias.

## Ejecución observada

Se ejecutaron los siguientes comandos en Python 3.12, con las dependencias de desarrollo del repositorio.

```sh
python -m pytest -q -W error tests/test_qa_service.py
python -m pytest -q -W error tests/test_qa_service.py::test_new_fixture_starts_with_empty_thread_and_no_outbox tests/test_qa_service.py::test_post_persists_exactly_one_reply_and_matching_outbox
```

La suite del PR completó **8 casos aprobados**. Los dos casos de independencia en orden inverso completaron **2 casos aprobados**. La validación conjunta con las pruebas de contrato de Andrés configuradas completó **115 aprobadas y 6 omitidas**. Las omisiones locales corresponden a los tests opcionales de Mongo/Rabbit reales.

La documentación de Isaías conserva su evidencia histórica de CI con infraestructura efímera. Los conteos locales de esta revisión se registran por separado porque incluyen los nuevos casos de contrato.

Se encontró una nota documental desactualizada al final de `QA_SERVICIOS_A.md` que pide mantener abierto el PR. GitHub confirma que el PR ya fue fusionado. Esta nota describe una instrucción previa a su integración.
