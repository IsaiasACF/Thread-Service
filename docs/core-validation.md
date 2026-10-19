# Cobertura y límites de validación

## Núcleo

La suite comprueba esquemas y ejemplos OpenAPI, validación de entrada, referencias inexistentes, orden de validaciones, ausencia de escrituras al rechazar operaciones, coherencia de respuesta/evento y traducción de errores a HTTP 404/422/500/502/503. No se exponen mensajes internos de MongoDB.

El repositorio se prueba con mocks/mongomock y, opcionalmente, MongoDB 7 real. Las cinco pruebas de concurrencia reales cubren reclamos paralelos, recuperación de lease, tokens obsoletos, carrera entre confirmar/liberar y rechazo atómico de inserciones duplicadas. Se habilitan con `THREAD_TEST_MONGODB_URL`; sin variable se omiten, con una URL inválida fallan.

## Integraciones y ensamble

- HTTPX MockTransport verifica rutas, cuerpos incompatibles, JSON inválido, 404, estados inesperados y timeouts/fallas de conexión. No sustituye una comprobación contra las implementaciones particulares de los servicios base conectados.
- El lifespan operativo se prueba inyectando MongoDB simulado y gateways controlados: crea índices, inyecta el servicio, permite POST/GET y retira el servicio al cerrar.
- El worker verifica publicación antes de marcar, propagación de fallas, liberación con token y conservación del evento cuando falla la confirmación o se pierde el reclamo.
- El publicador se comprueba con una conexión controlada: confirms, persistencia, routing key, ID estable, mandatory y cierre de conexión incluso ante fallo.
- La prueba real de entrega usa MongoDB y RabbitMQ: publica, simula caída después de publicar y antes de marcar, expira el lease y verifica dos entregas con el mismo ID y el posterior marcado en MongoDB. Requiere también `THREAD_TEST_RABBITMQ_URL`. Usa recursos con nombres únicos que elimina al finalizar.

## Ejecución reproducible

`docker compose --profile test run --build --rm tests` instala las dependencias y ejecuta la suite con Python 3.12 y servicios reales. GitHub Actions configura MongoDB y RabbitMQ, ejecuta la suite con advertencias como errores, valida Compose y construye la imagen runtime. La prueba de lifespan no realiza llamadas a Users/Messages reales; los contratos esperados están en README y contracts.

## Límites operativos

- `/health` es liveness, no readiness.
- No hay idempotencia HTTP: un error después de una escritura ambigua no prueba que no se guardó el documento. No se reintenta esa inserción desde la aplicación ni desde el driver.
- El registro respuesta/evento es atómico; la entrega posterior es al menos una vez bajo recuperación del broker y almacenamiento, con posibles duplicados. No se garantiza orden.
- Los timeouts AMQP y MongoDB limitan bloqueos normales; un retraso extraordinario que exceda el lease permite otro reclamo. Los consumidores deben deduplicar.
- No hay paginación, limpieza del historial de outbox, failover del almacenamiento ni autenticación en este alcance. La lista se ordena en memoria por fecha decodificada e ID.
- Los volúmenes Compose aportan persistencia local; no prueban recuperación ante pérdida del disco. Las pruebas no constituyen una verificación exhaustiva de todas las fallas distribuidas.
- La compatibilidad final con Users/Messages depende de que sus respuestas respeten los contratos documentados. Este repositorio no incluye esos servicios.
