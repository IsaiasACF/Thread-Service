# Validación independiente del núcleo

## API y errores

Las rutas `/api/v1` y los esquemas públicos se mantienen. OpenAPI declara
201/200 y errores 404, 422, 500, 502 y 503, con ejemplos y esquemas. Un 422
puede contener `detail` como texto (autor inexistente) o como arreglo de errores
(validación de entrada), conservando el comportamiento previo de FastAPI.

| Origen | HTTP | `detail` |
|---|---|---|
| Mensaje fuera del canal o inexistente | 404 | `Root message not found in channel` |
| Autor inexistente | 422 | `Author does not exist` |
| Respuesta externa incorrecta | 502 | `Dependent service failed` |
| Red/timeout de gateway | 503 | `Dependent service unavailable` |
| Conexión MongoDB, reconexión o timeout de red/selección | 503 | `Storage unavailable` |
| Otros errores PyMongo, incluida operación rechazada | 500 | `Storage operation failed` |
| Adaptadores no inyectados | 503 | `Thread Service not configured` |

`app/errors.py` define los errores de almacenamiento sin depender de PyMongo.
El repositorio traduce excepciones del driver, incluida la iteración diferida de
cursores; la causa original se conserva para diagnóstico interno. Los handlers
HTTP nunca incluyen mensajes del driver, credenciales ni respuestas upstream.
Estos errores también se propagan desde los métodos de outbox e índices;
las firmas de los puertos y el contrato del worker permanecen intactos.
`/health` es una comprobación de vida, no de conectividad o readiness.

## Persistencia y outbox

`save_with_outbox` hace un único `insert_one` con la respuesta y su evento
pendiente. No hay una escritura separada ni una transacción multidocumento.
Las pruebas verifican la llamada única, los datos coincidentes del evento,
los índices únicos y la ausencia de un segundo documento al rechazar duplicados.
El repositorio no añade reintentos propios de inserción: una pérdida de conexión
puede ocurrir después de persistir y antes de recibir confirmación. Un error HTTP
no demuestra que la escritura no ocurrió; repetir POST puede crear otra respuesta.
No se incorpora idempotencia HTTP, fuera del contrato aprobado. Los reintentos
internos del driver dependen de la configuración del futuro MongoClient.

El reclamo mantiene `find_one_and_update`, lease, incremento de intentos y token
nuevo por reclamo. Confirmar/liberar requiere el token vigente y evento pendiente.
Tras otro reclamo, el token anterior no puede modificar el evento. La expiración
por sí sola habilita un nuevo reclamo; no invalida el token hasta que otro reclamo
lo reemplaza. El worker debe publicar dentro del lease, como indica el contrato.
No se garantiza exactamente una publicación ni orden de publicación de eventos.
Los relojes de las instancias deben estar sincronizados para interpretar leases.

La lista pública excluye `_id` y `_outbox`, filtra canal y mensaje y ordena por
`created_at` decodificado e `id`. Esto corrige el orden ISO textual con fracciones
opcionales sin migrar documentos existentes. El resultado completo ya se cargaba
en memoria; su tamaño sigue sin estar limitado por paginación.

## Pruebas

- API y servicio: creación, consultas vacías, referencias inexistentes, validación
  de tipos, campos requeridos, blancos, límites tras strip, fallas de gateways y
  almacenamiento, ausencia de escrituras en rechazos, coherencia del evento.
- OpenAPI: códigos, esquemas, ejemplos y ambas formas de 422.
- Repositorio con mongomock/mocks: aislamiento, orden cronológico con desempate,
  privacidad del outbox, escritura única, errores diferidos, duplicados, reclamo,
  confirmación, liberación, leases inválidos, recuperación y tokens obsoletos.
- MongoDB 7 real: competencia entre 16 llamadas por uno y por varios eventos,
  recuperación de lease expirado, tokens anteriores, carrera confirmación/liberación
  y rechazo atómico de un insert duplicado. Se prueban operaciones del repositorio;
  no se implementa ni simula un worker de publicación. La expiración se provoca
  actualizando la fecha de lease en MongoDB, sin esperas dependientes del reloj.

Las pruebas con MongoDB real se ejecutan en CI mediante
`THREAD_TEST_MONGODB_URL`. Sin esa variable se omiten; con ella, una conexión
fallida hace fallar las pruebas. Las pruebas de mongomock no demuestran por sí
solas concurrencia entre procesos. Las pruebas reales verifican los escenarios
anteriores, no constituyen una prueba exhaustiva de todos los fallos distribuidos.

Validación local de esta implementación: **74 pruebas aprobadas**, incluidas cinco
con MongoDB 7 real, ejecutando `pytest -q -W error` con Python 3.12. No hubo
advertencias de Python. Las acciones checkout/setup-python se actualizan a v6,
que utiliza Node 24, para eliminar también el aviso de Node 20 en CI.

## Comprobaciones posteriores con Persona 2

- Clientes REST reales contra Users y el listado de Messages; traducción de fallas
  y validación de mensajes según los puertos existentes.
- Configuración y ciclo de vida del MongoClient, timeouts, credenciales, write
  concern e invocación de `ensure_indexes` en el ensamble productivo.
- RabbitMQ: publisher confirms, persistencia, ID estable, reintentos/backoff,
  duplicados y caída del worker después de publicar pero antes de confirmar outbox.
- Docker Compose completo y arranque `app.asgi:app`; el contenedor MongoDB de
  pruebas solo valida el repositorio y no verifica ese despliegue.
- Kubernetes: configuración, DNS, secretos, sondas y comportamiento entre réplicas.

No se modifican `app/ports.py`, `docs/contracts.md` ni archivos de Persona 2.
